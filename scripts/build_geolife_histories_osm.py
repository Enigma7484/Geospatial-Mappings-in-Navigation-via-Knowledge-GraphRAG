import json
import math
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import osmnx as ox
import networkx as nx

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_ROOT))
from app.routing import compute_route_features, get_parks_union

GEOLIFE_DATA_DIR = BACKEND_ROOT / "geolife_raw" / "Data"
OUTPUT_PATH = BACKEND_ROOT / "data" / "user_histories_osm.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def total_distance_km(points):
    if len(points) < 2:
        return 0.0
    return sum(haversine_m(points[i]["lat"], points[i]["lon"], points[i+1]["lat"], points[i+1]["lon"]) for i in range(len(points)-1)) / 1000.0


def parse_plt_file(path: Path):
    points = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()[6:]
    for line in lines:
        parts = line.strip().split(",")
        if len(parts) < 7:
            continue
        try:
            ts = datetime.strptime(f"{parts[5]} {parts[6]}", "%Y-%m-%d %H:%M:%S")
            points.append({"lat": float(parts[0]), "lon": float(parts[1]), "timestamp": ts})
        except Exception:
            continue
    return points


def infer_mode_from_points(points):
    if len(points) < 2:
        return "unknown"
    speeds = []
    for i in range(len(points)-1):
        p1, p2 = points[i], points[i+1]
        dt = (p2["timestamp"] - p1["timestamp"]).total_seconds()
        if dt <= 0:
            continue
        d = haversine_m(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
        s = (d / 1000.0) / (dt / 3600.0)
        if 0 <= s <= 150:
            speeds.append(s)
    if not speeds:
        return "unknown"
    dist_km = total_distance_km(points)
    duration_hr = max((points[-1]["timestamp"] - points[0]["timestamp"]).total_seconds() / 3600.0, 0.001)
    avg = dist_km / duration_hr
    speeds = sorted(speeds)
    median = speeds[len(speeds)//2]
    p90 = speeds[int(0.9 * (len(speeds)-1))]
    if 0.8 <= avg <= 7.0 and median <= 7.5 and p90 <= 12.0:
        return "walk_inferred"
    if 7.0 < avg <= 20.0:
        return "bike_or_slow_vehicle_inferred"
    if avg > 20.0:
        return "motorized_inferred"
    return "unknown"


def simplify_points_by_distance(points, min_gap_m=60.0):
    if not points:
        return []
    out, last = [points[0]], points[0]
    for p in points[1:-1]:
        if haversine_m(last["lat"], last["lon"], p["lat"], p["lon"]) >= min_gap_m:
            out.append(p); last = p
    if points[-1] != out[-1]:
        out.append(points[-1])
    return out


def trajectory_bbox(points, buffer_deg=0.015):
    lats, lons = [p["lat"] for p in points], [p["lon"] for p in points]
    return max(lats)+buffer_deg, min(lats)-buffer_deg, max(lons)+buffer_deg, min(lons)-buffer_deg

_graph_cache = {}

def get_trip_graph(points):
    north, south, east, west = trajectory_bbox(points)
    key = (round(north, 2), round(south, 2), round(east, 2), round(west, 2))
    if key in _graph_cache:
        return _graph_cache[key]
    print(f"  Building OSM graph for bbox: {key}")
    try:
        G = ox.graph_from_bbox(north, south, east, west, network_type="walk", simplify=True)
    except TypeError:
        G = ox.graph_from_bbox((north, south, east, west), network_type="walk", simplify=True)
    G = ox.distance.add_edge_lengths(G)
    try:
        G = ox.bearing.add_edge_bearings(G)
    except Exception:
        try: G = ox.add_edge_bearings(G)
        except Exception: pass
    G_proj = ox.project_graph(G)
    center = (sum(p["lat"] for p in points)/len(points), sum(p["lon"] for p in points)/len(points))
    parks_union = get_parks_union(center, 2500, G_proj)
    _graph_cache[key] = (G, G_proj, parks_union)
    return G, G_proj, parks_union


def map_match_points_to_nodes(G, points):
    nodes = ox.distance.nearest_nodes(G, X=[p["lon"] for p in points], Y=[p["lat"] for p in points])
    out = []
    for n in nodes:
        if not out or int(n) != out[-1]:
            out.append(int(n))
    return out


def reconstruct_osm_route(G, matched_nodes):
    if len(matched_nodes) < 2:
        return None
    full = []
    for a, b in zip(matched_nodes[:-1], matched_nodes[1:]):
        if a == b:
            continue
        try:
            seg = nx.shortest_path(G, a, b, weight="length")
        except Exception:
            continue
        if not seg:
            continue
        full.extend(seg if not full else seg[1:])
    cleaned = []
    for n in full:
        if not cleaned or n != cleaned[-1]:
            cleaned.append(n)
    return cleaned if len(cleaned) >= 2 else None


def build_osm_history_record(points, mode):
    if len(points) < 10:
        return None
    raw_dist_km = total_distance_km(points)
    if raw_dist_km < 0.2:
        return None
    simplified = simplify_points_by_distance(points)
    if len(simplified) < 3:
        return None
    try:
        G, G_proj, parks_union = get_trip_graph(simplified)
        matched = map_match_points_to_nodes(G, simplified)
        osm_route = reconstruct_osm_route(G, matched)
        if osm_route is None:
            return None
        feat = compute_route_features(G, G_proj, parks_union, osm_route)
        start, end = points[0]["timestamp"], points[-1]["timestamp"]
        duration_min = max((end - start).total_seconds()/60.0, 0.1)
        features = {k: feat[k] for k in ["distance_km", "major_pct", "walk_pct", "residential_pct", "service_pct", "intersections", "turns", "park_near_pct", "safety_score", "lit_pct", "signal_cnt", "crossing_cnt", "tunnel_m"]}
        features.update({"raw_gps_distance_km": round(raw_dist_km, 3), "duration_min": round(duration_min, 2), "avg_speed_kmh": round(raw_dist_km/(duration_min/60.0), 2), "matched_nodes": len(matched), "osm_route_nodes": len(osm_route)})
        return {"timestamp": start.isoformat(), "mode": mode, "origin": {"lat": points[0]["lat"], "lon": points[0]["lon"]}, "destination": {"lat": points[-1]["lat"], "lon": points[-1]["lon"]}, "features": features}
    except Exception as e:
        print(f"  OSM enrichment failed: {repr(e)}")
        return None


def build_histories_osm(max_users=5, max_trips_per_user=8):
    if not GEOLIFE_DATA_DIR.exists():
        raise FileNotFoundError(f"GeoLife data folder not found: {GEOLIFE_DATA_DIR}")
    histories = {}
    users = sorted([p for p in GEOLIFE_DATA_DIR.iterdir() if p.is_dir()])
    print(f"Found {len(users)} user folders.")
    for user_dir in users[:max_users]:
        user_id = f"geolife_osm_{user_dir.name}"
        traj = user_dir / "Trajectory"
        if not traj.exists():
            continue
        records = []
        print(f"\nUser {user_id}: scanning trajectories")
        for plt in sorted(traj.glob("*.plt")):
            points = parse_plt_file(plt)
            if len(points) < 10:
                continue
            mode = infer_mode_from_points(points)
            if mode != "walk_inferred":
                continue
            print(f"  Processing {plt.name} ({len(points)} GPS points)")
            rec = build_osm_history_record(points, mode)
            if rec:
                records.append(rec)
                print(f"  Added record: dist={rec['features']['distance_km']:.2f}km, park={rec['features']['park_near_pct']:.1f}%, safety={rec['features']['safety_score']:.1f}")
            if len(records) >= max_trips_per_user:
                break
        if records:
            histories[user_id] = records
            print(f"{user_id}: {len(records)} OSM-enriched records")
    return histories


if __name__ == "__main__":
    histories = build_histories_osm(max_users=5, max_trips_per_user=8)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(histories, f, indent=2)
    print("\n==============================")
    print("Saved OSM-enriched histories")
    print("==============================")
    print(f"Path: {OUTPUT_PATH}")
    print(f"Users with records: {len(histories)}")
    if histories:
        first = next(iter(histories))
        print(f"Example user_id: {first}")
        print(f"Example records: {len(histories[first])}")
