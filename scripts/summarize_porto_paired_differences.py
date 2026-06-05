"""Summarize paired Porto benchmark differences from evaluator JSON.

The evaluator can be expensive because it builds OSM driving candidates. This
post-processing script keeps the statistical comparison separate: it reads the
per-query JSON artifact, computes paired method differences over queries where
both methods ran, and writes JSON/CSV tables for the paper and meeting notes.
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "porto_candidate_baseline_comparison.json"
DEFAULT_DIFF_JSON = ROOT / "data" / "porto_paired_bootstrap_differences.json"
DEFAULT_DIFF_CSV = ROOT / "data" / "porto_paired_bootstrap_differences.csv"
DEFAULT_ABLATION_JSON = ROOT / "data" / "porto_ablation_results.json"
DEFAULT_ABLATION_CSV = ROOT / "data" / "porto_ablation_results.csv"

METRICS = [
    ("Hit@1", "hit_at_1", "higher"),
    ("Hit@3", "hit_at_3", "higher"),
    ("MRR", "reciprocal_rank", "higher"),
    ("NDCG@3", "ndcg_at_3", "higher"),
    ("mean feature distance", "top1_feature_distance", "lower"),
    ("path F1", "path_f1", "higher"),
    ("NDTW", "path_ndtw", "higher"),
]

PAIRED_COMPARISONS = [
    ("vehicle_profile", "shortest_distance"),
    ("learned_feature_ranker", "shortest_distance"),
    ("vehicle_profile", "profile"),
]

ABLATION_METHODS = [
    ("shortest_distance", "Shortest-distance"),
    ("profile", "Generic profile"),
    ("vehicle_profile_no_temporal", "Vehicle profile without temporal context"),
    ("vehicle_profile", "Vehicle profile with temporal context"),
    ("learned_feature_ranker", "Learned feature ranker"),
]


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def paired_values(queries: Iterable[Dict[str, Any]], method_a: str, method_b: str, field: str) -> List[float]:
    diffs = []
    for query in queries:
        methods = query.get("methods", {})
        if method_a not in methods or method_b not in methods:
            continue
        a = as_float(methods[method_a].get(field))
        b = as_float(methods[method_b].get(field))
        if a is None or b is None:
            continue
        diffs.append(a - b)
    return diffs


def bootstrap_ci(values: List[float], samples: int, seed: int) -> Tuple[Optional[float], Optional[float]]:
    clean = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(clean) == 0:
        return None, None
    if len(clean) == 1 or samples <= 0:
        value = float(clean[0])
        return value, value
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=float)
    for i in range(samples):
        means[i] = float(np.mean(rng.choice(clean, size=len(clean), replace=True)))
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarize_method(queries: Iterable[Dict[str, Any]], method: str, label: str) -> Dict[str, Any]:
    rows = [q.get("methods", {}).get(method) for q in queries if method in q.get("methods", {})]
    row: Dict[str, Any] = {
        "Method": label,
        "method_key": method,
        "Status": "ran" if rows else "missing",
        "N": len(rows),
        "Notes": "",
    }
    if not rows:
        row["Notes"] = "Not present in the input artifact; rerun the Porto evaluator after the May 2026 no-temporal variant change."
    for label_name, field, _direction in METRICS:
        values = [as_float(item.get(field)) for item in rows]
        clean = [v for v in values if v is not None]
        row[label_name] = float(np.mean(clean)) if clean else None
    return row


def write_csv(rows: List[Dict[str, Any]], path: Path, fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute paired Porto bootstrap differences and ablation summaries.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--diff-json-output", type=Path, default=DEFAULT_DIFF_JSON)
    parser.add_argument("--diff-csv-output", type=Path, default=DEFAULT_DIFF_CSV)
    parser.add_argument("--ablation-json-output", type=Path, default=DEFAULT_ABLATION_JSON)
    parser.add_argument("--ablation-csv-output", type=Path, default=DEFAULT_ABLATION_CSV)
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--random-seed", type=int, default=20260521)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    queries = data.get("per_query_results", [])

    diff_rows = []
    for comparison_index, (method_a, method_b) in enumerate(PAIRED_COMPARISONS):
        for metric_index, (metric_label, field, direction) in enumerate(METRICS):
            diffs = paired_values(queries, method_a, method_b, field)
            mean_diff = float(np.mean(diffs)) if diffs else None
            lo, hi = bootstrap_ci(
                diffs,
                args.bootstrap_samples,
                args.random_seed + comparison_index * 1000 + metric_index,
            )
            significant = bool(lo is not None and hi is not None and (lo > 0 or hi < 0))
            notes = f"Paired over {len(diffs)} queries; positive means Method A is numerically larger."
            if direction == "lower":
                notes += " For this metric, lower values are better."
            diff_rows.append({
                "Metric": metric_label,
                "Method A": method_a,
                "Method B": method_b,
                "Difference": mean_diff,
                "95% CI low": lo,
                "95% CI high": hi,
                "Significant?": "Yes" if significant else "No",
                "Notes": notes,
            })

    ablation_rows = [summarize_method(queries, method, label) for method, label in ABLATION_METHODS]

    diff_payload = {
        "metadata": {
            "input": str(args.input),
            "bootstrap_samples": args.bootstrap_samples,
            "random_seed": args.random_seed,
            "note": "Paired differences are computed only over queries where both methods are present.",
        },
        "rows": diff_rows,
    }
    ablation_payload = {
        "metadata": {
            "input": str(args.input),
            "note": (
                "This summarizes available ablation rows from the input artifact. "
                "The no-temporal vehicle-profile row requires rerunning the updated Porto evaluator."
            ),
        },
        "rows": ablation_rows,
    }

    args.diff_json_output.parent.mkdir(parents=True, exist_ok=True)
    args.diff_json_output.write_text(json.dumps(diff_payload, indent=2), encoding="utf-8")
    args.ablation_json_output.write_text(json.dumps(ablation_payload, indent=2), encoding="utf-8")

    write_csv(
        diff_rows,
        args.diff_csv_output,
        ["Metric", "Method A", "Method B", "Difference", "95% CI low", "95% CI high", "Significant?", "Notes"],
    )
    write_csv(
        ablation_rows,
        args.ablation_csv_output,
        ["Method", "method_key", "Status", "N", "Hit@1", "Hit@3", "MRR", "NDCG@3", "mean feature distance", "path F1", "NDTW", "Notes"],
    )
    print(f"Wrote paired differences: {args.diff_json_output} and {args.diff_csv_output}")
    print(f"Wrote ablation summary:   {args.ablation_json_output} and {args.ablation_csv_output}")


if __name__ == "__main__":
    main()
