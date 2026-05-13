"""Porto public-dataset route-candidate baseline evaluation.

This script is intentionally separate from the OSM public GPS trace evaluation.
The OSM trace pipeline tests whether pseudo-history profiles can be built from
public movement signals. This Porto pipeline is the first step toward a
publishable same-data benchmark: it uses a recognized public trajectory dataset,
reconstructs an observed route, generates OSM route candidates for the same
origin/destination, and evaluates candidate ranking with NASR-style path metrics.

The Porto dataset does not contain natural-language route preferences. Prompt
and hybrid baselines are therefore reported as skipped unless a later experiment
adds explicitly labeled synthetic or collected preference text.
"""

import argparse
import ast
import csv
import json
import sys
from datetime import datetime, timezone
from math import asin, cos, exp, radians, sin, sqrt
from pathlib import Path
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

import networkx as nx
import numpy as np
import osmnx as ox


BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_ROOT))

from app.profile import build_dynamic_profile, get_request_context, score_routes_with_profile
from app.routing import compute_route_features, normalize_highway_tag


DEFAULT_PORTO_CSV = BACKEND_ROOT / "data" / "porto" / "train.csv"
JSON_OUTPUT_PATH = BACKEND_ROOT / "data" / "porto_candidate_baseline_comparison.json"
CSV_OUTPUT_PATH = BACKEND_ROOT / "data" / "porto_candidate_baseline_comparison.csv"

RANK_FEATURES = [
    "distance_km",
    "major_pct",
    "walk_pct",
    "residential_pct",
    "service_pct",
    "intersections",
    "turns",
    "park_near_pct",
    "safety_score",
    "lit_pct",
    "signal_cnt",
    "crossing_cnt",
    "tunnel_m",
]

PATH_MATCH_THRESHOLD_M = 50.0
NDTW_NORMALIZATION_M = 100.0
BASELINE_ORDER = [
    "oracle_feature_upper_bound",
    "oracle_path_upper_bound",
    "random",
    "shortest_distance",
    "profile",
    "vehicle_profile",
    "prompt_sbert",
    "hybrid",
]

VEHICLE_PROFILE_WEIGHTS = {
    "distance_km": 1.2,
    "major_pct": 0.9,
    "residential_pct": 0.8,
    "service_pct": 0.6,
    "intersections": 0.9,
    "turns": 1.1,
    "signal_cnt": 0.5,
    "tunnel_m": 0.2,
}

MAJOR_ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
RESIDENTIAL_ROADS = {"residential", "living_street", "unclassified"}
SERVICE_ROADS = {"service"}


