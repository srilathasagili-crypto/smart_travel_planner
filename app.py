import os
import re

import pandas as pd
import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv
from services.places_service import PlacesService

load_dotenv()

try:
    import spacy
    try:
        _NLP = spacy.load("en_core_web_sm")
    except OSError:
        _NLP = None
except ImportError:
    _NLP = None

try:
    import anthropic
except ImportError:
    anthropic = None


# ============================================================================
# CONFIG
# ============================================================================

def _get_secret(key: str, default: str = "") -> str:
    """Check st.secrets first (Streamlit Cloud), then environment variables (local/.env)."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


class Config:
    ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY", "")
    MAX_PLACES_PER_CATEGORY = int(
        _get_secret("MAX_PLACES_PER_CATEGORY", 8)
    )


def validate_config():
    return True


# ============================================================================
# NLP: intent classification + entity extraction
# ============================================================================

PREFERENCE_KEYWORDS = {
    "tourist_places": [
        "tourist", "attractions", "sightseeing", "places", "monuments",
        "temples", "landmarks", "museums", "parks", "famous places",
    ],
    "restaurants": ["restaurant", "food", "eat", "dining", "cuisine", "cafe", "street food"],
    "hotels": ["hotel", "stay", "accommodation", "lodge", "resort", "homestay"],
    "adventure": ["adventure", "trekking", "hiking", "sports", "adrenaline"],
    "shopping": ["shopping", "market", "mall", "souvenirs"],
    "nightlife": ["nightlife", "pub", "club", "bar"],
}

BUDGET_KEYWORDS = {
    "budget": ["budget", "cheap", "affordable", "low cost", "economical"],
    "luxury": ["luxury", "premium", "5 star", "five star", "high end"],
    "mid-range": ["mid-range", "moderate", "3 star", "four star", "comfortable"],
}

TRIP_INTENT_PATTERNS = [r"\bplan\b.*\btrip\b", r"\bvisit\b", r"\btravel\b", r"\bitinerary\b", r"\btour\b"]
DAYS_PATTERN = re.compile(r"(\d+)\s*(?:-|\s)?\s*day", re.IGNORECASE)
LOCATION_PATTERN = re.compile(r"\b(?:to|in|for|near)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*)")
STOPWORDS_IN_LOCATION = {"Days", "Day", "Famous", "Good", "Budget"}


def detect_intent(text: str) -> str:
    lowered = text.lower()
    for pattern in TRIP_INTENT_PATTERNS:
        if re.search(pattern, lowered):
            return "plan_trip"
    return "unknown"


def extract_destination(text: str):
    if _NLP is not None:
        doc = _NLP(text)
        for ent in doc.ents:
            if ent.label_ in ("GPE", "LOC"):
                return ent.text.strip()
    for m in LOCATION_PATTERN.findall(text):
        if m not in STOPWORDS_IN_LOCATION:
            return m.strip()
    return None


def extract_days(text: str) -> int:
    match = DAYS_PATTERN.search(text)
    return max(1, int(match.group(1))) if match else 3


def extract_preferences(text: str) -> list:
    lowered = text.lower()
    found = [cat for cat, kws in PREFERENCE_KEYWORDS.items() if any(kw in lowered for kw in kws)]
    return found or ["tourist_places", "restaurants"]


def extract_budget(text: str) -> str:
    lowered = text.lower()
    for level, kws in BUDGET_KEYWORDS.items():
        if any(kw in lowered for kw in kws):
            return level
    return "mid-range"


def parse_travel_query(text: str) -> dict:
    return {
        "intent": detect_intent(text),
        "destination": extract_destination(text),
        "days": extract_days(text),
        "preferences": extract_preferences(text),
        "budget": extract_budget(text),
    }


# ============================================================================
# ITINERARY GENERATION (rule-based, with optional Claude narrative)
# ============================================================================

SLOTS = ["Morning", "Afternoon", "Evening"]


def _chunk_round_robin(items: list, n_buckets: int) -> list:
    buckets = [[] for _ in range(n_buckets)]
    for i, item in enumerate(items):
        buckets[i % n_buckets].append(item)
    return buckets


def generate_rule_based_itinerary(destination, days, ordered_places, restaurants, hotels):
    place_buckets = _chunk_round_robin(ordered_places, days)
    restaurant_buckets = _chunk_round_robin(restaurants, days)
    itinerary = []
    for day_index in range(days):
        day_places = place_buckets[day_index]
        day_restaurants = restaurant_buckets[day_index]
        morning = day_places[: max(1, len(day_places) // 2)]
        evening = day_places[max(1, len(day_places) // 2):]
        itinerary.append({"day": day_index + 1, "slots": {"Morning": morning, "Afternoon": day_restaurants, "Evening": evening}})
    return itinerary


def render_itinerary_as_text(destination, itinerary, hotels):
    lines = [f"{destination} Travel Plan", "=" * (len(destination) + 13), ""]
    if hotels:
        lines.append(f"Suggested stay: {hotels[0]['name']} ({hotels[0].get('address', '')})")
        lines.append("")
    for day in itinerary:
        lines.append(f"Day {day['day']}:")
        for slot in SLOTS:
            items = day["slots"].get(slot, [])
            if not items:
                continue
            names = ", ".join(item["name"] for item in items)
            lines.append(f"  {slot}: {names}")
        lines.append("")
    return "\n".join(lines)


def generate_llm_narrative(destination, days, itinerary, hotels, budget):
    plain_text = render_itinerary_as_text(destination, itinerary, hotels)
    if not Config.ANTHROPIC_API_KEY or anthropic is None:
        return plain_text
    try:
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        prompt = (
            f"Rewrite the following {days}-day travel itinerary for {destination} "
            f"(budget level: {budget}) as a warm, concise, day-by-day travel plan. "
            f"Keep all place names exactly as given. Use short paragraphs, no markdown tables.\n\n{plain_text}"
        )
        response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1200, messages=[{"role": "user", "content": prompt}])
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_blocks) if text_blocks else plain_text
    except Exception:
        return plain_text


# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="Smart Travel Planner", page_icon="🧭", layout="wide")

CATEGORY_COLORS = {
    "tourist_places": [26, 115, 232],
    "restaurants": [217, 48, 37],
    "hotels": [24, 128, 56],
    "adventure": [244, 160, 0],
    "shopping": [154, 24, 178],
    "nightlife": [95, 99, 104],
}


@st.cache_resource
def get_services():
    return PlacesService(), DirectionsService()


def run_pipeline(query: str) -> dict:
    places_service, directions_service = get_services()
    parsed = parse_travel_query(query)

    if parsed["intent"] != "plan_trip":
        raise ValueError("I couldn't detect a trip-planning request. Try: 'Plan a 3-day trip to Goa with beaches and seafood.'")
    if not parsed["destination"]:
        raise ValueError("I couldn't identify a destination. Try: 'Plan a trip to Jaipur for 4 days.'")

    destination, days, preferences, budget = parsed["destination"], parsed["days"], parsed["preferences"], parsed["budget"]

    geo = places_service.geocode_destination(destination)
    if not geo:
        raise ValueError(f"Couldn't find a location matching '{destination}'.")

    gathered = places_service.gather_all(destination, preferences, budget)
    attractions = gathered.get("tourist_places", [])
    restaurants = gathered.get("restaurants", [])
    hotels = gathered.get("hotels", [])

    if not attractions and not restaurants:
        raise ValueError(f"No places found for '{destination}'. Try a more specific destination.")

    start_point = hotels[0] if hotels else {"lat": geo["lat"], "lng": geo["lng"], "name": destination}
    ordered_attractions = directions_service.optimize_route(start_point, attractions) if attractions else []
    route_stats = (
        directions_service.total_route_stats(start_point, ordered_attractions)
        if ordered_attractions else {"total_distance_km": 0, "total_duration_min": 0}
    )

    itinerary = generate_rule_based_itinerary(destination, days, ordered_attractions, restaurants, hotels)
    narrative = generate_llm_narrative(destination, days, itinerary, hotels, budget)

    return {
        "destination": {"name": destination, "formatted_address": geo["formatted_address"], "lat": geo["lat"], "lng": geo["lng"]},
        "route_stats": route_stats,
        "itinerary": itinerary,
        "narrative": narrative,
        "map_markers": ordered_attractions + restaurants + hotels,
    }


def render_map(destination: dict, markers: list):
    if not markers:
        st.info("No map markers to display.")
        return
    df = pd.DataFrame(markers)
    df["color"] = df["category"].map(lambda c: CATEGORY_COLORS.get(c, [66, 133, 244]))
    layer = pdk.Layer("ScatterplotLayer", data=df, get_position="[lng, lat]", get_fill_color="color", get_radius=120, pickable=True)
    view_state = pdk.ViewState(latitude=destination["lat"], longitude=destination["lng"], zoom=12, pitch=0)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{name} ({category})"}))


def render_itinerary(itinerary: list):
    for day in itinerary:
        with st.expander(f"Day {day['day']}", expanded=True):
            for slot, items in day["slots"].items():
                if not items:
                    continue
                st.markdown(f"**{slot}**")
                for item in items:
                    rating = f" ⭐ {item['rating']}" if item.get("rating") else ""
                    st.markdown(f"- {item['name']}{rating}")


def main():
    st.title("🧭 Smart Travel Planner")
    st.caption("Describe your trip in plain English — NLP + OpenStreetMap handle the rest.")

    try:
        validate_config()
    except EnvironmentError as e:
        st.error(str(e))
        st.stop()

    query = st.text_area(
        "Your trip request",
        placeholder="e.g. Plan a 3-day trip to Bangalore. I want to visit famous tourist "
                    "places, eat at good restaurants, and stay in budget hotels.",
        height=100,
    )

    if st.button("Plan My Trip", type="primary"):
        if not query.strip():
            st.warning("Please describe your trip first.")
            st.stop()
        with st.spinner("Understanding your request and building your itinerary..."):
            try:
                result = run_pipeline(query)
            except ValueError as e:
                st.error(str(e)); st.stop()
            except RuntimeError as e:
                st.error(f"Map service error: {e}")
            except Exception as e:
                st.error(f"Something went wrong: {e}"); st.stop()
        st.session_state["result"] = result

    if "result" in st.session_state:
        result = st.session_state["result"]
        dest, stats = result["destination"], result["route_stats"]

        st.subheader(f"{dest['name']} — {len(result['itinerary'])}-Day Trip")
        st.caption(dest["formatted_address"])
        c1, c2 = st.columns(2)
        c1.metric("Estimated sightseeing distance", f"{stats['total_distance_km']} km")
        c2.metric("Estimated driving time", f"{stats['total_duration_min']} min")

        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("### Itinerary")
            render_itinerary(result["itinerary"])
            with st.expander("Full narrative"):
                st.text(result["narrative"])
        with col2:
            st.markdown("### Map")
            render_map(dest, result["map_markers"])


if __name__ == "__main__":
    main()
