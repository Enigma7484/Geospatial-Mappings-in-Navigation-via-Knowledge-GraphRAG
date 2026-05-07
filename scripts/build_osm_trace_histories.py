import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString


# --------------------------------------------------
# Paths / imports
# --------------------------------------------------

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_ROOT))

from app.routing import compute_route_features

PROBE_DIR = BACKEND_ROOT / "data" / "osm_history_probe"

HISTORY_OUTPUT_PATH = BACKEND_ROOT / "data" / "user_histories_osm_trace.json"
QUALITY_REPORT_PATH = BACKEND_ROOT / "data" / "osm_trace_quality_report.json"
RANKING_EVAL_PATH = BACKEND_ROOT / "data" / "osm_trace_ranking_eval.json"

HISTORY_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Basic helpers
# --------------------------------------------------

def make_json_safe(obj):
    """
    Recursively convert NumPy/Python objects into JSON-safe values.
    """
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

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_time(t: Optional[str]) -> Optional[datetime]:
    if not t:
        return None
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00"))
    except Exception:
        return None


def safe_mean(values: List[float], default: float = 0.0) -> float:
    values = [v for v in values if v is not None and np.isfinite(v)]
    return float(np.mean(values)) if values else default


def safe_median(values: List[float], default: float = 0.0) -> float:
    values = [v for v in values if v is not None and np.isfinite(v)]
    return float(np.median(values)) if values else default


def safe_min(values: List[float], default: float = 0.0) -> float:
    values = [v for v in values if v is not None and np.isfinite(v)]
    return float(np.min(values)) if values else default


def safe_max(values: List[float], default: float = 0.0) -> float:
    values = [v for v in values if v is not None and np.isfinite(v)]
    return float(np.max(values)) if values else default


# --------------------------------------------------
# GPX parsing
# --------------------------------------------------

def parse_gpx_trackpoints(path: Path) -> List[Dict[str, Any]]:
    root = ET.parse(path).getroot()

    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    points = []

    for pt in root.iter(f"{ns}trkpt"):
        lat = pt.attrib.get("lat")
        lon = pt.attrib.get("lon")
        time_el = pt.find(f"{ns}time")

        if lat is None or lon is None:
            continue

        dt = parse_time(time_el.text if time_el is not None else None)

        points.append({
            "lat": float(lat),
            "lon": float(lon),
            "timestamp": dt,
            "has_timestamp": dt is not None,
        })

    return points


def load_all_probe_points() -> List[Dict[str, Any]]:
    gpx_files = sorted(PROBE_DIR.glob("osm_trackpoints_page_*.gpx"))

    if not gpx_files:
        raise FileNotFoundError(
            f"No OSM probe GPX files found in {PROBE_DIR}. "
            "Run scripts/osm_history_probe.py first."
        )

    all_points = []

    for path in gpx_files:
        pts = parse_gpx_trackpoints(path)
        print(f"Loaded {len(pts)} points from {path.name}")
        all_points.extend(pts)

    with_time = [p for p in all_points if p["timestamp"] is not None]
    with_time.sort(key=lambda p: p["timestamp"])

    return with_time


# --------------------------------------------------
# Segment construction
# --------------------------------------------------

def build_pseudo_segments(
    points: List[Dict[str, Any]],
    max_gap_min: float = 10.0,
    max_jump_m: float = 500.0,
    min_points: int = 5,
) -> List[List[Dict[str, Any]]]:
    """
    Reconstruct movement-like pseudo-segments from timestamped OSM trackpoints.

    These are not guaranteed to be one true user/trip.
    They are OSM-native historical movement signals.
    """
    if len(points) < min_points:
        return []

    segments = []
    current = [points[0]]

    for prev, curr in zip(points[:-1], points[1:]):
        gap_min = (curr["timestamp"] - prev["timestamp"]).total_seconds() / 60.0
        jump_m = haversine_m(prev["lat"], prev["lon"], curr["lat"], curr["lon"])

        if gap_min > max_gap_min or jump_m > max_jump_m:
            if len(current) >= min_points:
                segments.append(current)
            current = [curr]
        else:
            current.append(curr)

    if len(current) >= min_points:
        segments.append(current)

    return segments


def segment_distance_km(segment: List[Dict[str, Any]]) -> float:
    total_m = 0.0

    for a, b in zip(segment[:-1], segment[1:]):
        total_m += haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])

    return total_m / 1000.0


