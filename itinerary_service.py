"""
services/itinerary_service.py

Turns an optimized route (places, restaurants, hotels) into a day-wise itinerary.

If ANTHROPIC_API_KEY is configured, uses Claude to write a natural-language
itinerary. Otherwise falls back to a deterministic rule-based generator that
distributes places evenly across the requested number of days
(morning / afternoon / evening slots). The fallback guarantees the app works
end-to-end with zero paid LLM calls.
"""

import json
from config import Config

try:
    import anthropic
except ImportError:
    anthropic = None


SLOTS = ["Morning", "Afternoon", "Evening"]


def _chunk_round_robin(items: list, n_buckets: int) -> list[list]:
    """Distribute `items` across `n_buckets` as evenly as possible, preserving order."""
    buckets = [[] for _ in range(n_buckets)]
    for i, item in enumerate(items):
        buckets[i % n_buckets].append(item)
    return buckets


def generate_rule_based_itinerary(
    destination: str,
    days: int,
    ordered_places: list[dict],
    restaurants: list[dict],
    hotels: list[dict],
) -> list[dict]:
    """
    Builds a day-wise plan without any external LLM call.

    Returns:
        [
          {
            "day": 1,
            "slots": {
              "Morning": [{"name":.., "category":..}, ...],
              "Afternoon": [...],
              "Evening": [...]
            }
          }, ...
        ]
    """
    place_buckets = _chunk_round_robin(ordered_places, days)
    restaurant_buckets = _chunk_round_robin(restaurants, days)

    itinerary = []
    for day_index in range(days):
        day_places = place_buckets[day_index]
        day_restaurants = restaurant_buckets[day_index]

        # Spread that day's attractions across Morning/Evening, food across Afternoon
        morning = day_places[: max(1, len(day_places) // 2)]
        evening = day_places[max(1, len(day_places) // 2):]
        afternoon = day_restaurants

        itinerary.append({
            "day": day_index + 1,
            "slots": {
                "Morning": morning,
                "Afternoon": afternoon,
                "Evening": evening,
            },
        })

    return itinerary


def generate_llm_narrative(
    destination: str,
    days: int,
    itinerary: list[dict],
    hotels: list[dict],
    budget: str,
) -> str:
    """
    Optional: ask Claude to turn the structured itinerary into friendly prose.
    Requires ANTHROPIC_API_KEY. Falls back to a plain-text rendering on any failure.
    """
    plain_text = render_itinerary_as_text(destination, itinerary, hotels)

    if not Config.ANTHROPIC_API_KEY or anthropic is None:
        return plain_text

    try:
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        prompt = (
            f"Rewrite the following {days}-day travel itinerary for {destination} "
            f"(budget level: {budget}) as a warm, concise, day-by-day travel plan. "
            f"Keep all place names exactly as given. Use short paragraphs, no markdown tables.\n\n"
            f"{plain_text}"
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_blocks) if text_blocks else plain_text
    except Exception:
        # Never let an LLM outage break the app — fall back to the deterministic plan.
        return plain_text


def render_itinerary_as_text(destination: str, itinerary: list[dict], hotels: list[dict]) -> str:
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
