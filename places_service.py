import googlemaps
from config import Config

_QUERY_TEMPLATES = {
    "tourist_places": "top tourist attractions in {destination}",
    "restaurants": "best restaurants in {destination}",
    "hotels": "{budget} hotels in {destination}",
    "adventure": "adventure activities in {destination}",
    "shopping": "shopping markets in {destination}",
    "nightlife": "nightlife spots in {destination}",
}


class PlacesService:
    def __init__(self, api_key: str = None):
        self.client = googlemaps.Client(key=api_key or Config.GOOGLE_MAPS_API_KEY)

    def geocode_destination(self, destination: str) -> dict | None:
        """Resolve a destination name to lat/lng, used to anchor searches and the map."""
        try:
            results = self.client.geocode(destination)
        except Exception as exc:
            raise RuntimeError(f"Geocoding failed for '{destination}': {exc}") from exc

        if not results:
            return None

        location = results[0]["geometry"]["location"]
        return {
            "formatted_address": results[0]["formatted_address"],
            "lat": location["lat"],
            "lng": location["lng"],
        }

    def search_category(
        self, category: str, destination: str, budget: str = "mid-range", limit: int = None
    ) -> list[dict]:
        """
        Run a Google Places text search for one preference category
        (tourist_places / restaurants / hotels / adventure / shopping / nightlife).
        """
        limit = limit or Config.MAX_PLACES_PER_CATEGORY
        query_template = _QUERY_TEMPLATES.get(category)
        if not query_template:
            return []

        query = query_template.format(destination=destination, budget=budget)

        try:
            response = self.client.places(query=query)
        except Exception as exc:
            raise RuntimeError(f"Places search failed for '{query}': {exc}") from exc

        places = []
        for result in response.get("results", [])[:limit]:
            places.append({
                "name": result.get("name"),
                "address": result.get("formatted_address"),
                "rating": result.get("rating"),
                "user_ratings_total": result.get("user_ratings_total"),
                "place_id": result.get("place_id"),
                "lat": result["geometry"]["location"]["lat"],
                "lng": result["geometry"]["location"]["lng"],
                "category": category,
            })
        return places

    def gather_all(self, destination: str, preferences: list[str], budget: str) -> dict:
        """Fetch places for every requested preference category."""
        results = {}
        for category in preferences:
            results[category] = self.search_category(category, destination, budget)
        return results
