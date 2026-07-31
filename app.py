"""
app.py

Smart Travel Planner - Streamlit application.

Run locally:
    streamlit run app.py

Deploy on Streamlit Cloud:
    Point the app's "Main file path" to app.py, and set GOOGLE_MAPS_API_KEY
    (and optionally ANTHROPIC_API_KEY) under App settings -> Secrets.
"""

import pandas as pd
import pydeck as pdk
import streamlit as st

from config import Config, validate_config
from nlp.extractor import parse_travel_query
from services.places_service import PlacesService
from services.directions_service import DirectionsService
from services.itinerary_service import generate_rule_based_itinerary, generate_llm_narrative

st.set_page_config(page_title="Smart Travel Planner", page_icon="🧭", layout="wide")

CATEGORY_COLORS = {
    "tourist_places": [26, 115, 232],   # blue
    "restaurants": [217, 48, 37],       # red
    "hotels": [24, 128, 56],            # green
    "adventure": [244, 160, 0],         # orange
    "shopping": [154, 24, 178],         # purple
    "nightlife": [95, 99, 104],         # grey
}


@st.cache_resource
def get_services():
    return PlacesService(), DirectionsService()


def run_pipeline(query: str) -> dict:
    """Runs the full NLP -> Places -> Route optimization -> Itinerary pipeline."""
    places_service, directions_service = get_services()

    parsed = parse_travel_query(query)

    if parsed["intent"] != "plan_trip":
        raise ValueError(
            "I couldn't detect a trip-planning request in that message. "
            "Try something like: 'Plan a 3-day trip to Goa with beaches and seafood.'"
        )

    if not parsed["destination"]:
        raise ValueError(
            "I couldn't identify a destination. Please mention a city, e.g. "
            "'Plan a trip to Jaipur for 4 days.'"
        )

    destination = parsed["destination"]
    days = parsed["days"]
    preferences = parsed["preferences"]
    budget = parsed["budget"]

    geo = places_service.geocode_destination(destination)
    if not geo:
        raise ValueError(f"Couldn't find a location matching '{destination}'.")

    gathered = places_service.gather_all(destination, preferences, budget)
    attractions = gathered.get("tourist_places", [])
    restaurants = gathered.get("restaurants", [])
    hotels = gathered.get("hotels", [])

    if not attractions and not restaurants:
        raise ValueError(
            f"No places found for '{destination}'. Try a more specific or well-known destination."
        )

    start_point = hotels[0] if hotels else {"lat": geo["lat"], "lng": geo["lng"], "name": destination}

    ordered_attractions = directions_service.optimize_route(start_point, attractions) if attractions else []
    route_stats = (
        directions_service.total_route_stats(start_point, ordered_attractions)
        if ordered_attractions else {"total_distance_km": 0, "total_duration_min": 0}
    )

    itinerary = generate_rule_based_itinerary(destination, days, ordered_attractions, restaurants, hotels)
    narrative = generate_llm_narrative(destination, days, itinerary, hotels, budget)

    all_markers = ordered_attractions + restaurants + hotels

    return {
        "query_understood": parsed,
        "destination": {
            "name": destination,
            "formatted_address": geo["formatted_address"],
            "lat": geo["lat"],
            "lng": geo["lng"],
        },
        "route_stats": route_stats,
        "itinerary": itinerary,
        "narrative": narrative,
        "map_markers": all_markers,
    }


def render_map(destination: dict, markers: list[dict]):
    if not markers:
        st.info("No map markers to display.")
        return

    df = pd.DataFrame(markers)
    df["color"] = df["category"].map(lambda c: CATEGORY_COLORS.get(c, [66, 133, 244]))

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[lng, lat]",
        get_fill_color="color",
        get_radius=120,
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=destination["lat"], longitude=destination["lng"], zoom=12, pitch=0
    )

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "{name} ({category})"},
    ))

    legend = "  ".join(
        f":{'blue' if c=='tourist_places' else 'red' if c=='restaurants' else 'green' if c=='hotels' else 'orange'}[●] {c.replace('_',' ').title()}"
        for c in df["category"].unique()
    )
    st.caption(legend)


def render_itinerary(itinerary: list[dict]):
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
    st.caption("Describe your trip in plain English — NLP + Google Maps handle the rest.")

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
                st.error(str(e))
                st.stop()
            except RuntimeError as e:
                st.error(f"Google Maps API error: {e}")
                st.stop()
            except Exception as e:
                st.error(f"Something went wrong while generating your itinerary: {e}")
                st.stop()

        st.session_state["result"] = result

    if "result" in st.session_state:
        result = st.session_state["result"]
        dest = result["destination"]
        stats = result["route_stats"]

        st.subheader(f"{dest['name']} — {len(result['itinerary'])}-Day Trip")
        st.caption(dest["formatted_address"])
        st.metric("Estimated sightseeing distance", f"{stats['total_distance_km']} km")
        st.metric("Estimated driving time", f"{stats['total_duration_min']} min")

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
