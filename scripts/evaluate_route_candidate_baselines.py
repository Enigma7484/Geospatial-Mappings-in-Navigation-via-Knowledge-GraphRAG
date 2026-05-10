import argparse
import csv
import json
import sys
from datetime import datetime
from math import asin, cos, exp, radians, sin, sqrt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_ROOT))

from app.profile import build_dynamic_profile, get_request_context, score_routes_with_profile
from app.routing import generate_rankable_routes


HISTORY_PATH = BACKEND_ROOT / "data" / "user_histories_osm_trace.json"
JSON_OUTPUT_PATH = BACKEND_ROOT / "data" / "route_candidate_baseline_comparison.json"
CSV_OUTPUT_PATH = BACKEND_ROOT / "data" / "route_candidate_baseline_comparison.csv"

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

BASELINE_DESCRIPTIONS = {
    "random": "Randomly permutes generated OSM route candidates; deterministic seed for reproducibility.",
    "shortest_distance": "Ranks generated candidates by shortest OSM route distance.",
    "profile": "Builds a dynamic profile from earlier pseudo-history records and scores generated candidates.",
    "prompt_sbert": "Ranks generated route summaries by semantic similarity to preference text using SBERT.",
    "hybrid": "Combines profile and prompt/SBERT scores using the backend's 0.75/0.25 weighting.",
}

PATH_MATCH_THRESHOLD_M = 30.0
NDTW_NORMALIZATION_M = 50.0


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


def safe_mean(values: List[float], default: Optional[float] = None) -> Optional[float]:
    clean = [float(v) for v in values if v is not None and np.isfinite(v)]
    if not clean:
        return default
    return float(np.mean(clean))


def safe_median(values: List[float], default: Optional[float] = None) -> Optional[float]:
    clean = [float(v) for v in values if v is not None and np.isfinite(v)]
    if not clean:
        return default
    return float(np.median(clean))


