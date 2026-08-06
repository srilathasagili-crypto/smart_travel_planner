import requests
from math import radians, sin, cos, sqrt, atan2


class DirectionsService:

    def __init__(self):
        pass

    def calculate_distance(self, point1, point2):
        """
        Calculate straight-line distance using Haversine formula
        """

        lat1, lon1 = point1["lat"], point1["lng"]
        lat2, lon2 = point2["lat"], point2["lng"]

        R = 6371  # Earth radius in km

        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)

        a = (
            sin(dlat / 2) ** 2
            + cos(radians(lat1))
            * cos(radians(lat2))
            * sin(dlon / 2) ** 2
        )

        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return round(R * c, 2)


    def distance_matrix(self, origins, destinations):

        matrix = []

        for origin in origins:

            row = []

            for destination in destinations:

                distance = self.calculate_distance(
                    origin,
                    destination
                )

                row.append({
                    "distance_m": distance * 1000,
                    "duration_s": (distance / 40) * 3600
                })

            matrix.append(row)

        return matrix


    def optimize_route(self, start, stops):

        if not stops:
            return []

        remaining = stops.copy()
        ordered = []

        current = start

        while remaining:

            nearest = min(
                remaining,
                key=lambda x: self.calculate_distance(
                    current,
                    x
                )
            )

            ordered.append(nearest)
            remaining.remove(nearest)
            current = nearest

        return ordered


    def total_route_stats(self, start, ordered_stops):

        route = [start] + ordered_stops

        total_distance = 0

        for i in range(len(route)-1):

            total_distance += self.calculate_distance(
                route[i],
                route[i+1]
            )


        return {
            "total_distance_km": round(total_distance,1),
            "total_duration_min": round(
                (total_distance / 40) * 60
            )
        }