def make_json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [make_json_safe(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_mean(values: Iterable[Any], default: Optional[float] = None) -> Optional[float]:
    clean = [float(v) for v in values if v is not None and np.isfinite(v)]
    if not clean:
        return default
    return float(np.mean(clean))


def haversine_m(a: List[float], b: List[float]) -> float:
    lat1, lon1 = radians(float(a[0])), radians(float(a[1]))
    lat2, lon2 = radians(float(b[0])), radians(float(b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371000.0 * 2 * asin(sqrt(h))


def path_length_km(coords: List[List[float]]) -> float:
    if len(coords) < 2:
        return 0.0
    return sum(haversine_m(a, b) for a, b in zip(coords[:-1], coords[1:])) / 1000.0


def min_distance_to_path_m(point: List[float], path: List[List[float]]) -> float:
    if not path:
        return float("inf")
    return min(haversine_m(point, other) for other in path)


def path_match_metrics(predicted: List[List[float]], reference: List[List[float]]) -> Dict[str, Optional[float]]:
    if not predicted or not reference:
        return {
            "path_precision": None,
            "path_recall": None,
            "path_f1": None,
            "path_ndtw": None,
            "path_edit_distance": None,
            "path_max_distance_m": None,
        }
    pred_to_ref = [min_distance_to_path_m(p, reference) for p in predicted]
    ref_to_pred = [min_distance_to_path_m(p, predicted) for p in reference]
    precision = float(np.mean([d <= PATH_MATCH_THRESHOLD_M for d in pred_to_ref]))
    recall = float(np.mean([d <= PATH_MATCH_THRESHOLD_M for d in ref_to_pred]))
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "path_precision": precision,
        "path_recall": recall,
        "path_f1": f1,
        "path_ndtw": normalized_dtw(predicted, reference),
        "path_edit_distance": coordinate_edit_distance(predicted, reference),
        "path_max_distance_m": float(max(max(pred_to_ref, default=0.0), max(ref_to_pred, default=0.0))),
    }


def normalized_dtw(path_a: List[List[float]], path_b: List[List[float]]) -> float:
    n, m = len(path_a), len(path_b)
    if n == 0 or m == 0:
        return 0.0
    dp = np.full((n + 1, m + 1), float("inf"))
    dp[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = haversine_m(path_a[i - 1], path_b[j - 1])
            dp[i, j] = cost + min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
    return float(exp(-dp[n, m] / (max(n, m) * NDTW_NORMALIZATION_M)))


def coordinate_edit_distance(path_a: List[List[float]], path_b: List[List[float]], decimals: int = 4) -> int:
    tokens_a = [(round(float(lat), decimals), round(float(lon), decimals)) for lat, lon in path_a]
    tokens_b = [(round(float(lat), decimals), round(float(lon), decimals)) for lat, lon in path_b]
    n, m = len(tokens_a), len(tokens_b)
    dp = np.zeros((n + 1, m + 1), dtype=int)
    dp[:, 0] = np.arange(n + 1)
    dp[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            substitution = 0 if tokens_a[i - 1] == tokens_b[j - 1] else 1
            dp[i, j] = min(dp[i - 1, j] + 1, dp[i, j - 1] + 1, dp[i - 1, j - 1] + substitution)
    return int(dp[n, m])


def feature_vec(features: Dict[str, Any]) -> np.ndarray:
    return np.array([safe_float(features.get(name, 0.0)) for name in RANK_FEATURES], dtype=float)


def minmax_matrix(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    mn = X.min(axis=0)
    mx = X.max(axis=0)
    denom = np.where(np.isclose(mx - mn, 0), 1.0, mx - mn)
    return (X - mn) / denom


def dcg_at_k(relevances: List[float], k: int) -> float:
    rel = np.asarray(relevances[:k], dtype=float)
    if len(rel) == 0:
        return 0.0
    discounts = np.log2(np.arange(2, len(rel) + 2))
    return float(np.sum(rel / discounts))


def ndcg_at_k(ranked_relevances: List[float], k: int) -> float:
    actual = dcg_at_k(ranked_relevances, k)
    ideal = dcg_at_k(sorted(ranked_relevances, reverse=True), k)
    return 0.0 if ideal == 0 else float(actual / ideal)


def minmax_scores(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    mn = values.min()
    mx = values.max()
    if np.isclose(mx, mn):
        return np.ones_like(values) * 0.5
    return (values - mn) / (mx - mn)


def ranking_from_scores(scores: np.ndarray) -> List[int]:
    return [int(idx) for idx in np.argsort(-np.asarray(scores, dtype=float))]


def vehicle_profile_scores(route_feature_dicts: List[Dict[str, Any]], profile: Dict[str, Any]) -> np.ndarray:
    """Score Porto driving candidates by closeness to contextual vehicle-history targets.

    The normal profile scorer was designed around walking comfort signals such
    as parks, footpaths, and crossings. Porto is a taxi dataset, so this baseline
    focuses on driving-relevant route shape and road-class exposure. It remains
    unsupervised: it only uses earlier trip features, not held-out labels.
    """
    avg = profile["avg_features"]
    matrix = []
    target = []
    weights = []
    for name, weight in VEHICLE_PROFILE_WEIGHTS.items():
        matrix.append([safe_float(route.get(name)) for route in route_feature_dicts])
        target.append(safe_float(avg.get(name)))
        weights.append(weight)
    X = np.asarray(matrix, dtype=float).T
    target_vec = np.asarray(target, dtype=float)
    weights_vec = np.asarray(weights, dtype=float)
    normalized = minmax_matrix(np.vstack([target_vec, X]))
    deltas = np.abs(normalized[1:] - normalized[0])
    penalties = np.sum(deltas * weights_vec, axis=1)

    # During rush hour, add a modest extra penalty for stop-heavy routes.
    context = profile.get("context", {})
    if context.get("rush_hour"):
        signal_norm = _series_minmax([r.get("signal_cnt", 0.0) for r in route_feature_dicts])
        intersection_norm = _series_minmax([r.get("intersections", 0.0) for r in route_feature_dicts])
        penalties += 0.25 * signal_norm + 0.20 * intersection_norm
    return minmax_scores(-penalties)


def _series_minmax(values: List[Any]) -> np.ndarray:
    return minmax_scores(np.array([safe_float(v) for v in values], dtype=float))


def route_to_coordinates(G: nx.MultiDiGraph, route: List[int]) -> List[List[float]]:
    return [[float(G.nodes[node]["y"]), float(G.nodes[node]["x"])] for node in route]


def parse_porto_polyline(polyline: str) -> List[List[float]]:
    raw = ast.literal_eval(polyline)
    coords = []
    for lon, lat in raw:
        coords.append([float(lat), float(lon)])
    return coords


def load_porto_rows(path: Path, max_rows_to_scan: int, min_points: int, sample_stride: int) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing Porto CSV at {path}. Download the public Porto Taxi Service Trajectory dataset "
            "from UCI or Figshare and place train.csv under data/porto/train.csv."
        )

    rows = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw_idx, row in enumerate(reader):
            if raw_idx >= max_rows_to_scan:
                break
            if raw_idx % max(sample_stride, 1) != 0:
                continue
            if str(row.get("MISSING_DATA", "")).lower() == "true":
                continue
            try:
                coords = parse_porto_polyline(row["POLYLINE"])
            except Exception:
                continue
            if len(coords) < min_points:
                continue
            rows.append({
                "trip_id": row.get("TRIP_ID", str(raw_idx)),
                "taxi_id": row.get("TAXI_ID", "unknown"),
                "timestamp": datetime.fromtimestamp(int(row["TIMESTAMP"]), tz=timezone.utc).isoformat()
                if row.get("TIMESTAMP")
                else None,
                "coordinates": coords,
            })
    return rows


def graph_for_trip(coords: List[List[float]], dist_meters: int) -> nx.MultiDiGraph:
    lats = [p[0] for p in coords]
    lons = [p[1] for p in coords]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))
    radius = max(dist_meters, int(max(haversine_m(center, p) for p in coords) + 1000))
    print(f"  Building Porto drive graph center={center} radius={radius}m")
    G = ox.graph_from_point(center, dist=radius, network_type="drive", simplify=True)
    G = ox.distance.add_edge_lengths(G)
    try:
        G = ox.bearing.add_edge_bearings(G)
    except Exception:
        try:
            G = ox.add_edge_bearings(G)
        except Exception:
            pass
    annotate_vehicle_candidate_weights(G)
    return G


def annotate_vehicle_candidate_weights(G: nx.MultiDiGraph) -> None:
    """Attach several deterministic driving weights for candidate diversity."""
    for _, v, _, data in G.edges(keys=True, data=True):
        length = safe_float(data.get("length"), 1.0) or 1.0
        hwy = normalize_highway_tag(data.get("highway"))
        degree = G.degree[v] if v in G.nodes else 2

        prefer_major = length
        if hwy in MAJOR_ROADS:
            prefer_major *= 0.82
        elif hwy in RESIDENTIAL_ROADS:
            prefer_major *= 1.05
        elif hwy in SERVICE_ROADS:
            prefer_major *= 1.18

        avoid_major = length
        if hwy in MAJOR_ROADS:
            avoid_major *= 1.25
        elif hwy in RESIDENTIAL_ROADS:
            avoid_major *= 0.95
        elif hwy in SERVICE_ROADS:
            avoid_major *= 1.08

        simple = length + max(degree - 2, 0) * 10.0
        if hwy in MAJOR_ROADS:
            simple *= 0.96
        if hwy in SERVICE_ROADS:
            simple *= 1.12

        avoid_local = length
        if hwy in RESIDENTIAL_ROADS:
            avoid_local *= 1.15
        if hwy in SERVICE_ROADS:
            avoid_local *= 1.30
        if hwy in MAJOR_ROADS:
            avoid_local *= 0.90

        data["vehicle_length"] = length
        data["vehicle_prefer_major"] = max(1.0, prefer_major)
        data["vehicle_avoid_major"] = max(1.0, avoid_major)
        data["vehicle_simple"] = max(1.0, simple)
        data["vehicle_avoid_local"] = max(1.0, avoid_local)


def simplify_trace_anchors(coords: List[List[float]], min_anchor_spacing_m: float, max_anchors: int) -> List[List[float]]:
    """Reduce dense/noisy GPS samples before shortest-path stitching.

    Stitching every sampled point can create zig-zag detours when GPS samples
    snap to alternating nearby streets. Keeping spatially separated anchors
    preserves the trip envelope while reducing overbuilt reconstructed paths.
    """
    if len(coords) <= 2 or min_anchor_spacing_m <= 0:
        return coords
    anchors = [coords[0]]
    for point in coords[1:-1]:
        if haversine_m(anchors[-1], point) >= min_anchor_spacing_m:
            anchors.append(point)
    if anchors[-1] != coords[-1]:
        anchors.append(coords[-1])
    if max_anchors > 1 and len(anchors) > max_anchors:
        indices = np.linspace(0, len(anchors) - 1, max_anchors, dtype=int)
        anchors = [anchors[int(i)] for i in indices]
    return anchors


def reconstruct_route(
    G: nx.MultiDiGraph,
    coords: List[List[float]],
    min_anchor_spacing_m: float,
    max_anchors: int,
) -> Tuple[Optional[List[int]], Dict[str, Any]]:
    anchor_coords = simplify_trace_anchors(coords, min_anchor_spacing_m, max_anchors)
    xs = [p[1] for p in anchor_coords]
    ys = [p[0] for p in anchor_coords]
    nodes = ox.distance.nearest_nodes(G, X=xs, Y=ys)
    deduped = []
    for node in nodes:
        node = int(node)
        if not deduped or deduped[-1] != node:
            deduped.append(node)
    diagnostics = {
        "raw_trace_points": len(coords),
        "anchor_points": len(anchor_coords),
        "anchor_reduction_ratio": len(anchor_coords) / max(len(coords), 1),
        "unique_anchor_nodes": len(deduped),
        "min_anchor_spacing_m": min_anchor_spacing_m,
        "max_anchors": max_anchors,
    }
    if len(deduped) < 2:
        return None, diagnostics
    route = []
    attempted_pairs = 0
    successful_pairs = 0
    for a, b in zip(deduped[:-1], deduped[1:]):
        attempted_pairs += 1
        try:
            path = nx.shortest_path(G, a, b, weight="length")
            successful_pairs += 1
        except Exception:
            continue
        if not route:
            route.extend(path)
        else:
            route.extend(path[1:])
    cleaned = []
    for node in route:
        if not cleaned or cleaned[-1] != node:
            cleaned.append(node)
    diagnostics.update({
        "attempted_anchor_pairs": attempted_pairs,
        "successful_anchor_pairs": successful_pairs,
        "anchor_pair_success_rate": successful_pairs / max(attempted_pairs, 1),
        "reconstructed_route_nodes": len(cleaned),
    })
    return (cleaned if len(cleaned) >= 2 else None), diagnostics


def generate_candidates(G: nx.MultiDiGraph, origin: List[float], destination: List[float], k_routes: int) -> List[List[int]]:
    orig = ox.distance.nearest_nodes(G, X=origin[1], Y=origin[0])
    dest = ox.distance.nearest_nodes(G, X=destination[1], Y=destination[0])
    routes = []
    weights = ["length", "vehicle_prefer_major", "vehicle_avoid_major", "vehicle_simple", "vehicle_avoid_local"]
    per_weight_k = max(2, min(k_routes, 4))
    for weight in weights:
        try:
            routes.extend(list(ox.k_shortest_paths(G, orig, dest, k=per_weight_k, weight=weight)))
        except Exception:
            try:
                routes.append(nx.shortest_path(G, orig, dest, weight=weight))
            except Exception:
                continue
    if not routes:
        routes = [nx.shortest_path(G, orig, dest, weight="length")]
    unique = []
    seen = set()
    for route in routes:
        key = tuple(route)
        if key not in seen:
            unique.append(route)
            seen.add(key)
    return unique[:k_routes]


def candidate_distances_and_relevances(observed_features: Dict[str, Any], candidate_features: List[Dict[str, Any]]) -> Dict[str, Any]:
    observed_vec = feature_vec(observed_features)
    candidate_vecs = np.vstack([feature_vec(c) for c in candidate_features])
    normalized = minmax_matrix(np.vstack([observed_vec, candidate_vecs]))
    distances = np.linalg.norm(normalized[1:] - normalized[0], axis=1)
    max_dist = max(float(np.max(distances)), 1e-9)
    return {
        "oracle_index": int(np.argmin(distances)),
        "feature_distances": [float(x) for x in distances],
        "relevances": [1.0 - float(d / max_dist) for d in distances],
    }


def path_oracle_info(candidate_features: List[Dict[str, Any]], reference_coords: List[List[float]]) -> Dict[str, Any]:
    metrics = [path_match_metrics(candidate["coordinates"], reference_coords) for candidate in candidate_features]
    # Prefer path F1, then NDTW, then smaller max distance when there is a tie.
    ranking = sorted(
        range(len(candidate_features)),
        key=lambda i: (
            safe_float(metrics[i].get("path_f1"), -1.0),
            safe_float(metrics[i].get("path_ndtw"), -1.0),
            -safe_float(metrics[i].get("path_max_distance_m"), float("inf")),
        ),
        reverse=True,
    )
    return {
        "oracle_index": int(ranking[0]),
        "ranking": [int(i) for i in ranking],
        "metrics": metrics,
        "relevances": [safe_float(m.get("path_f1"), 0.0) for m in metrics],
    }


def evaluate_ranking(
    method: str,
    ranked_indices: List[int],
    oracle_index: int,
    relevances: List[float],
    feature_distances: List[float],
    candidate_features: List[Dict[str, Any]],
    reference_coords: List[List[float]],
    trip: Dict[str, Any],
) -> Dict[str, Any]:
    oracle_rank = ranked_indices.index(oracle_index) + 1
    ranked_relevances = [relevances[i] for i in ranked_indices]
    top_index = ranked_indices[0]
    path_metrics = path_match_metrics(candidate_features[top_index]["coordinates"], reference_coords)
    return {
        "method": method,
        "trip_id": trip["trip_id"],
        "taxi_id": trip["taxi_id"],
        "timestamp": trip["timestamp"],
        "oracle_rank": oracle_rank,
        "hit_at_1": oracle_rank <= 1,
        "hit_at_3": oracle_rank <= 3,
        "reciprocal_rank": 1.0 / oracle_rank,
        "ndcg_at_3": ndcg_at_k(ranked_relevances, 3),
        "top1_feature_distance": feature_distances[top_index],
        "oracle_feature_distance": feature_distances[oracle_index],
        **path_metrics,
        "ranked_indices": ranked_indices,
    }


def evaluate_porto(
    trips: List[Dict[str, Any]],
    max_tests: int,
    min_history_records: int,
    dist_meters: int,
    k_routes: int,
    random_seed: int,
    min_anchor_spacing_m: float,
    max_anchors: int,
) -> Dict[str, Any]:
    usable_records = []
    per_query_results = []
    skipped = []

    for idx, trip in enumerate(trips):
        if len(per_query_results) >= max_tests:
            break
        print(f"\nProcessing Porto trip {idx}: {trip['trip_id']}")
        try:
            G = graph_for_trip(trip["coordinates"], dist_meters)
            observed_route, reconstruction_diag = reconstruct_route(
                G,
                trip["coordinates"],
                min_anchor_spacing_m=min_anchor_spacing_m,
                max_anchors=max_anchors,
            )
            if observed_route is None:
                skipped.append({"trip_id": trip["trip_id"], "reason": "map matching failed", **reconstruction_diag})
                continue
            observed_features = compute_route_features(G, ox.project_graph(G), None, observed_route)
            observed_features["raw_trace_distance_km"] = path_length_km(trip["coordinates"])
            observed_features["route_distance_ratio"] = observed_features["distance_km"] / max(
                observed_features["raw_trace_distance_km"], 0.001
            )
            record = {
                "timestamp": trip["timestamp"],
                "mode": "porto_taxi_public",
                "source": "porto_taxi_public_dataset",
                "taxi_id": trip["taxi_id"],
                "features": observed_features,
            }
            usable_records.append(record)
            if len(usable_records) <= min_history_records:
                continue

            train = usable_records[:-1]
            candidate_routes = generate_candidates(G, trip["coordinates"][0], trip["coordinates"][-1], k_routes)
            if not candidate_routes:
                skipped.append({"trip_id": trip["trip_id"], "reason": "no generated candidates"})
                continue
            candidate_features = [compute_route_features(G, ox.project_graph(G), None, route) for route in candidate_routes]
            sim = candidate_distances_and_relevances(observed_features, candidate_features)
            oracle_index = sim["oracle_index"]
            feature_distances = sim["feature_distances"]
            relevances = sim["relevances"]
            path_oracle = path_oracle_info(candidate_features, observed_features["coordinates"])

            query = {
                "trip_id": trip["trip_id"],
                "taxi_id": trip["taxi_id"],
                "timestamp": trip["timestamp"],
                "candidate_count": len(candidate_features),
                "oracle_candidate_index": oracle_index,
                "path_oracle_candidate_index": path_oracle["oracle_index"],
                "observed_route_distance_ratio": observed_features["route_distance_ratio"],
                "reconstruction": reconstruction_diag,
                "methods": {},
            }

            oracle_ranking = sorted(range(len(candidate_features)), key=lambda i: feature_distances[i])
            query["methods"]["oracle_feature_upper_bound"] = evaluate_ranking(
                "oracle_feature_upper_bound",
                oracle_ranking,
                oracle_index,
                relevances,
                feature_distances,
                candidate_features,
                observed_features["coordinates"],
                trip,
            )

            query["methods"]["oracle_path_upper_bound"] = evaluate_ranking(
                "oracle_path_upper_bound",
                path_oracle["ranking"],
                path_oracle["oracle_index"],
                path_oracle["relevances"],
                feature_distances,
                candidate_features,
                observed_features["coordinates"],
                trip,
            )

            rng = np.random.default_rng(random_seed + idx)
            random_ranking = [int(i) for i in rng.permutation(len(candidate_features))]
            query["methods"]["random"] = evaluate_ranking(
                "random", random_ranking, oracle_index, relevances, feature_distances, candidate_features, observed_features["coordinates"], trip
            )

            shortest_ranking = sorted(range(len(candidate_features)), key=lambda i: safe_float(candidate_features[i].get("distance_km")))
            query["methods"]["shortest_distance"] = evaluate_ranking(
                "shortest_distance",
                shortest_ranking,
                oracle_index,
                relevances,
                feature_distances,
                candidate_features,
                observed_features["coordinates"],
                trip,
            )

            try:
                context = get_request_context(trip["timestamp"])
                profile = build_dynamic_profile(train, context)
                profile_scores = score_routes_with_profile(candidate_features, profile)
                profile_ranking = ranking_from_scores(profile_scores)
                query["methods"]["profile"] = evaluate_ranking(
                    "profile",
                    profile_ranking,
                    oracle_index,
                    relevances,
                    feature_distances,
                    candidate_features,
                    observed_features["coordinates"],
                    trip,
                )
                query["methods"]["profile"]["scores"] = [float(x) for x in profile_scores]

                vehicle_scores = vehicle_profile_scores(candidate_features, profile)
                vehicle_ranking = ranking_from_scores(vehicle_scores)
                query["methods"]["vehicle_profile"] = evaluate_ranking(
                    "vehicle_profile",
                    vehicle_ranking,
                    oracle_index,
                    relevances,
                    feature_distances,
                    candidate_features,
                    observed_features["coordinates"],
                    trip,
                )
                query["methods"]["vehicle_profile"]["scores"] = [float(x) for x in vehicle_scores]
            except Exception as exc:
                skipped.append({"trip_id": trip["trip_id"], "reason": f"profile failed: {repr(exc)}"})

            per_query_results.append(query)
        except Exception as exc:
            skipped.append({"trip_id": trip["trip_id"], "reason": repr(exc)})

    return {
        "num_records_built": len(usable_records),
        "num_queries": len(per_query_results),
        "reconstruction_mode": {
            "min_anchor_spacing_m": min_anchor_spacing_m,
            "max_anchors": max_anchors,
        },
        "per_query_results": per_query_results,
        "skipped": skipped,
    }


SUMMARY_METRICS = [
    "hit_at_1",
    "hit_at_3",
    "mrr",
    "ndcg_at_3",
    "mean_feature_distance",
    "mean_path_f1",
    "mean_path_ndtw",
    "mean_path_edit_distance",
    "mean_path_max_distance_m",
]


def bootstrap_ci(values: List[Any], samples: int, seed: int) -> Tuple[Optional[float], Optional[float]]:
    clean = np.array([float(v) for v in values if v is not None and np.isfinite(v)], dtype=float)
    if len(clean) == 0:
        return None, None
    if len(clean) == 1 or samples <= 0:
        value = float(clean[0])
        return value, value
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=float)
    for i in range(samples):
        draw = rng.choice(clean, size=len(clean), replace=True)
        means[i] = float(np.mean(draw))
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarize_skip_reasons(skipped: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts = Counter(item.get("reason", "unknown") for item in skipped)
    return [{"reason": reason, "count": count} for reason, count in counts.most_common()]


def summarize_query_diagnostics(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    queries = evaluation["per_query_results"]
    ratios = [q.get("observed_route_distance_ratio") for q in queries]
    candidate_counts = [q.get("candidate_count") for q in queries]
    anchor_points = [q.get("reconstruction", {}).get("anchor_points") for q in queries]
    raw_points = [q.get("reconstruction", {}).get("raw_trace_points") for q in queries]
    anchor_reduction = [q.get("reconstruction", {}).get("anchor_reduction_ratio") for q in queries]
    high_ratio = [
        {
            "trip_id": q.get("trip_id"),
            "taxi_id": q.get("taxi_id"),
            "observed_route_distance_ratio": q.get("observed_route_distance_ratio"),
            "candidate_count": q.get("candidate_count"),
        }
        for q in queries
        if safe_float(q.get("observed_route_distance_ratio"), 0.0) > 2.0
    ]
    return {
        "mean_observed_route_distance_ratio": safe_mean(ratios, None),
        "median_observed_route_distance_ratio": float(np.median([r for r in ratios if r is not None])) if ratios else None,
        "mean_candidate_count": safe_mean(candidate_counts, None),
        "mean_raw_trace_points": safe_mean(raw_points, None),
        "mean_anchor_points": safe_mean(anchor_points, None),
        "mean_anchor_reduction_ratio": safe_mean(anchor_reduction, None),
        "high_route_distance_ratio_count": len(high_ratio),
        "high_route_distance_ratio_examples": high_ratio[:10],
        "skip_reason_counts": summarize_skip_reasons(evaluation["skipped"]),
    }


def summarize_results(evaluation: Dict[str, Any], bootstrap_samples: int, random_seed: int) -> List[Dict[str, Any]]:
    by_method: Dict[str, List[Dict[str, Any]]] = {}
    for query in evaluation["per_query_results"]:
        for method, result in query["methods"].items():
            by_method.setdefault(method, []).append(result)

    rows = []
    skipped_reasons = {
        "prompt_sbert": "Porto trajectories do not include natural-language preference text.",
        "hybrid": "Hybrid requires both profile history and natural-language preference text.",
        "vehicle_profile": "Vehicle profile scoring failed or no successful query results.",
    }
    for method in BASELINE_ORDER:
        results = by_method.get(method, [])
        metric_values = {
            "hit_at_1": [1.0 if r["hit_at_1"] else 0.0 for r in results],
            "hit_at_3": [1.0 if r["hit_at_3"] else 0.0 for r in results],
            "mrr": [r["reciprocal_rank"] for r in results],
            "ndcg_at_3": [r["ndcg_at_3"] for r in results],
            "mean_feature_distance": [r["top1_feature_distance"] for r in results],
            "mean_path_f1": [r["path_f1"] for r in results],
            "mean_path_ndtw": [r["path_ndtw"] for r in results],
            "mean_path_edit_distance": [r["path_edit_distance"] for r in results],
            "mean_path_max_distance_m": [r["path_max_distance_m"] for r in results],
        }
        row = {
            "method": method,
            "status": "ran" if results else "skipped",
            "skip_reason": None if results else skipped_reasons.get(method, "No successful query results."),
            "num_queries": len(results),
        }
        for metric in SUMMARY_METRICS:
            row[metric] = safe_mean(metric_values[metric], None)
            lo, hi = bootstrap_ci(metric_values[metric], bootstrap_samples, random_seed + len(rows) * 1000 + len(metric))
            row[f"{metric}_ci95_low"] = lo
            row[f"{metric}_ci95_high"] = hi
        rows.append(row)
    return rows


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "method",
        "status",
        "skip_reason",
        "num_queries",
    ]
    for metric in SUMMARY_METRICS:
        fieldnames.extend([metric, f"{metric}_ci95_low", f"{metric}_ci95_high"])
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_summary(rows: List[Dict[str, Any]]) -> None:
    print("\nPorto Candidate Baseline Comparison")
    print("=" * 120)
    print(f"{'method':<18} {'status':<8} {'n':>4} {'Hit@1':>8} {'Hit@3':>8} {'MRR':>8} {'NDCG@3':>8} {'PathF1':>8} {'NDTW':>8}")
    print("-" * 120)
    for row in rows:
        if row["status"] == "ran":
            print(
                f"{row['method']:<18} {row['status']:<8} {row['num_queries']:>4} "
                f"{row['hit_at_1']:>8.3f} {row['hit_at_3']:>8.3f} {row['mrr']:>8.3f} "
                f"{row['ndcg_at_3']:>8.3f} {row['mean_path_f1']:>8.3f} {row['mean_path_ndtw']:>8.3f}"
            )
        else:
            print(f"{row['method']:<18} {row['status']:<8} {row['num_queries']:>4}  {row['skip_reason']}")
    print("=" * 120)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate route-candidate baselines on the public Porto taxi trajectory dataset. "
            "This is the first step toward a NASR-style same-data benchmark."
        )
    )
    parser.add_argument("--porto-csv", type=Path, default=DEFAULT_PORTO_CSV)
    parser.add_argument("--json-output", type=Path, default=JSON_OUTPUT_PATH)
    parser.add_argument("--csv-output", type=Path, default=CSV_OUTPUT_PATH)
    parser.add_argument("--max-rows-to-scan", type=int, default=5000)
    parser.add_argument("--sample-stride", type=int, default=100)
    parser.add_argument("--min-points", type=int, default=20)
    parser.add_argument("--max-tests", type=int, default=10)
    parser.add_argument("--min-history-records", type=int, default=3)
    parser.add_argument("--dist-meters", type=int, default=2500)
    parser.add_argument("--k-routes", type=int, default=5)
    parser.add_argument("--random-seed", type=int, default=20260512)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument(
        "--min-anchor-spacing-m",
        type=float,
        default=0.0,
        help="Minimum spacing between GPS anchors used for reconstruction. 0 keeps all sampled points.",
    )
    parser.add_argument(
        "--max-anchors",
        type=int,
        default=80,
        help="Maximum GPS anchors used for reconstruction after spacing simplification.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        trips = load_porto_rows(args.porto_csv, args.max_rows_to_scan, args.min_points, args.sample_stride)
    except FileNotFoundError as exc:
        output = {
            "metadata": {
                "porto_csv": str(args.porto_csv),
                "evaluation_type": "porto_candidate_ranking",
                "status": "missing_dataset",
                "message": str(exc),
                "dataset_sources": [
                    "https://archive.ics.uci.edu/dataset/339/taxi%2Bservice%2Btrajectory%2Bprediction%2Bchallenge%2Becml%2Bpkdd%2B2015",
                    "https://figshare.com/articles/dataset/Porto_taxi_trajectories/12302165",
                ],
            },
            "summary": [],
            "per_query_results": [],
            "skipped": [],
        }
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(make_json_safe(output), indent=2), encoding="utf-8")
        write_csv([], args.csv_output)
        print(str(exc))
        print(f"Saved placeholder JSON: {args.json_output}")
        print(f"Saved placeholder CSV:  {args.csv_output}")
        return

    evaluation = evaluate_porto(
        trips=trips,
        max_tests=args.max_tests,
        min_history_records=args.min_history_records,
        dist_meters=args.dist_meters,
        k_routes=args.k_routes,
        random_seed=args.random_seed,
        min_anchor_spacing_m=args.min_anchor_spacing_m,
        max_anchors=args.max_anchors,
    )
    rows = summarize_results(evaluation, args.bootstrap_samples, args.random_seed)
    diagnostics = summarize_query_diagnostics(evaluation)
    output = {
        "metadata": {
            "porto_csv": str(args.porto_csv),
            "evaluation_type": "porto_candidate_ranking",
            "max_rows_to_scan": args.max_rows_to_scan,
            "sample_stride": args.sample_stride,
            "min_points": args.min_points,
            "max_tests": args.max_tests,
            "dist_meters": args.dist_meters,
            "k_routes": args.k_routes,
            "bootstrap_samples": args.bootstrap_samples,
            "min_anchor_spacing_m": args.min_anchor_spacing_m,
            "max_anchors": args.max_anchors,
            "path_match_threshold_m": PATH_MATCH_THRESHOLD_M,
            "note": (
                "This is a same-public-dataset benchmark scaffold for Porto taxi trajectories. "
                "It is closer to NASR-style route recovery than the OSM public trace pseudo-history experiment, "
                "but it still needs careful split matching and external baseline reproduction before claiming superiority."
            ),
        },
        "summary": rows,
        "diagnostics": diagnostics,
        **evaluation,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(make_json_safe(output), indent=2), encoding="utf-8")
    write_csv(rows, args.csv_output)
    print_summary(rows)
    print(f"\nRecords built: {evaluation['num_records_built']}")
    print(f"Successful queries: {evaluation['num_queries']}")
    print(
        "Reconstruction anchors: "
        f"mean_raw={diagnostics.get('mean_raw_trace_points'):.1f} "
        f"mean_anchor={diagnostics.get('mean_anchor_points'):.1f} "
        f"mean_ratio={diagnostics.get('mean_anchor_reduction_ratio'):.3f}"
    )
    print(f"Skipped trips: {len(evaluation['skipped'])}")
    if diagnostics["skip_reason_counts"]:
        print("Skip reasons:")
        for item in diagnostics["skip_reason_counts"]:
            print(f"  {item['count']:>3}  {item['reason']}")
    print(f"Saved JSON: {args.json_output}")
    print(f"Saved CSV:  {args.csv_output}")


if __name__ == "__main__":
    main()