def segment_duration_min(segment: List[Dict[str, Any]]) -> float:
    return max(
        (segment[-1]["timestamp"] - segment[0]["timestamp"]).total_seconds() / 60.0,
        0.01,
    )


def segment_speed_kmh(segment: List[Dict[str, Any]]) -> float:
    dist_km = segment_distance_km(segment)
    duration_hr = max(segment_duration_min(segment) / 60.0, 0.001)
    return dist_km / duration_hr


def max_segment_jump_m(segment: List[Dict[str, Any]]) -> float:
    jumps = [
        haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        for a, b in zip(segment[:-1], segment[1:])
    ]
    return safe_max(jumps, 0.0)


def filter_useful_segments(segments: List[List[Dict[str, Any]]]) -> List[List[Dict[str, Any]]]:
    useful = []

    for seg in segments:
        dist = segment_distance_km(seg)
        speed = segment_speed_kmh(seg)
        max_jump = max_segment_jump_m(seg)

        # Prototype screening thresholds.
        # These are not universal claims; they are initial data-quality filters.
        if (
            dist >= 0.2
            and 1.0 <= speed <= 80.0
            and max_jump <= 500.0
        ):
            useful.append(seg)

    return useful


# --------------------------------------------------
# OSM graph + parks
# --------------------------------------------------

_graph_cache = {}


def segment_bbox(segment: List[Dict[str, Any]], buffer_deg: float = 0.003):
    lats = [p["lat"] for p in segment]
    lons = [p["lon"] for p in segment]

    north = max(lats) + buffer_deg
    south = min(lats) - buffer_deg
    east = max(lons) + buffer_deg
    west = min(lons) - buffer_deg

    return north, south, east, west


def get_graph_for_segment(segment: List[Dict[str, Any]]):
    north, south, east, west = segment_bbox(segment)

    cache_key = (
        round(north, 3),
        round(south, 3),
        round(east, 3),
        round(west, 3),
    )

    if cache_key in _graph_cache:
        return _graph_cache[cache_key]

    print(f"  Building OSM graph for bbox north={north}, south={south}, east={east}, west={west}")

    # IMPORTANT:
    # OSMnx newer versions expect bbox as (west, south, east, north).
    # Older versions accepted separate north, south, east, west args.
    try:
        G = ox.graph_from_bbox(
            bbox=(west, south, east, north),
            network_type="walk",
            simplify=True,
        )
    except TypeError:
        G = ox.graph_from_bbox(
            north,
            south,
            east,
            west,
            network_type="walk",
            simplify=True,
        )

    G = ox.distance.add_edge_lengths(G)

    try:
        G = ox.bearing.add_edge_bearings(G)
    except Exception:
        try:
            G = ox.add_edge_bearings(G)
        except Exception:
            pass

    G_proj = ox.project_graph(G)

    center = (
        sum(p["lat"] for p in segment) / len(segment),
        sum(p["lon"] for p in segment) / len(segment),
    )

    tags = {
        "leisure": ["park", "garden", "playground"],
        "landuse": ["grass", "recreation_ground"],
        "natural": ["wood"],
    }

    parks_union = None

    try:
        try:
            parks = ox.features_from_point(center, tags=tags, dist=2000)
        except Exception:
            parks = ox.geometries_from_point(center, tags=tags, dist=2000)

        if len(parks) > 0:
            parks = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()

        if len(parks) > 0:
            nodes_proj = ox.graph_to_gdfs(G_proj, nodes=True, edges=False)
            parks_proj = parks.to_crs(nodes_proj.crs)

            if hasattr(parks_proj.geometry, "union_all"):
                parks_union = parks_proj.geometry.union_all()
            else:
                parks_union = parks_proj.geometry.unary_union

    except Exception as e:
        print(f"  Park fetch failed: {repr(e)}")
        parks_union = None

    _graph_cache[cache_key] = (G, G_proj, parks_union)
    return G, G_proj, parks_union

# --------------------------------------------------
# Approximate map-matching
# --------------------------------------------------

