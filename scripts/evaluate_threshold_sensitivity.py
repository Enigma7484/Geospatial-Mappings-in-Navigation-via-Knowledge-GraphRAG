import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_ROOT))

from scripts.build_osm_trace_histories import (
    build_data_quality_report,
    build_history_record_from_segment,
    build_pseudo_segments,
    load_all_probe_points,
    make_json_safe,
    max_segment_jump_m,
    safe_mean,
    safe_median,
    segment_distance_km,
    segment_duration_min,
    segment_speed_kmh,
)


JSON_OUTPUT_PATH = BACKEND_ROOT / "data" / "threshold_sensitivity.json"
CSV_OUTPUT_PATH = BACKEND_ROOT / "data" / "threshold_sensitivity.csv"


DEFAULT_CONFIGS = [
    {
        "name": "current",
        "max_gap_min": 10.0,
        "max_jump_m": 500.0,
        "min_points": 5,
        "min_distance_km": 0.2,
        "min_speed_kmh": 1.0,
        "max_speed_kmh": 80.0,
        "filter_max_jump_m": 500.0,
    },
    {
        "name": "stricter_gap",
        "max_gap_min": 5.0,
        "max_jump_m": 500.0,
        "min_points": 5,
        "min_distance_km": 0.2,
        "min_speed_kmh": 1.0,
        "max_speed_kmh": 80.0,
        "filter_max_jump_m": 500.0,
    },
    {
        "name": "stricter_jump",
        "max_gap_min": 10.0,
        "max_jump_m": 250.0,
        "min_points": 5,
        "min_distance_km": 0.2,
        "min_speed_kmh": 1.0,
        "max_speed_kmh": 80.0,
        "filter_max_jump_m": 250.0,
    },
    {
        "name": "stricter_distance",
        "max_gap_min": 10.0,
        "max_jump_m": 500.0,
        "min_points": 5,
        "min_distance_km": 0.5,
        "min_speed_kmh": 1.0,
        "max_speed_kmh": 80.0,
        "filter_max_jump_m": 500.0,
    },
    {
        "name": "lower_speed_ceiling",
        "max_gap_min": 10.0,
        "max_jump_m": 500.0,
        "min_points": 5,
        "min_distance_km": 0.2,
        "min_speed_kmh": 1.0,
        "max_speed_kmh": 25.0,
        "filter_max_jump_m": 500.0,
    },
]


