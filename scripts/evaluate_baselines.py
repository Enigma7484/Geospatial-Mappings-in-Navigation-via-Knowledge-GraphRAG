import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_ROOT))

from app.profile import build_dynamic_profile, get_request_context, score_routes_with_profile


HISTORY_PATH = BACKEND_ROOT / "data" / "user_histories_osm_trace.json"
JSON_OUTPUT_PATH = BACKEND_ROOT / "data" / "baseline_comparison.json"
CSV_OUTPUT_PATH = BACKEND_ROOT / "data" / "baseline_comparison.csv"

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
    "random": "Randomly permutes the same candidate pool; deterministic seed for reproducibility.",
    "shortest_distance": "Ranks candidates by shortest reconstructed OSM route distance.",
    "prompt_sbert": "Ranks route text by semantic similarity to preference text using SBERT.",
    "profile": "Builds a dynamic profile from earlier records and scores candidates with profile weights.",
    "hybrid": "Combines profile and prompt/SBERT scores using the backend's 0.75/0.25 weighting.",
}


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


def load_histories(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing OSM pseudo-history file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {user_id: records for user_id, records in data.items() if isinstance(records, list)}


def feature_vec(features: Dict[str, Any]) -> np.ndarray:
    return np.array([safe_float(features.get(name, 0.0)) for name in RANK_FEATURES], dtype=float)


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


def candidate_distances_and_relevances(
    heldout_features: Dict[str, Any],
    candidate_features: List[Dict[str, Any]],
) -> Dict[str, List[float]]:
    heldout_vec = feature_vec(heldout_features)
    candidate_vecs = np.vstack([feature_vec(c) for c in candidate_features])
    normalized = minmax_matrix(np.vstack([heldout_vec, candidate_vecs]))
    target = normalized[0]
    candidates = normalized[1:]
    distances = np.linalg.norm(candidates - target, axis=1)
    max_dist = max(float(np.max(distances)), 1e-9)
    relevances = [1.0 - float(d / max_dist) for d in distances]
    return {
        "feature_distances": [float(x) for x in distances],
        "relevances": relevances,
    }


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


def preference_text_for_record(record: Dict[str, Any]) -> Optional[str]:
    for key in ("preference", "preference_text", "user_preference", "prompt"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def ranking_from_scores(scores: np.ndarray) -> List[int]:
    return [int(idx) for idx in np.argsort(-np.asarray(scores, dtype=float))]


def evaluate_ranking(
    method: str,
    ranked_indices: List[int],
    relevances: List[float],
    feature_distances: List[float],
    user_id: str,
    test_index: int,
    timestamp: str,
) -> Dict[str, Any]:
    oracle_rank = ranked_indices.index(0) + 1
    ranked_relevances = [relevances[i] for i in ranked_indices]
    top_index = ranked_indices[0]
    return {
        "method": method,
        "user_id": user_id,
        "test_index": test_index,
        "timestamp": timestamp,
        "oracle_rank": oracle_rank,
        "hit_at_1": oracle_rank <= 1,
        "hit_at_3": oracle_rank <= 3,
        "reciprocal_rank": 1.0 / oracle_rank,
        "ndcg_at_3": ndcg_at_k(ranked_relevances, 3),
        "top1_feature_distance": feature_distances[top_index],
        "ranked_indices": ranked_indices,
        "ranked_relevances": ranked_relevances,
        "ranked_feature_distances": [feature_distances[i] for i in ranked_indices],
    }


def add_skip(skipped: Dict[str, str], method: str, reason: str) -> None:
    skipped.setdefault(method, reason)


def evaluate_histories(
    histories: Dict[str, List[Dict[str, Any]]],
    min_history_records: int = 3,
    max_previous_candidates: int = 5,
    random_seed: int = 20260508,
) -> Dict[str, Any]:
    per_query_results = []
    skipped: Dict[str, str] = {}
    num_queries = 0

    for user_id, records in histories.items():
        usable_records = [r for r in records if isinstance(r.get("features"), dict)]
        if len(usable_records) <= min_history_records:
            add_skip(
                skipped,
                "all",
                f"{user_id} has {len(usable_records)} usable records; need more than {min_history_records}.",
            )
            continue

        for test_index in range(min_history_records, len(usable_records)):
            train = usable_records[:test_index]
            heldout = usable_records[test_index]
            timestamp = heldout.get("timestamp")
            if not timestamp:
                continue

            # Candidate pool follows the existing leave-one-out setup:
            # candidate 0 is the observed/pseudo-route, followed by recent previous routes.
            previous = train[-max_previous_candidates:]
            candidate_records = [heldout] + previous
            candidate_features = [r["features"] for r in candidate_records]
            if len(candidate_features) < 2:
                continue

            num_queries += 1
            sim = candidate_distances_and_relevances(heldout["features"], candidate_features)
            feature_distances = sim["feature_distances"]
            relevances = sim["relevances"]

            query_result = {
                "user_id": user_id,
                "test_index": test_index,
                "timestamp": timestamp,
                "candidate_count": len(candidate_features),
                "oracle_candidate_index": 0,
                "methods": {},
            }

            # Baseline 1: random ranking.
            # This measures whether any personalized method beats chance under the same candidate set.
            rng = np.random.default_rng(random_seed + test_index)
            random_ranking = [int(i) for i in rng.permutation(len(candidate_features))]
            query_result["methods"]["random"] = evaluate_ranking(
                "random", random_ranking, relevances, feature_distances, user_id, test_index, timestamp
            )

            # Baseline 2: shortest-distance ranking.
            # This is the non-personalized route-planning baseline most routing systems optimize first.
            shortest_ranking = sorted(
                range(len(candidate_features)),
                key=lambda i: safe_float(candidate_features[i].get("distance_km"), float("inf")),
            )
            query_result["methods"]["shortest_distance"] = evaluate_ranking(
                "shortest_distance", shortest_ranking, relevances, feature_distances, user_id, test_index, timestamp
            )

            # Baseline 4: profile ranking.
            # Earlier pseudo-history records are converted into dynamic profile weights.
            try:
                context = get_request_context(timestamp)
                profile = build_dynamic_profile(train, context)
                profile_scores = score_routes_with_profile(candidate_features, profile)
                profile_ranking = ranking_from_scores(profile_scores)
                query_result["methods"]["profile"] = evaluate_ranking(
                    "profile", profile_ranking, relevances, feature_distances, user_id, test_index, timestamp
                )
                query_result["methods"]["profile"]["scores"] = [float(x) for x in profile_scores]
            except Exception as exc:
                add_skip(skipped, "profile", f"Profile baseline failed: {repr(exc)}")
                profile_scores = None

            preference = preference_text_for_record(heldout)
            sbert_scores = None

            # Baseline 3: prompt/SBERT ranking.
            # This requires real preference text in the history record; the current OSM pseudo-history
            # usually does not contain it, so the baseline is skipped honestly when absent.
            if not preference:
                add_skip(skipped, "prompt_sbert", "No preference text found in OSM pseudo-history records.")
            else:
                try:
                    from app.ranking import rank_route_texts

                    route_texts = [route_text_from_features(f) for f in candidate_features]
                    sbert_scores = minmax_scores(np.asarray(rank_route_texts(route_texts, preference), dtype=float))
                    sbert_ranking = ranking_from_scores(sbert_scores)
                    query_result["methods"]["prompt_sbert"] = evaluate_ranking(
                        "prompt_sbert", sbert_ranking, relevances, feature_distances, user_id, test_index, timestamp
                    )
                    query_result["methods"]["prompt_sbert"]["scores"] = [float(x) for x in sbert_scores]
                    query_result["methods"]["prompt_sbert"]["preference"] = preference
                except Exception as exc:
                    add_skip(skipped, "prompt_sbert", f"Prompt/SBERT baseline failed: {repr(exc)}")

            # Baseline 5: hybrid ranking.
            # Mirrors app/main.py: 0.75 profile score + 0.25 SBERT score.
            if profile_scores is None:
                add_skip(skipped, "hybrid", "Profile scores unavailable.")
            elif sbert_scores is None:
                add_skip(skipped, "hybrid", "No prompt/SBERT scores available because preference text is missing or SBERT failed.")
            else:
                hybrid_scores = 0.75 * np.asarray(profile_scores, dtype=float) + 0.25 * np.asarray(sbert_scores, dtype=float)
                hybrid_ranking = ranking_from_scores(hybrid_scores)
                query_result["methods"]["hybrid"] = evaluate_ranking(
                    "hybrid", hybrid_ranking, relevances, feature_distances, user_id, test_index, timestamp
                )
                query_result["methods"]["hybrid"]["scores"] = [float(x) for x in hybrid_scores]

            per_query_results.append(query_result)

    return {
        "num_queries": num_queries,
        "per_query_results": per_query_results,
        "skipped": skipped,
    }


def summarize_results(evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_method: Dict[str, List[Dict[str, Any]]] = {}
    for query in evaluation["per_query_results"]:
        for method, result in query["methods"].items():
            by_method.setdefault(method, []).append(result)

    rows = []
    all_methods = ["random", "shortest_distance", "prompt_sbert", "profile", "hybrid"]
    for method in all_methods:
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
                "skip_reason": "",
                "description": BASELINE_DESCRIPTIONS[method],
            })
        else:
            rows.append({
                "method": method,
                "status": "skipped",
                "num_queries": 0,
                "hit_at_1": None,
                "hit_at_3": None,
                "mrr": None,
                "ndcg_at_3": None,
                "mean_feature_distance": None,
                "skip_reason": evaluation["skipped"].get(method, "No valid queries for this baseline."),
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
        "skip_reason",
        "description",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_summary_table(rows: List[Dict[str, Any]]) -> None:
    print("\nBaseline Comparison")
    print("=" * 98)
    print(f"{'method':<18} {'status':<8} {'n':>3} {'Hit@1':>8} {'Hit@3':>8} {'MRR':>8} {'NDCG@3':>8} {'MeanDist':>10}")
    print("-" * 98)
    for row in rows:
        if row["status"] == "ran":
            print(
                f"{row['method']:<18} {row['status']:<8} {row['num_queries']:>3} "
                f"{row['hit_at_1']:>8.3f} {row['hit_at_3']:>8.3f} "
                f"{row['mrr']:>8.3f} {row['ndcg_at_3']:>8.3f} "
                f"{row['mean_feature_distance']:>10.3f}"
            )
        else:
            print(f"{row['method']:<18} {row['status']:<8} {row['num_queries']:>3} {'-':>8} {'-':>8} {'-':>8} {'-':>8} {'-':>10}")
            print(f"  reason: {row['skip_reason']}")
    print("=" * 98)


def main() -> None:
    histories = load_histories(HISTORY_PATH)
    evaluation = evaluate_histories(histories)
    rows = summarize_results(evaluation)

    output = {
        "metadata": {
            "history_path": str(HISTORY_PATH),
            "json_output_path": str(JSON_OUTPUT_PATH),
            "csv_output_path": str(CSV_OUTPUT_PATH),
            "feature_names": RANK_FEATURES,
            "evaluation_setup": (
                "Leave-one-out over OSM pseudo-history records. Earlier records form profile history; "
                "candidate 0 is the held-out observed/pseudo-route and candidates 1..k are recent previous routes."
            ),
            "oracle_definition": "The held-out record, inserted as candidate index 0.",
            "note": (
                "These are preliminary pseudo-history ranking baselines. They do not establish final route-choice "
                "performance against independently observed user decisions."
            ),
        },
        "summary": rows,
        "skipped": evaluation["skipped"],
        "per_query_results": evaluation["per_query_results"],
    }

    JSON_OUTPUT_PATH.write_text(json.dumps(make_json_safe(output), indent=2), encoding="utf-8")
    write_csv(rows, CSV_OUTPUT_PATH)
    print_summary_table(rows)
    print(f"\nSaved JSON: {JSON_OUTPUT_PATH}")
    print(f"Saved CSV:  {CSV_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