def reconstruct_route_from_segment(G, segment: List[Dict[str, Any]]) -> Tuple[Optional[List[int]], Dict[str, Any]]:
    xs = [p["lon"] for p in segment]
    ys = [p["lat"] for p in segment]

    matched_nodes = ox.distance.nearest_nodes(G, X=xs, Y=ys)

    deduped = []
    for n in matched_nodes:
        n = int(n)
        if not deduped or n != deduped[-1]:
            deduped.append(n)

    diagnostics = {
        "segment_points": len(segment),
        "matched_points": len(matched_nodes),
        "unique_matched_nodes": len(deduped),
        "matched_point_coverage": len(matched_nodes) / max(len(segment), 1),
    }

    if len(deduped) < 2:
        return None, diagnostics

    full_route = []
    successful_pairs = 0
    attempted_pairs = 0

    for a, b in zip(deduped[:-1], deduped[1:]):
        if a == b:
            continue

        attempted_pairs += 1

        try:
            path = nx.shortest_path(G, a, b, weight="length")
            successful_pairs += 1
        except Exception:
            continue

        if not path:
            continue

        if not full_route:
            full_route.extend(path)
        else:
            full_route.extend(path[1:])

    cleaned = []
    for n in full_route:
        if not cleaned or n != cleaned[-1]:
            cleaned.append(n)

    diagnostics["attempted_node_pairs"] = attempted_pairs
    diagnostics["successful_node_pairs"] = successful_pairs
    diagnostics["pair_success_rate"] = successful_pairs / max(attempted_pairs, 1)
    diagnostics["route_nodes"] = len(cleaned)

    if len(cleaned) < 2:
        return None, diagnostics

    return cleaned, diagnostics


def route_line_distance_stats(
    G,
    G_proj,
    route: List[int],
    segment: List[Dict[str, Any]],
) -> Dict[str, float]:
    """
    Compute GPS-to-route distance in meters after projecting both route and GPS points.
    """
    try:
        route_points_ll = [
            Point(G.nodes[n]["x"], G.nodes[n]["y"])
            for n in route
            if n in G.nodes
        ]

        if len(route_points_ll) < 2:
            return {
                "gps_to_route_mean_m": None,
                "gps_to_route_median_m": None,
            }

        route_gdf = gpd.GeoSeries(
            [LineString(route_points_ll)],
            crs="EPSG:4326",
        )

        gps_gdf = gpd.GeoSeries(
            [Point(p["lon"], p["lat"]) for p in segment],
            crs="EPSG:4326",
        )

        projected_crs = ox.graph_to_gdfs(G_proj, nodes=True, edges=False).crs

        route_proj = route_gdf.to_crs(projected_crs).iloc[0]
        gps_proj = gps_gdf.to_crs(projected_crs)

        dists = [pt.distance(route_proj) for pt in gps_proj]

        return {
            "gps_to_route_mean_m": safe_mean(dists, None),
            "gps_to_route_median_m": safe_median(dists, None),
        }

    except Exception as e:
        print(f"  GPS-route distance calc failed: {repr(e)}")
        return {
            "gps_to_route_mean_m": None,
            "gps_to_route_median_m": None,
        }


# --------------------------------------------------
# History record building
# --------------------------------------------------