def filter_segments_with_config(segments: List[List[Dict[str, Any]]], config: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    useful = []
    for seg in segments:
        dist = segment_distance_km(seg)
        speed = segment_speed_kmh(seg)
        jump = max_segment_jump_m(seg)
        if (
            dist >= float(config["min_distance_km"])
            and float(config["min_speed_kmh"]) <= speed <= float(config["max_speed_kmh"])
            and jump <= float(config["filter_max_jump_m"])
        ):
            useful.append(seg)
    return useful


def summarize_segments(segments: List[List[Dict[str, Any]]]) -> Dict[str, Optional[float]]:
    return {
        "segment_count": len(segments),
        "avg_segment_distance_km": safe_mean([segment_distance_km(s) for s in segments], None),
        "median_segment_distance_km": safe_median([segment_distance_km(s) for s in segments], None),
        "avg_segment_duration_min": safe_mean([segment_duration_min(s) for s in segments], None),
        "median_segment_duration_min": safe_median([segment_duration_min(s) for s in segments], None),
        "avg_segment_speed_kmh": safe_mean([segment_speed_kmh(s) for s in segments], None),
        "median_segment_speed_kmh": safe_median([segment_speed_kmh(s) for s in segments], None),
        "max_segment_jump_m": max([max_segment_jump_m(s) for s in segments], default=None),
    }


def evaluate_config(
    config: Dict[str, Any],
    all_points: List[Dict[str, Any]],
    total_points: int,
    timestamped_points: int,
    max_segments: Optional[int],
    skip_map_match: bool,
) -> Dict[str, Any]:
    print(f"\n=== Threshold config: {config['name']} ===")
    pseudo_segments = build_pseudo_segments(
        all_points,
        max_gap_min=float(config["max_gap_min"]),
        max_jump_m=float(config["max_jump_m"]),
        min_points=int(config["min_points"]),
    )
    useful_segments = filter_segments_with_config(pseudo_segments, config)
    attempted_segments = useful_segments[:max_segments] if max_segments is not None else useful_segments

    print(f"Pseudo-segments: {len(pseudo_segments)}")
    print(f"Useful segments: {len(useful_segments)}")
    print(f"Map-match attempts in this run: {len(attempted_segments)}")

    map_match_diags = []
    if skip_map_match:
        map_match_diags = [
            {
                "segment_index": idx,
                "raw_trace_distance_km": segment_distance_km(seg),
                "duration_min": segment_duration_min(seg),
                "avg_speed_kmh": segment_speed_kmh(seg),
                "max_jump_m": max_segment_jump_m(seg),
                "map_match_success": False,
                "error": "map matching skipped",
            }
            for idx, seg in enumerate(attempted_segments)
        ]
    else:
        for idx, seg in enumerate(attempted_segments):
            _, diag = build_history_record_from_segment(seg, idx)
            map_match_diags.append(diag)

    report = build_data_quality_report(
        total_points=total_points,
        timestamped_points=timestamped_points,
        pseudo_segments=pseudo_segments,
        useful_segments=useful_segments,
        map_match_diags=map_match_diags,
    )

    row = {
        "config": config["name"],
        "max_gap_min": config["max_gap_min"],
        "max_jump_m": config["max_jump_m"],
        "min_points": config["min_points"],
        "min_distance_km": config["min_distance_km"],
        "min_speed_kmh": config["min_speed_kmh"],
        "max_speed_kmh": config["max_speed_kmh"],
        "filter_max_jump_m": config["filter_max_jump_m"],
        "total_points": total_points,
        "timestamped_points": timestamped_points,
        "pseudo_segments_found": len(pseudo_segments),
        "useful_segments_found": len(useful_segments),
        "segments_map_matched": len(map_match_diags),
        "map_match_success_rate": report["map_matching_quality"]["map_match_success_rate"],
        "median_gps_to_route_median_m": report["map_matching_quality"]["median_gps_to_route_median_m"],
        "median_route_distance_ratio": report["map_matching_quality"]["median_route_distance_ratio"],
        "strict_prototype_usable": report["strict_prototype_usable"],
        "exploratory_usable": report["exploratory_usable"],
        "strict_failed_checks": ",".join(report["failed_checks"]["strict"]),
        "exploratory_failed_checks": ",".join(report["failed_checks"]["exploratory"]),
    }

    return {
        "config": config,
        "segment_summary": {
            "pseudo": summarize_segments(pseudo_segments),
            "useful": summarize_segments(useful_segments),
        },
        "row": row,
        "quality_report": report,
    }


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "config",
        "max_gap_min",
        "max_jump_m",
        "min_points",
        "min_distance_km",
        "min_speed_kmh",
        "max_speed_kmh",
        "filter_max_jump_m",
        "total_points",
        "timestamped_points",
        "pseudo_segments_found",
        "useful_segments_found",
        "segments_map_matched",
        "map_match_success_rate",
        "median_gps_to_route_median_m",
        "median_route_distance_ratio",
        "strict_prototype_usable",
        "exploratory_usable",
        "strict_failed_checks",
        "exploratory_failed_checks",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_summary(rows: List[Dict[str, Any]]) -> None:
    print("\nThreshold Sensitivity Summary")
    print("=" * 132)
    print(
        f"{'config':<18} {'pseudo':>7} {'useful':>7} {'matched':>7} "
        f"{'MMrate':>8} {'GPSmed':>9} {'RatioMed':>9} {'strict':>8} {'explore':>8} {'strict failed'}"
    )
    print("-" * 132)
    for row in rows:
        print(
            f"{row['config']:<18} {row['pseudo_segments_found']:>7} {row['useful_segments_found']:>7} "
            f"{row['segments_map_matched']:>7} {float(row['map_match_success_rate']):>8.3f} "
            f"{float(row['median_gps_to_route_median_m']):>9.3f} "
            f"{float(row['median_route_distance_ratio']):>9.3f} "
            f"{str(row['strict_prototype_usable']):>8} {str(row['exploratory_usable']):>8} "
            f"{row['strict_failed_checks']}"
        )
    print("=" * 132)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run threshold-sensitivity experiments over OSM-derived pseudo-history reconstruction. "
            "This does not overwrite the main history file."
        )
    )
    parser.add_argument("--json-output", type=Path, default=JSON_OUTPUT_PATH)
    parser.add_argument("--csv-output", type=Path, default=CSV_OUTPUT_PATH)
    parser.add_argument("--max-segments", type=int, default=None, help="Optional cap on useful segments map-matched per config.")
    parser.add_argument("--max-configs", type=int, default=None, help="Optional cap on default configs for quicker smoke runs.")
    parser.add_argument("--skip-map-match", action="store_true", help="Only evaluate segmentation/filtering thresholds.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    all_points = load_all_probe_points()
    total_points = len(all_points)
    timestamped_points = sum(1 for p in all_points if p["timestamp"] is not None)

    configs = DEFAULT_CONFIGS[: args.max_configs] if args.max_configs is not None else DEFAULT_CONFIGS
    results = [
        evaluate_config(
            config=config,
            all_points=all_points,
            total_points=total_points,
            timestamped_points=timestamped_points,
            max_segments=args.max_segments,
            skip_map_match=args.skip_map_match,
        )
        for config in configs
    ]
    rows = [r["row"] for r in results]

    output = {
        "metadata": {
            "total_points": total_points,
            "timestamped_points": timestamped_points,
            "skip_map_match": args.skip_map_match,
            "max_segments": args.max_segments,
            "note": (
                "Threshold sensitivity checks whether the OSM-derived pseudo-history pipeline is robust to "
                "segmentation and filtering choices. It is not a direct external-baseline comparison."
            ),
        },
        "summary": rows,
        "results": results,
    }

    args.json_output.write_text(json.dumps(make_json_safe(output), indent=2), encoding="utf-8")
    write_csv(rows, args.csv_output)
    print_summary(rows)
    print(f"\nSaved JSON: {args.json_output}")
    print(f"Saved CSV:  {args.csv_output}")


if __name__ == "__main__":
    main()
