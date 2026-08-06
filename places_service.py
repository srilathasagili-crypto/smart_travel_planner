import requests
from geopy.geocoders import Nominatim


_QUERY_TAGS = {
    "tourist_places": ["tourism", "attraction"],
    "restaurants": ["amenity", "restaurant"],
    "hotels": ["tourism", "hotel"],
    "adventure": ["sport", "park"],
    "shopping": ["shop", "mall"],
    "nightlife": ["amenity", "bar"],
}


class PlacesService:

    def __init__(self):
        self.geolocator = Nominatim(
            user_agent="smart_travel_planner"
        )


    def geocode_destination(self, destination: str):

        try:
            location = self.geolocator.geocode(destination)

        except Exception as exc:
            raise RuntimeError(
                f"Geocoding failed: {exc}"
            )

        if not location:
            return None

        return {
            "formatted_address": location.address,
            "lat": location.latitude,
            "lng": location.longitude
        }


    def search_category(
        self,
        category: str,
        destination: str,
        budget: str = "mid-range",
        limit: int = 5
    ):

        location = self.geocode_destination(destination)

        if not location:
            return []


        lat = location["lat"]
        lng = location["lng"]


        tag_type, tag_value = _QUERY_TAGS.get(
            category,
            ["amenity", "restaurant"]
        )


        query = f"""
        [out:json];
        (
          node["{tag_type}"="{tag_value}"]
          (around:5000,{lat},{lng});

          way["{tag_type}"="{tag_value}"]
          (around:5000,{lat},{lng});
        );
        out center {limit};
        """


        url = "https://overpass-api.de/api/interpreter"


        response = requests.post(
            url,
            data=query,
            headers={
                "User-Agent": "smart-travel-planner"
            }
        )


        data = response.json()


        places = []


        for item in data.get("elements", [])[:limit]:

            tags = item.get("tags", {})


            latitude = (
                item.get("lat")
                or item.get("center", {}).get("lat")
            )

            longitude = (
                item.get("lon")
                or item.get("center", {}).get("lon")
            )


            places.append({

                "name": tags.get(
                    "name",
                    "Unknown place"
                ),

                "address": tags.get(
                    "addr:street",
                    destination
                ),

                "rating": None,

                "user_ratings_total": None,

                "lat": latitude,

                "lng": longitude,

                "category": category
            })


        return places



    def gather_all(
        self,
        destination: str,
        preferences: list[str],
        budget: str
    ):

        results = {}

        for category in preferences:

            results[category] = self.search_category(
                category,
                destination,
                budget
            )

        return results
