import unittest

import networkx as nx

from app.routing import (
    annotate_edge_generation_costs,
    estimate_edge_speed_kph,
    straight_line_distance_m,
)
from app.ranking import feature_preference_scores
from app.schemas import RankRoutesRequest


class RoutingModeTests(unittest.TestCase):
    def test_request_defaults_to_walking(self):
        request = RankRoutesRequest(origin="A", destination="B")
        self.assertEqual(request.travel_mode, "walking")

    def test_speed_parser_supports_kph_and_mph(self):
        self.assertEqual(estimate_edge_speed_kph({"maxspeed": "50"}), 50)
        self.assertAlmostEqual(
            estimate_edge_speed_kph({"maxspeed": "30 mph"}),
            48.2802,
            places=3,
        )

    def test_straight_line_distance_for_short_city_trip(self):
        distance = straight_line_distance_m((43.6629, -79.3957), (43.6535, -79.3839))
        self.assertGreater(distance, 1000)
        self.assertLess(distance, 2000)

    def test_driving_edges_receive_faster_time_costs(self):
        graph = nx.MultiDiGraph()
        projected = nx.MultiDiGraph()
        graph.add_edge(1, 2, key=0, length=1000, highway="residential")
        projected.add_edge(1, 2, key=0, length=1000, highway="residential")

        annotate_edge_generation_costs(graph, projected, None, travel_mode="walking")
        walking_seconds = graph.edges[1, 2, 0]["travel_time"]
        annotate_edge_generation_costs(graph, projected, None, travel_mode="driving")
        driving_seconds = graph.edges[1, 2, 0]["travel_time"]

        self.assertLess(driving_seconds, walking_seconds)
        self.assertGreater(graph.edges[1, 2, 0]["simple_weight"], 0)

    def test_avoid_highways_prefers_lower_major_road_exposure(self):
        scores = feature_preference_scores(
            [
                {"major_pct": 80, "residential_pct": 10},
                {"major_pct": 20, "residential_pct": 60},
            ],
            "Avoid highways and use calmer streets.",
        )
        self.assertGreater(scores[1], scores[0])


if __name__ == "__main__":
    unittest.main()
