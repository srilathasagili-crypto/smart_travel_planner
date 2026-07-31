"""
services/directions_service.py

Uses the Google Distance Matrix API to compute pairwise travel distances/times
between a list of places, then applies a nearest-neighbor route optimization
(a lightweight TSP heuristic — good enough for a handful of daily stops).
"""

import googlemaps
from config import Config


class DirectionsService:
    def __init__(self, api_key: str = None):
        self.client = googlemaps.Client(key=api_key or Config.GOOGLE_MAPS_API_KEY)

    def distance_matrix(self, origins: list[dict], destinations: list[dict]) -> list[list[dict]]:
        """
        origins/destinations: list of {"lat":.., "lng":..}
        Returns a 2D matrix [i][j] = {"distance_m":.., "duration_s":..}
        """
        origin_coords = [f"{p['lat']},{p['lng']}" for p in origins]
        dest_coords = [f"{p['lat']},{p['lng']}" for p in destinations]

        try:
            response = self.client.distance_matrix(
                origins=origin_coords, destinations=dest_coords, mode="driving"
            )
        except Exception as exc:
            raise RuntimeError(f"Distance matrix request failed: {exc}") from exc

        matrix = []
        for row in response.get("rows", []):
            matrix_row = []
            for element in row.get("elements", []):
                if element.get("status") == "OK":
                    matrix_row.append({
                        "distance_m": element["distance"]["value"],
                        "duration_s": element["duration"]["value"],
                    })
                else:
                    matrix_row.append({"distance_m": None, "duration_s": None})
            matrix.append(matrix_row)
        return matrix

    def optimize_route(self, start: dict, stops: list[dict]) -> list[dict]:
        """
        Nearest-neighbor heuristic: starting from `start` (e.g. the hotel),
        repeatedly visit the nearest unvisited stop. Returns `stops` reordered.

        This keeps API usage light (one distance-matrix call) while still
        meaningfully shortening the total route compared to an arbitrary order.
        """
        if not stops:
            return []

        remaining = stops.copy()
        ordered = []
        current = start

        # Compute the full matrix once: current+remaining as origins/destinations
        all_points = [start] + stops
        matrix = self.distance_matrix(all_points, all_points)

        current_idx = 0  # index of `start` within all_points
        visited_idx = set()

        while remaining:
            best_idx = None
            best_distance = None
            for i, point in enumerate(all_points):
                if i == 0 or i in visited_idx or point not in remaining:
                    continue
                dist = matrix[current_idx][i]["distance_m"]
                if dist is None:
                    continue
                if best_distance is None or dist < best_distance:
                    best_distance = dist
                    best_idx = i

            if best_idx is None:
                # Fallback: no distance data, just append remaining in original order
                ordered.extend(remaining)
                break

            next_point = all_points[best_idx]
            ordered.append(next_point)
            remaining.remove(next_point)
            visited_idx.add(best_idx)
            current_idx = best_idx

        return ordered

    def total_route_stats(self, start: dict, ordered_stops: list[dict]) -> dict:
        """Sum distance/duration across the ordered route, start -> stop1 -> stop2 -> ..."""
        route = [start] + ordered_stops
        total_distance_m = 0
        total_duration_s = 0

        for i in range(len(route) - 1):
            leg = self.distance_matrix([route[i]], [route[i + 1]])
            element = leg[0][0]
            if element["distance_m"] is not None:
                total_distance_m += element["distance_m"]
                total_duration_s += element["duration_s"]

        return {
            "total_distance_km": round(total_distance_m / 1000, 1),
            "total_duration_min": round(total_duration_s / 60),
        }