def build_history_record_from_segment(segment: List[Dict[str, Any]], idx: int) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    raw_trace_distance_km = segment_distance_km(segment)
    duration_min = segment_duration_min(segment)
    avg_speed_kmh = segment_speed_kmh(segment)
    max_jump_m = max_segment_jump_m(segment)

    base_diag = {
        "segment_index": idx,
        "raw_trace_distance_km": raw_trace_distance_km,
        "duration_min": duration_min,
        "avg_speed_kmh": avg_speed_kmh,
        "max_jump_m": max_jump_m,
        "map_match_success": False,
    }

    try:
        G, G_proj, parks_union = get_graph_for_segment(segment)
        route, match_diag = reconstruct_route_from_segment(G, segment)
        base_diag.update(match_diag)

        if route is None:
            print(f"  Segment {idx}: failed to reconstruct route")
            return None, base_diag

        feat = compute_route_features(G, G_proj, parks_union, route)

        distance_stats = route_line_distance_stats(G, G_proj, route, segment)
        base_diag.update(distance_stats)

        route_distance_km = feat["distance_km"]
        route_distance_ratio = route_distance_km / max(raw_trace_distance_km, 0.001)

        base_diag.update({
            "map_match_success": True,
            "route_distance_km": route_distance_km,
            "route_distance_ratio": route_distance_ratio,
            "candidate_feature_summary": feat["summary"],
        })

        record = {
            "timestamp": segment[0]["timestamp"].isoformat(),
            "mode": "osm_pseudo_trace",
            "source": "osm_public_gps_trackpoints",
            "origin": {
                "lat": segment[0]["lat"],
                "lon": segment[0]["lon"],
            },
            "destination": {
                "lat": segment[-1]["lat"],
                "lon": segment[-1]["lon"],
            },
            "features": {
                "distance_km": feat["distance_km"],
                "major_pct": feat["major_pct"],
                "walk_pct": feat["walk_pct"],
                "residential_pct": feat["residential_pct"],
                "service_pct": feat["service_pct"],
                "intersections": feat["intersections"],
                "turns": feat["turns"],
                "park_near_pct": feat["park_near_pct"],
                "safety_score": feat["safety_score"],
                "lit_pct": feat["lit_pct"],
                "signal_cnt": feat["signal_cnt"],
                "crossing_cnt": feat["crossing_cnt"],
                "tunnel_m": feat["tunnel_m"],

                "raw_trace_distance_km": round(raw_trace_distance_km, 3),
                "duration_min": round(duration_min, 2),
                "avg_speed_kmh": round(avg_speed_kmh, 2),
                "pseudo_segment_points": len(segment),
                "route_distance_ratio": route_distance_ratio,
                "gps_to_route_mean_m": distance_stats["gps_to_route_mean_m"],
                "gps_to_route_median_m": distance_stats["gps_to_route_median_m"],
            },
        }

        print(
            f"  Segment {idx}: added "
            f"route_dist={record['features']['distance_km']:.2f}km, "
            f"raw_dist={raw_trace_distance_km:.2f}km, "
            f"ratio={route_distance_ratio:.2f}, "
            f"safety={record['features']['safety_score']:.1f}/100"
        )

        return record, base_diag

    except Exception as e:
        base_diag["error"] = repr(e)
        print(f"  Segment {idx}: failed with {repr(e)}")
        return None, base_diag


# --------------------------------------------------
# Quality reports
# --------------------------------------------------

def build_data_quality_report(
    total_points: int,
    timestamped_points: int,
    pseudo_segments: List[List[Dict[str, Any]]],
    useful_segments: List[List[Dict[str, Any]]],
    map_match_diags: List[Dict[str, Any]],
) -> Dict[str, Any]:

    useful_distances = [segment_distance_km(s) for s in useful_segments]
    useful_durations = [segment_duration_min(s) for s in useful_segments]
    useful_speeds = [segment_speed_kmh(s) for s in useful_segments]
    useful_jumps = [max_segment_jump_m(s) for s in useful_segments]

    successes = [d for d in map_match_diags if d.get("map_match_success")]
    route_ratios = [d.get("route_distance_ratio") for d in successes]
    gps_mean_dists = [d.get("gps_to_route_mean_m") for d in successes]
    gps_median_dists = [d.get("gps_to_route_median_m") for d in successes]
    pair_success_rates = [d.get("pair_success_rate") for d in successes]

    report = {
        "data_quality": {
            "total_points": total_points,
            "timestamped_points": timestamped_points,
            "timestamp_coverage": timestamped_points / max(total_points, 1),

            "pseudo_segments_found": len(pseudo_segments),
            "useful_segments_found": len(useful_segments),
            "useful_segment_rate": len(useful_segments) / max(len(pseudo_segments), 1),

            "avg_segment_distance_km": safe_mean(useful_distances),
            "median_segment_distance_km": safe_median(useful_distances),
            "min_segment_distance_km": safe_min(useful_distances),
            "max_segment_distance_km": safe_max(useful_distances),

            "avg_segment_duration_min": safe_mean(useful_durations),
            "median_segment_duration_min": safe_median(useful_durations),

            "avg_segment_speed_kmh": safe_mean(useful_speeds),
            "median_segment_speed_kmh": safe_median(useful_speeds),

            "max_observed_jump_m": safe_max(useful_jumps),
        },

        "map_matching_quality": {
            "segments_attempted": len(map_match_diags),
            "map_match_successes": len(successes),
            "map_match_success_rate": len(successes) / max(len(map_match_diags), 1),

            "avg_route_distance_ratio": safe_mean(route_ratios),
            "median_route_distance_ratio": safe_median(route_ratios),

            "avg_gps_to_route_mean_m": safe_mean(gps_mean_dists),
            "median_gps_to_route_median_m": safe_median(gps_median_dists),

            "avg_pair_success_rate": safe_mean(pair_success_rates),
        },

        "prototype_thresholds": {
            "timestamp_coverage_min": 0.80,
            "useful_segments_min": 5,
            "map_match_success_rate_min": 0.70,
            "route_distance_ratio_target_range": [0.5, 2.0],
            "gps_to_route_median_target_m": 100,
        },
    }

    checks = {
        "timestamp_coverage_ok": report["data_quality"]["timestamp_coverage"] >= 0.80,
        "useful_segments_ok": report["data_quality"]["useful_segments_found"] >= 5,
        "map_match_success_rate_ok": report["map_matching_quality"]["map_match_success_rate"] >= 0.70,
        "route_distance_ratio_ok": (
            0.5 <= report["map_matching_quality"]["median_route_distance_ratio"] <= 2.5
        ),
        "gps_to_route_distance_ok": (
            report["map_matching_quality"]["median_gps_to_route_median_m"] <= 100
        ),
    }

    report["checks"] = checks
    report["overall_prototype_usable"] = all(checks.values())

    return report


