import json
import sys
from pathlib import Path
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_ROOT))

from app.routing import generate_rankable_routes
from app.profile import get_request_context, build_dynamic_profile, summarize_profile, score_routes_with_profile

DATA_PATH = BACKEND_ROOT / "data" / "user_histories.json"
OUTPUT_PATH = BACKEND_ROOT / "data" / "evaluation_results.json"
FEATURES = ["distance_km", "major_pct", "walk_pct", "residential_pct", "service_pct", "intersections", "turns", "park_near_pct", "safety_score", "lit_pct", "signal_cnt", "crossing_cnt", "tunnel_m"]


def safe_float(x, default=0.0):
    try:
        return default if x is None else float(x)
    except Exception:
        return default


def vector_from_features(feats):
    return np.array([safe_float(feats.get(f, 0.0)) for f in FEATURES], dtype=float)


def normalize_matrix(X):
    X = np.asarray(X, dtype=float)
    mn, mx = X.min(axis=0), X.max(axis=0)
    denom = np.where(np.isclose(mx - mn, 0), 1.0, mx - mn)
    return (X - mn) / denom


def feature_similarity_rank(actual_features, candidate_features):
    actual_vec = vector_from_features(actual_features)
    candidate_vecs = np.vstack([vector_from_features(c) for c in candidate_features])
    all_norm = normalize_matrix(np.vstack([actual_vec, candidate_vecs]))
    distances = np.linalg.norm(all_norm[1:] - all_norm[0], axis=1)
    return int(np.argmin(distances)), distances


def evaluate_user(user_id, records, max_tests=5, dist_meters=1500, k_routes=3):
    results = []
    if len(records) < 4:
        return results
    for test_i in range(3, min(len(records), 3 + max_tests)):
        test_trip = records[test_i]
        train_history = records[:test_i]
        origin, destination = test_trip.get("origin"), test_trip.get("destination")
        if not origin or not destination:
            continue
        print(f"\nEvaluating {user_id}, trip {test_i}")
        print(f"Origin: {origin}")
        print(f"Destination: {destination}")
        try:
            context = get_request_context(test_trip.get("timestamp"))
            profile = build_dynamic_profile(train_history, context)
            route_feature_dicts, _ = generate_rankable_routes(origin=origin, destination=destination, dist_meters=dist_meters, k_routes=k_routes)
            if not route_feature_dicts:
                continue
            profile_scores = score_routes_with_profile(route_feature_dicts, profile)
            ranking = np.argsort(-profile_scores)
            oracle_idx, feature_distances = feature_similarity_rank(test_trip["features"], route_feature_dicts)
            rank_position = int(np.where(ranking == oracle_idx)[0][0]) + 1
            result = {
                "user_id": user_id,
                "trip_index": test_i,
                "timestamp": test_trip.get("timestamp"),
                "mode": test_trip.get("mode"),
                "context": context,
                "profile_summary": summarize_profile(profile),
                "actual_features": test_trip["features"],
                "oracle_candidate_index": oracle_idx,
                "oracle_rank_position": rank_position,
                "top1_candidate_index": int(ranking[0]),
                "top1_is_oracle": bool(ranking[0] == oracle_idx),
                "profile_scores": [float(x) for x in profile_scores],
                "feature_distances_to_actual": [float(x) for x in feature_distances],
                "candidate_summaries": [c["summary"] for c in route_feature_dicts],
            }
            print(f"Oracle candidate: {oracle_idx}")
            print(f"Oracle rank position: {rank_position}")
            print(f"Top-1 is oracle: {result['top1_is_oracle']}")
            results.append(result)
        except Exception as e:
            print(f"Failed {user_id}, trip {test_i}: {repr(e)}")
    return results


def main(max_users=3):
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        histories = json.load(f)
    all_results = []
    for user_id, records in list(histories.items())[:max_users]:
        print("\n==============================")
        print(f"User: {user_id}, records: {len(records)}")
        print("==============================")
        all_results.extend(evaluate_user(user_id, records, max_tests=5, dist_meters=1500, k_routes=3))
    if all_results:
        top1_hits = sum(1 for r in all_results if r["top1_is_oracle"])
        mrr = np.mean([1.0 / r["oracle_rank_position"] for r in all_results])
        summary = {"num_tests": len(all_results), "top1_hits": top1_hits, "top1_accuracy": top1_hits / len(all_results), "mrr": float(mrr)}
    else:
        summary = {"num_tests": 0, "top1_hits": 0, "top1_accuracy": 0.0, "mrr": 0.0}
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": all_results}, f, indent=2)
    print("\n==============================")
    print("Evaluation Summary")
    print("==============================")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved results to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main(max_users=3)
