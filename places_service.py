import requests
from geopy.geocoders import Nominatim


_QUERY_TAGS = {
    "tourist_places": [
        ("tourism", "attraction"),
        ("tourism", "museum"),
        ("historic", "monument")
    ],

    "restaurants": [
        ("amenity", "restaurant"),
        ("amenity", "cafe")
    ],

    "hotels": [
        ("tourism", "hotel"),
        ("tourism", "guest_house")
    ],

    "adventure": [
        ("sport", "park"),
        ("leisure", "park")
    ],

    "shopping": [
        ("shop", "mall"),
        ("shop", "marketplace")
    ],

    "nightlife": [
        ("amenity", "bar"),
        ("amenity", "pub")
    ]
}


class PlacesService:

    def __init__(self):

        self.geolocator = Nominatim(
            user_agent="smart_travel_planner"
        )


    # -----------------------------------------
    # Convert place name to latitude longitude
    # -----------------------------------------

    def geocode_destination(self, destination):

        try:

            location = self.geolocator.geocode(
                destination,
                timeout=10
            )

        except Exception as e:

            print("Geocoding error:", e)
            return None


        if not location:
            return None


        return {

            "formatted_address": location.address,

            "lat": location.latitude,

            "lng": location.longitude

        }



    # -----------------------------------------
    # Search places using OpenStreetMap
    # -----------------------------------------

    def search_category(
            self,
            category,
            destination,
            budget="mid-range",
            limit=5
    ):


        location = self.geocode_destination(
            destination
        )


        if not location:
            return []


        lat = location["lat"]
        lng = location["lng"]



        tags = _QUERY_TAGS.get(
            category,
            [("amenity", "restaurant")]
        )


        query_parts = []


        for tag_type, tag_value in tags:


            query_parts.append(
                f"""
                node["{tag_type}"="{tag_value}"]
                (around:5000,{lat},{lng});

                way["{tag_type}"="{tag_value}"]
                (around:5000,{lat},{lng});
                """
            )



        query = f"""

        [out:json];

        (
            {" ".join(query_parts)}
        );

        out center {limit};

        """



        url = (
            "https://overpass.kumi.systems/api/interpreter"
        )


        try:

            response = requests.post(

                url,

                data=query,

                headers={
                    "User-Agent":
                    "smart-travel-planner"
                },

                timeout=30

            )


            if response.status_code != 200:

                print(
                    "Overpass error:",
                    response.status_code
                )

                return []



            data = response.json()


        except Exception as e:

            print(
                "Overpass request failed:",
                e
            )

            return []



        places = []



        for item in data.get(
                "elements",
                []
        ):


            tags = item.get(
                "tags",
                {}
            )


            latitude = (

                item.get("lat")

                or

                item.get(
                    "center",
                    {}
                ).get("lat")

            )


            longitude = (

                item.get("lon")

                or

                item.get(
                    "center",
                    {}
                ).get("lon")

            )



            places.append({

                "name":
                    tags.get(
                        "name",
                        "Unknown Place"
                    ),


                "address":
                    tags.get(
                        "addr:street",
                        destination
                    ),


                "lat":
                    latitude,


                "lng":
                    longitude,


                "category":
                    category,


                "rating":
                    None

            })


        return places




    # -----------------------------------------
    # Get all required categories
    # -----------------------------------------

    def gather_all(
            self,
            destination,
            preferences,
            budget="mid-range"
    ):


        results = {}


        for category in preferences:


            results[category] = self.search_category(

                category,

                destination,

                budget

            )


        return results