# --------------------------------------------------
# Ranking evaluation
# --------------------------------------------------

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


def minmax_matrix(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    mn = X.min(axis=0)
    mx = X.max(axis=0)
    denom = np.where(np.isclose(mx - mn, 0), 1.0, mx - mn)
    return (X - mn) / denom


def feature_vec(features: Dict[str, Any]) -> np.ndarray:
    return np.array([float(features.get(f, 0.0) or 0.0) for f in RANK_FEATURES])


def dcg_at_k(relevances: List[float], k: int) -> float:
    rel = np.asarray(relevances[:k], dtype=float)
    if len(rel) == 0:
        return 0.0

    discounts = np.log2(np.arange(2, len(rel) + 2))
    return float(np.sum(rel / discounts))


def ndcg_at_k(relevances: List[float], k: int) -> float:
    actual = dcg_at_k(relevances, k)
    ideal = dcg_at_k(sorted(relevances, reverse=True), k)
    if ideal == 0:
        return 0.0
    return actual / ideal


def evaluate_profile_ranking(records: List[Dict[str, Any]], max_tests: int = 10) -> Dict[str, Any]:
    """
    Lightweight evaluation over the generated OSM pseudo-history records.

    Leave-one-out style:
    - Use previous records as history.
    - Hold out one record as observed pseudo-route.
    - Candidate set = previous history records + held-out record.
    - Relevance = feature similarity to held-out observed route.
    - Model ranking = profile score from current profile.

    This is not final navigation evaluation.
    It is a controlled profile-ranking sanity check.
    """
    if len(records) < 4:
        return {
            "num_tests": 0,
            "reason": "Need at least 4 records for profile ranking evaluation.",
        }

    from app.profile import (
        get_request_context,
        build_dynamic_profile,
        score_routes_with_profile,
    )

    test_results = []

    test_indices = list(range(3, min(len(records), 3 + max_tests)))

    for test_idx in test_indices:
        train = records[:test_idx]
        heldout = records[test_idx]
        context = get_request_context(heldout["timestamp"])
        profile = build_dynamic_profile(train, context)

        # Candidate pool: heldout + previous examples.
        # This checks if the profile ranks the observed-like route highly.
        candidates = [heldout["features"]] + [r["features"] for r in train[-5:]]

        profile_scores = score_routes_with_profile(candidates, profile)
        ranked_indices = [int(x) for x in np.argsort(-profile_scores)]

        # Relevance by feature similarity to heldout route.
        heldout_vec = feature_vec(heldout["features"])
        cand_vecs = np.vstack([feature_vec(c) for c in candidates])
        all_norm = minmax_matrix(np.vstack([heldout_vec, cand_vecs]))

        target = all_norm[0]
        cand_norm = all_norm[1:]

        dists = np.linalg.norm(cand_norm - target, axis=1)
        max_dist = max(float(np.max(dists)), 1e-9)
        relevances = [1.0 - float(d / max_dist) for d in dists]

        # Oracle is candidate 0 because candidate 0 is the actual heldout record.
        oracle_rank = ranked_indices.index(0) + 1

        ranked_relevances = [relevances[i] for i in ranked_indices]

        test_results.append({
            "test_index": test_idx,
            "timestamp": heldout["timestamp"],
            "oracle_rank": oracle_rank,
            "hit_at_1": oracle_rank <= 1,
            "hit_at_3": oracle_rank <= 3,
            "reciprocal_rank": 1.0 / oracle_rank,
            "ndcg_at_3": ndcg_at_k(ranked_relevances, 3),
            "profile_scores": [float(x) for x in profile_scores],
            "ranked_indices": ranked_indices,
            "relevances_ranked": ranked_relevances,
        })

    if not test_results:
        return {"num_tests": 0}

    return {
        "num_tests": len(test_results),
        "hit_at_1": safe_mean([1.0 if r["hit_at_1"] else 0.0 for r in test_results]),
        "hit_at_3": safe_mean([1.0 if r["hit_at_3"] else 0.0 for r in test_results]),
        "mrr": safe_mean([r["reciprocal_rank"] for r in test_results]),
        "ndcg_at_3": safe_mean([r["ndcg_at_3"] for r in test_results]),
        "results": test_results,
        "note": (
            "This is a preliminary profile-ranking sanity check using OSM pseudo-history records. "
            "It does not replace full route-choice evaluation against independently observed trips."
        ),
    }


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    all_points = load_all_probe_points()

    total_points = len(all_points)
    timestamped_points = sum(1 for p in all_points if p["timestamp"] is not None)

    print(f"\nTotal timestamped OSM trackpoints loaded: {timestamped_points}")

    pseudo_segments = build_pseudo_segments(all_points)
    useful_segments = filter_useful_segments(pseudo_segments)

    print(f"Pseudo-segments found: {len(pseudo_segments)}")
    print(f"Useful segments found: {len(useful_segments)}")

    records = []
    map_match_diags = []

    for idx, seg in enumerate(useful_segments):
        print(f"\nProcessing segment {idx}")
        print(
            f"  points={len(seg)}, "
            f"raw_dist={segment_distance_km(seg):.2f}km, "
            f"duration={segment_duration_min(seg):.2f}min, "
            f"speed={segment_speed_kmh(seg):.2f}km/h, "
            f"max_jump={max_segment_jump_m(seg):.1f}m"
        )

        record, diag = build_history_record_from_segment(seg, idx)
        map_match_diags.append(diag)

        if record:
            records.append(record)

    histories = {
        "osm_trace_toronto": records
    }

    HISTORY_OUTPUT_PATH.write_text(
        json.dumps(make_json_safe(histories), indent=2),
        encoding="utf-8"
    )

    quality_report = build_data_quality_report(
        total_points=total_points,
        timestamped_points=timestamped_points,
        pseudo_segments=pseudo_segments,
        useful_segments=useful_segments,
        map_match_diags=map_match_diags,
    )

    QUALITY_REPORT_PATH.write_text(
        json.dumps(make_json_safe(quality_report), indent=2),
        encoding="utf-8"
    )

    ranking_eval = evaluate_profile_ranking(records, max_tests=10)
    RANKING_EVAL_PATH.write_text(
        json.dumps(make_json_safe(ranking_eval), indent=2),
        encoding="utf-8"
    )

    print("\n==============================")
    print("OSM Trace History Build Complete")
    print("==============================")
    print(f"History output: {HISTORY_OUTPUT_PATH}")
    print(f"Quality report: {QUALITY_REPORT_PATH}")
    print(f"Ranking eval:   {RANKING_EVAL_PATH}")
    print(f"User ID: osm_trace_toronto")
    print(f"Records: {len(records)}")

    print("\nData / Map-Matching Quality Summary:")
    print(json.dumps({
        "timestamp_coverage": quality_report["data_quality"]["timestamp_coverage"],
        "pseudo_segments_found": quality_report["data_quality"]["pseudo_segments_found"],
        "useful_segments_found": quality_report["data_quality"]["useful_segments_found"],
        "useful_segment_rate": quality_report["data_quality"]["useful_segment_rate"],
        "map_match_success_rate": quality_report["map_matching_quality"]["map_match_success_rate"],
        "median_route_distance_ratio": quality_report["map_matching_quality"]["median_route_distance_ratio"],
        "median_gps_to_route_median_m": quality_report["map_matching_quality"]["median_gps_to_route_median_m"],
        "overall_prototype_usable": quality_report["overall_prototype_usable"],
    }, indent=2))

    print("\nProfile Ranking Evaluation Summary:")
    print(json.dumps({
        "num_tests": ranking_eval.get("num_tests"),
        "hit_at_1": ranking_eval.get("hit_at_1"),
        "hit_at_3": ranking_eval.get("hit_at_3"),
        "mrr": ranking_eval.get("mrr"),
        "ndcg_at_3": ranking_eval.get("ndcg_at_3"),
    }, indent=2))


if __name__ == "__main__":
    main()