def minmax_matrix(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    mn = X.min(axis=0)
    mx = X.max(axis=0)
    denom = np.where(np.isclose(mx - mn, 0), 1.0, mx - mn)
    return (X - mn) / denom


def minmax_scores(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    mn = values.min()
    mx = values.max()
    if np.isclose(mx, mn):
        return np.ones_like(values) * 0.5
    return (values - mn) / (mx - mn)


def feature_vec(features: Dict[str, Any]) -> np.ndarray:
    return np.array([safe_float(features.get(name, 0.0)) for name in RANK_FEATURES], dtype=float)


def haversine_m(a: List[float], b: List[float]) -> float:
    lat1, lon1 = radians(float(a[0])), radians(float(a[1]))
    lat2, lon2 = radians(float(b[0])), radians(float(b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371000.0 * 2 * asin(sqrt(h))


def min_distance_to_path_m(point: List[float], path: List[List[float]]) -> float:
    if not path:
        return float("inf")
    return min(haversine_m(point, other) for other in path)


def path_match_metrics(
    predicted_coords: Optional[List[List[float]]],
    reference_coords: Optional[List[List[float]]],
    threshold_m: float = PATH_MATCH_THRESHOLD_M,
) -> Dict[str, Optional[float]]:
    """Approximate NASR/RICK-style path similarity against a reference geometry."""
    if not predicted_coords or not reference_coords:
        return {
            "path_precision": None,
            "path_recall": None,
            "path_f1": None,
            "path_max_distance_m": None,
            "path_ndtw": None,
            "path_edit_distance": None,
            "path_length_ratio_to_reference": None,
        }

    pred_to_ref = [min_distance_to_path_m(p, reference_coords) for p in predicted_coords]
    ref_to_pred = [min_distance_to_path_m(p, predicted_coords) for p in reference_coords]
    precision = float(np.mean([d <= threshold_m for d in pred_to_ref]))
    recall = float(np.mean([d <= threshold_m for d in ref_to_pred]))
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    max_distance = max(max(pred_to_ref, default=0.0), max(ref_to_pred, default=0.0))
    ndtw = normalized_dtw(predicted_coords, reference_coords)
    edit_distance = coordinate_edit_distance(predicted_coords, reference_coords)

    pred_len = polyline_length_km(predicted_coords)
    reference_len = polyline_length_km(reference_coords)
    length_ratio = pred_len / reference_len if reference_len > 0 else None

    return {
        "path_precision": precision,
        "path_recall": recall,
        "path_f1": f1,
        "path_max_distance_m": float(max_distance),
        "path_ndtw": ndtw,
        "path_edit_distance": edit_distance,
        "path_length_ratio_to_reference": length_ratio,
    }


def normalized_dtw(path_a: List[List[float]], path_b: List[List[float]]) -> float:
    if not path_a or not path_b:
        return 0.0
    n, m = len(path_a), len(path_b)
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
            dp[i, j] = min(
                dp[i - 1, j] + 1,
                dp[i, j - 1] + 1,
                dp[i - 1, j - 1] + substitution,
            )
    return int(dp[n, m])


def polyline_length_km(coords: List[List[float]]) -> float:
    if not coords or len(coords) < 2:
        return 0.0
    return float(sum(haversine_m(a, b) for a, b in zip(coords[:-1], coords[1:])) / 1000.0)


def dcg_at_k(relevances: List[float], k: int) -> float:
    rel = np.asarray(relevances[:k], dtype=float)
    if len(rel) == 0:
        return 0.0
    discounts = np.log2(np.arange(2, len(rel) + 2))
    return float(np.sum(rel / discounts))


def ndcg_at_k(ranked_relevances: List[float], k: int) -> float:
    actual = dcg_at_k(ranked_relevances, k)
    ideal = dcg_at_k(sorted(ranked_relevances, reverse=True), k)
    if ideal == 0:
        return 0.0
    return float(actual / ideal)


def load_histories(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing OSM pseudo-history file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {user_id: records for user_id, records in data.items() if isinstance(records, list)}


def preference_text_for_record(record: Dict[str, Any]) -> Optional[str]:
    for key in ("preference", "preference_text", "user_preference", "prompt"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def preference_source_for_record(record: Dict[str, Any]) -> Optional[str]:
    source = record.get("preference_source")
    if isinstance(source, str) and source.strip():
        return source.strip()
    if preference_text_for_record(record):
        return "unknown"
    return None


def observed_route_coordinates(record: Dict[str, Any]) -> Optional[List[List[float]]]:
    coords = record.get("reconstructed_route_coordinates")
    if isinstance(coords, list) and coords:
        return coords
    features = record.get("features") or {}
    coords = features.get("coordinates")
    if isinstance(coords, list) and coords:
        return coords
    return None


def route_text_from_features(features: Dict[str, Any]) -> str:
    if features.get("summary"):
        return str(features["summary"])
    return (
        f"Walking route of {safe_float(features.get('distance_km')):.2f} km. "
        f"{safe_float(features.get('walk_pct')):.1f}% walking ways, "
        f"{safe_float(features.get('residential_pct')):.1f}% residential streets, "
        f"{safe_float(features.get('service_pct')):.1f}% service roads, "
        f"{safe_float(features.get('major_pct')):.1f}% major roads, "
        f"{int(safe_float(features.get('intersections')))} intersections, "
        f"{int(safe_float(features.get('turns')))} turns, "
        f"{safe_float(features.get('park_near_pct')):.1f}% near parks, "
        f"safety proxy {safe_float(features.get('safety_score')):.1f}/100."
    )


def ranking_from_scores(scores: np.ndarray) -> List[int]:
    return [int(idx) for idx in np.argsort(-np.asarray(scores, dtype=float))]


def origin_destination_for_record(record: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, float]]:
    origin = record.get("origin") or {}
    destination = record.get("destination") or {}
    return (
        {"lat": safe_float(origin.get("lat")), "lon": safe_float(origin.get("lon"))},
        {"lat": safe_float(destination.get("lat")), "lon": safe_float(destination.get("lon"))},
    )


def candidate_distances_and_relevances(
    observed_features: Dict[str, Any],
    candidate_features: List[Dict[str, Any]],
) -> Dict[str, Any]:
    observed_vec = feature_vec(observed_features)
    candidate_vecs = np.vstack([feature_vec(c) for c in candidate_features])
    normalized = minmax_matrix(np.vstack([observed_vec, candidate_vecs]))
    observed_norm = normalized[0]
    candidate_norm = normalized[1:]
    distances = np.linalg.norm(candidate_norm - observed_norm, axis=1)
    max_dist = max(float(np.max(distances)), 1e-9)
    relevances = [1.0 - float(d / max_dist) for d in distances]
    oracle_index = int(np.argmin(distances))
    return {
        "oracle_index": oracle_index,
        "feature_distances": [float(x) for x in distances],
        "relevances": relevances,
    }


def evaluate_ranking(
    method: str,
    ranked_indices: List[int],
    oracle_index: int,
    relevances: List[float],
    feature_distances: List[float],
    candidate_features: List[Dict[str, Any]],
    path_reference_coords: Optional[List[List[float]]],
    path_reference_type: str,
    user_id: str,
    test_index: int,
    timestamp: str,
) -> Dict[str, Any]:
    oracle_rank = ranked_indices.index(oracle_index) + 1
    ranked_relevances = [relevances[i] for i in ranked_indices]
    top_index = ranked_indices[0]
    path_metrics = path_match_metrics(
        candidate_features[top_index].get("coordinates"),
        path_reference_coords,
    )
    return {
        "method": method,
        "user_id": user_id,
        "test_index": test_index,
        "timestamp": timestamp,
        "oracle_candidate_index": oracle_index,
        "oracle_rank": oracle_rank,
        "hit_at_1": oracle_rank <= 1,
        "hit_at_3": oracle_rank <= 3,
        "reciprocal_rank": 1.0 / oracle_rank,
        "ndcg_at_3": ndcg_at_k(ranked_relevances, 3),
        "top1_feature_distance": feature_distances[top_index],
        "oracle_feature_distance": feature_distances[oracle_index],
        "path_reference_type": path_reference_type,
        **path_metrics,
        "ranked_indices": ranked_indices,
        "ranked_relevances": ranked_relevances,
        "ranked_feature_distances": [feature_distances[i] for i in ranked_indices],
    }


def add_skip(skipped: Dict[str, List[str]], key: str, reason: str) -> None:
    skipped.setdefault(key, [])
    if reason not in skipped[key]:
        skipped[key].append(reason)


def generate_candidates_for_record(
    record: Dict[str, Any],
    dist_meters: int,
    k_routes: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    origin, destination = origin_destination_for_record(record)
    return generate_rankable_routes(
        origin=origin,
        destination=destination,
        dist_meters=dist_meters,
        k_routes=k_routes,
    )


def evaluate_histories(
    histories: Dict[str, List[Dict[str, Any]]],
    min_history_records: int,
    max_tests: Optional[int],
    dist_meters: int,
    k_routes: int,
    random_seed: int,
) -> Dict[str, Any]:
    per_query_results = []
    skipped: Dict[str, List[str]] = {}
    attempted_records = 0

    for user_id, records in histories.items():
        usable_records = [r for r in records if isinstance(r.get("features"), dict)]
        if len(usable_records) <= min_history_records:
            add_skip(
                skipped,
                "all",
                f"{user_id} has {len(usable_records)} usable records; need more than {min_history_records}.",
            )
            continue

        test_indices = list(range(min_history_records, len(usable_records)))
        if max_tests is not None:
            test_indices = test_indices[:max_tests]

        for test_index in test_indices:
            attempted_records += 1
            train = usable_records[:test_index]
            heldout = usable_records[test_index]
            timestamp = heldout.get("timestamp")
            if not timestamp:
                add_skip(skipped, "record", f"{user_id} index {test_index}: missing timestamp.")
                continue

            try:
                candidate_features, route_texts = generate_candidates_for_record(
                    heldout,
                    dist_meters=dist_meters,
                    k_routes=k_routes,
                )
            except Exception as exc:
                add_skip(skipped, "route_generation", f"{user_id} index {test_index}: {repr(exc)}")
                continue

            if not candidate_features:
                add_skip(skipped, "route_generation", f"{user_id} index {test_index}: no candidate routes generated.")
                continue

            sim = candidate_distances_and_relevances(heldout["features"], candidate_features)
            oracle_index = sim["oracle_index"]
            feature_distances = sim["feature_distances"]
            relevances = sim["relevances"]
            path_reference_coords = observed_route_coordinates(heldout)
            path_reference_type = "heldout_reconstructed_route"
            if not path_reference_coords:
                path_reference_coords = candidate_features[oracle_index].get("coordinates")
                path_reference_type = "generated_oracle_candidate_fallback"

            query_result = {
                "user_id": user_id,
                "test_index": test_index,
                "timestamp": timestamp,
                "origin": heldout.get("origin"),
                "destination": heldout.get("destination"),
                "candidate_count": len(candidate_features),
                "oracle_candidate_index": oracle_index,
                "oracle_feature_distance": feature_distances[oracle_index],
                "observed_gps_to_route_median_m": heldout["features"].get("gps_to_route_median_m"),
                "observed_gps_to_route_mean_m": heldout["features"].get("gps_to_route_mean_m"),
                "observed_route_distance_ratio": heldout["features"].get("route_distance_ratio"),
                "observed_raw_trace_distance_km": heldout["features"].get("raw_trace_distance_km"),
                "observed_reconstructed_coordinate_count": len(path_reference_coords or []),
                "path_reference_type": path_reference_type,
                "candidate_distances_to_observed": feature_distances,
                "candidate_relevances": relevances,
                "candidate_summaries": [c.get("summary") for c in candidate_features],
                "methods": {},
            }

            # Baseline 1: random ranking over generated route candidates.
            rng = np.random.default_rng(random_seed + test_index)
            random_ranking = [int(i) for i in rng.permutation(len(candidate_features))]
            query_result["methods"]["random"] = evaluate_ranking(
                "random",
                random_ranking,
                oracle_index,
                relevances,
                feature_distances,
                candidate_features,
                path_reference_coords,
                path_reference_type,
                user_id,
                test_index,
                timestamp,
            )

            # Baseline 2: shortest-distance ranking over generated route candidates.
            shortest_ranking = sorted(
                range(len(candidate_features)),
                key=lambda i: safe_float(candidate_features[i].get("distance_km"), float("inf")),
            )
            query_result["methods"]["shortest_distance"] = evaluate_ranking(
                "shortest_distance",
                shortest_ranking,
                oracle_index,
                relevances,
                feature_distances,
                candidate_features,
                path_reference_coords,
                path_reference_type,
                user_id,
                test_index,
                timestamp,
            )

            profile_scores = None
            try:
                context = get_request_context(timestamp)
                profile = build_dynamic_profile(train, context)
                profile_scores = score_routes_with_profile(candidate_features, profile)
                profile_ranking = ranking_from_scores(profile_scores)
                query_result["methods"]["profile"] = evaluate_ranking(
                    "profile",
                    profile_ranking,
                    oracle_index,
                    relevances,
                    feature_distances,
                    candidate_features,
                    path_reference_coords,
                    path_reference_type,
                    user_id,
                    test_index,
                    timestamp,
                )
                query_result["methods"]["profile"]["scores"] = [float(x) for x in profile_scores]
            except Exception as exc:
                add_skip(skipped, "profile", f"{user_id} index {test_index}: {repr(exc)}")

            preference = preference_text_for_record(heldout)
            preference_source = preference_source_for_record(heldout)
            sbert_scores = None
            if not preference:
                add_skip(skipped, "prompt_sbert", "No preference text found in OSM pseudo-history records.")
            else:
                try:
                    from app.ranking import rank_route_texts

                    texts = route_texts or [route_text_from_features(f) for f in candidate_features]
                    sbert_scores = minmax_scores(np.asarray(rank_route_texts(texts, preference), dtype=float))
                    sbert_ranking = ranking_from_scores(sbert_scores)
                    query_result["methods"]["prompt_sbert"] = evaluate_ranking(
                        "prompt_sbert",
                        sbert_ranking,
                        oracle_index,
                        relevances,
                        feature_distances,
                        candidate_features,
                        path_reference_coords,
                        path_reference_type,
                        user_id,
                        test_index,
                        timestamp,
                    )
                    query_result["methods"]["prompt_sbert"]["scores"] = [float(x) for x in sbert_scores]
                    query_result["methods"]["prompt_sbert"]["preference"] = preference
                    query_result["methods"]["prompt_sbert"]["preference_source"] = preference_source
                except Exception as exc:
                    add_skip(skipped, "prompt_sbert", f"{user_id} index {test_index}: {repr(exc)}")

            if profile_scores is None:
                add_skip(skipped, "hybrid", "Profile scores unavailable for at least one query.")
            elif sbert_scores is None:
                add_skip(skipped, "hybrid", "No prompt/SBERT scores available because preference text is missing or SBERT failed.")
            else:
                hybrid_scores = 0.75 * np.asarray(profile_scores, dtype=float) + 0.25 * np.asarray(sbert_scores, dtype=float)
                hybrid_ranking = ranking_from_scores(hybrid_scores)
                query_result["methods"]["hybrid"] = evaluate_ranking(
                    "hybrid",
                    hybrid_ranking,
                    oracle_index,
                    relevances,
                    feature_distances,
                    candidate_features,
                    path_reference_coords,
                    path_reference_type,
                    user_id,
                    test_index,
                    timestamp,
                )
                query_result["methods"]["hybrid"]["scores"] = [float(x) for x in hybrid_scores]

            per_query_results.append(query_result)

    return {
        "attempted_records": attempted_records,
        "num_queries": len(per_query_results),
        "per_query_results": per_query_results,
        "skipped": skipped,
    }


def summarize_results(evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_method: Dict[str, List[Dict[str, Any]]] = {}
    for query in evaluation["per_query_results"]:
        for method, result in query["methods"].items():
            by_method.setdefault(method, []).append(result)

    rows = []
    for method in ["random", "shortest_distance", "profile", "prompt_sbert", "hybrid"]:
        results = by_method.get(method, [])
        if results:
            rows.append({
                "method": method,
                "status": "ran",
                "num_queries": len(results),
                "hit_at_1": safe_mean([1.0 if r["hit_at_1"] else 0.0 for r in results], 0.0),
                "hit_at_3": safe_mean([1.0 if r["hit_at_3"] else 0.0 for r in results], 0.0),
                "mrr": safe_mean([r["reciprocal_rank"] for r in results], 0.0),
                "ndcg_at_3": safe_mean([r["ndcg_at_3"] for r in results], 0.0),
                "mean_feature_distance": safe_mean([r["top1_feature_distance"] for r in results], 0.0),
                "mean_path_precision": safe_mean([r["path_precision"] for r in results], None),
                "mean_path_recall": safe_mean([r["path_recall"] for r in results], None),
                "mean_path_f1": safe_mean([r["path_f1"] for r in results], None),
                "mean_path_ndtw": safe_mean([r["path_ndtw"] for r in results], None),
                "mean_path_edit_distance": safe_mean([r["path_edit_distance"] for r in results], None),
                "mean_path_max_distance_m": safe_mean([r["path_max_distance_m"] for r in results], None),
                "mean_path_length_ratio_to_reference": safe_mean(
                    [r["path_length_ratio_to_reference"] for r in results], None
                ),
                "skip_reason": "",
                "description": BASELINE_DESCRIPTIONS[method],
            })
        else:
            reasons = evaluation["skipped"].get(method, ["No valid queries for this baseline."])
            rows.append({
                "method": method,
                "status": "skipped",
                "num_queries": 0,
                "hit_at_1": None,
                "hit_at_3": None,
                "mrr": None,
                "ndcg_at_3": None,
                "mean_feature_distance": None,
                "mean_path_precision": None,
                "mean_path_recall": None,
                "mean_path_f1": None,
                "mean_path_ndtw": None,
                "mean_path_edit_distance": None,
                "mean_path_max_distance_m": None,
                "mean_path_length_ratio_to_reference": None,
                "skip_reason": " | ".join(reasons),
                "description": BASELINE_DESCRIPTIONS[method],
            })
    return rows


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "method",
        "status",
        "num_queries",
        "hit_at_1",
        "hit_at_3",
        "mrr",
        "ndcg_at_3",
        "mean_feature_distance",
        "mean_path_precision",
        "mean_path_recall",
        "mean_path_f1",
        "mean_path_ndtw",
        "mean_path_edit_distance",
        "mean_path_max_distance_m",
        "mean_path_length_ratio_to_reference",
        "skip_reason",
        "description",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_summary_table(rows: List[Dict[str, Any]]) -> None:
    print("\nRoute-Candidate Baseline Comparison")
    print("=" * 132)
    print(
        f"{'method':<18} {'status':<8} {'n':>3} {'Hit@1':>8} {'Hit@3':>8} "
        f"{'MRR':>8} {'NDCG@3':>8} {'FeatDist':>9} {'PathF1':>8} {'NDTW':>8} {'EditD':>8} {'MaxM':>8}"
    )
    print("-" * 132)
    for row in rows:
        if row["status"] == "ran":
            print(
                f"{row['method']:<18} {row['status']:<8} {row['num_queries']:>3} "
                f"{row['hit_at_1']:>8.3f} {row['hit_at_3']:>8.3f} "
                f"{row['mrr']:>8.3f} {row['ndcg_at_3']:>8.3f} "
                f"{row['mean_feature_distance']:>9.3f} "
                f"{row['mean_path_f1']:>8.3f} {row['mean_path_ndtw']:>8.3f} "
                f"{row['mean_path_edit_distance']:>8.1f} {row['mean_path_max_distance_m']:>8.1f}"
            )
        else:
            print(
                f"{row['method']:<18} {row['status']:<8} {row['num_queries']:>3} "
                f"{'-':>8} {'-':>8} {'-':>8} {'-':>8} {'-':>9} {'-':>8} {'-':>8} {'-':>8} {'-':>8}"
            )
            print(f"  reason: {row['skip_reason']}")
    print("=" * 132)


def summarize_observed_reconstruction(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    queries = evaluation["per_query_results"]
    return {
        "num_queries": len(queries),
        "mean_observed_gps_to_route_median_m": safe_mean(
            [q.get("observed_gps_to_route_median_m") for q in queries], None
        ),
        "median_observed_gps_to_route_median_m": safe_median(
            [q.get("observed_gps_to_route_median_m") for q in queries], None
        ),
        "mean_observed_route_distance_ratio": safe_mean(
            [q.get("observed_route_distance_ratio") for q in queries], None
        ),
        "median_observed_route_distance_ratio": safe_median(
            [q.get("observed_route_distance_ratio") for q in queries], None
        ),
        "path_reference_types": sorted({q.get("path_reference_type") for q in queries if q.get("path_reference_type")}),
        "note": (
            "These diagnostics come from the held-out OSM pseudo-history reconstruction. "
            "Path-overlap metrics compare each method's top generated candidate to the held-out reconstructed route "
            "when reconstructed coordinates are present. Older history files fall back to the generated oracle candidate."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate ranking baselines over generated OSM route candidates. "
            "This complements scripts/evaluate_baselines.py, which ranks held-out history records "
            "against previous history records as a weaker sanity check."
        )
    )
    parser.add_argument("--history-path", type=Path, default=HISTORY_PATH)
    parser.add_argument("--json-output", type=Path, default=JSON_OUTPUT_PATH)
    parser.add_argument("--csv-output", type=Path, default=CSV_OUTPUT_PATH)
    parser.add_argument("--dist-meters", type=int, default=4000)
    parser.add_argument("--k-routes", type=int, default=5)
    parser.add_argument("--min-history-records", type=int, default=3)
    parser.add_argument("--max-tests", type=int, default=None)
    parser.add_argument("--random-seed", type=int, default=20260509)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    histories = load_histories(args.history_path)
    evaluation = evaluate_histories(
        histories=histories,
        min_history_records=args.min_history_records,
        max_tests=args.max_tests,
        dist_meters=args.dist_meters,
        k_routes=args.k_routes,
        random_seed=args.random_seed,
    )
    rows = summarize_results(evaluation)

    output = {
        "metadata": {
            "history_path": str(args.history_path),
            "json_output_path": str(args.json_output),
            "csv_output_path": str(args.csv_output),
            "dist_meters": args.dist_meters,
            "k_routes": args.k_routes,
            "min_history_records": args.min_history_records,
            "max_tests": args.max_tests,
            "feature_names": RANK_FEATURES,
            "evaluation_type": "route_candidate_ranking",
            "paper_aligned_proxy_metrics": {
                "path_precision_recall_f1": (
                    "Approximate NASR-style overlap: point coverage within "
                    f"{PATH_MATCH_THRESHOLD_M:.0f} meters between top-ranked generated route and held-out reconstructed route."
                ),
                "path_edit_distance": (
                    "Approximate NASR-style edit distance over rounded coordinate tokens; lower is better."
                ),
                "path_ndtw": (
                    "RICK-style normalized dynamic time warping over generated route coordinates and held-out reconstructed route coordinates; higher is better."
                ),
                "path_max_distance_m": (
                    "RICK-style maximum nearest-point distance between the top-ranked generated route and held-out reconstructed route; lower is better."
                ),
            },
            "old_evaluation_note": (
                "scripts/evaluate_baselines.py is retained as a history-record ranking sanity check: "
                "it ranks the held-out history record against previous history records. "
                "This script is stricter: it generates OSM route candidates for the held-out origin/destination "
                "and selects the oracle as the generated candidate closest to the observed pseudo-route features."
            ),
            "oracle_definition": (
                "For each held-out OSM pseudo-history record, the oracle is the generated route candidate with "
                "minimum normalized feature distance to the held-out reconstructed route features."
            ),
            "note": (
                "These are preliminary pseudo-history route-candidate baselines. They do not establish final "
                "route-choice performance against independently observed user decisions. Synthetic preference text, "
                "when present, is used only as a labeled prompt-baseline ablation."
            ),
        },
        "summary": rows,
        "observed_reconstruction_summary": summarize_observed_reconstruction(evaluation),
        "skipped": evaluation["skipped"],
        "attempted_records": evaluation["attempted_records"],
        "num_queries": evaluation["num_queries"],
        "per_query_results": evaluation["per_query_results"],
    }

    args.json_output.write_text(json.dumps(make_json_safe(output), indent=2), encoding="utf-8")
    write_csv(rows, args.csv_output)
    print_summary_table(rows)
    print(f"\nAttempted held-out records: {evaluation['attempted_records']}")
    print(f"Successful route-candidate queries: {evaluation['num_queries']}")
    print(f"Saved JSON: {args.json_output}")
    print(f"Saved CSV:  {args.csv_output}")


if __name__ == "__main__":
    main()
