import json
import math
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

BACKEND_ROOT = Path(__file__).resolve().parent.parent
GEOLIFE_DATA_DIR = BACKEND_ROOT / "geolife_raw" / "Data"
OUTPUT_PATH = BACKEND_ROOT / "data" / "user_histories.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def count_turns(points: List[Dict[str, Any]], threshold_deg: float = 55.0, min_segment_m: float = 20.0) -> int:
    if len(points) < 3:
        return 0
    bearings = []
    anchor = points[0]
    for p in points[1:]:
        d = haversine_m(anchor["lat"], anchor["lon"], p["lat"], p["lon"])
        if d < min_segment_m:
            continue
        bearings.append(bearing_deg(anchor["lat"], anchor["lon"], p["lat"], p["lon"]))
        anchor = p
    turns = 0
    for i in range(1, len(bearings)):
        diff = abs(bearings[i] - bearings[i - 1])
        diff = min(diff, 360 - diff)
        if diff > threshold_deg:
            turns += 1
    return turns


def total_distance_km(points: List[Dict[str, Any]]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(haversine_m(points[i]["lat"], points[i]["lon"], points[i+1]["lat"], points[i+1]["lon"]) for i in range(len(points)-1)) / 1000.0


def parse_plt_file(path: Path) -> List[Dict[str, Any]]:
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


def infer_mode_from_points(points: List[Dict[str, Any]]) -> str:
    if len(points) < 2:
        return "unknown"
    speeds = []
    for i in range(len(points)-1):
        p1, p2 = points[i], points[i+1]
        dt = (p2["timestamp"] - p1["timestamp"]).total_seconds()
        if dt <= 0:
            continue
        dist_m = haversine_m(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
        speed = (dist_m / 1000.0) / (dt / 3600.0)
        if 0 <= speed <= 150:
            speeds.append(speed)
    if not speeds:
        return "unknown"
    dist_km = total_distance_km(points)
    duration_hr = max((points[-1]["timestamp"] - points[0]["timestamp"]).total_seconds() / 3600.0, 0.001)
    avg_speed = dist_km / duration_hr
    speeds = sorted(speeds)
    median_speed = speeds[len(speeds)//2]
    p90_speed = speeds[int(0.9 * (len(speeds)-1))]
    if 0.8 <= avg_speed <= 7.0 and median_speed <= 7.5 and p90_speed <= 12.0:
        return "walk_inferred"
    if 7.0 < avg_speed <= 20.0:
        return "bike_or_slow_vehicle_inferred"
    if avg_speed > 20.0:
        return "motorized_inferred"
    return "unknown"


def build_history_record(points: List[Dict[str, Any]], mode: Optional[str]) -> Optional[Dict[str, Any]]:
    if len(points) < 10:
        return None
    start, end = points[0]["timestamp"], points[-1]["timestamp"]
    duration_min = max((end - start).total_seconds() / 60.0, 0.1)
    dist_km = total_distance_km(points)
    if dist_km < 0.2:
        return None
    avg_speed_kmh = dist_km / (duration_min / 60.0)
    turns = count_turns(points)
    capped_turns = min(turns, 30)
    features = {
        "distance_km": round(dist_km, 3),
        "major_pct": 15.0,
        "walk_pct": 60.0 if mode in ["walk", "walk_inferred"] else 40.0,
        "residential_pct": 20.0,
        "service_pct": 5.0,
        "intersections": min(max(1, int(capped_turns * 1.5)), 60),
        "turns": capped_turns,
        "park_near_pct": 10.0,
        "safety_score": 50.0,
        "lit_pct": 0.0,
        "signal_cnt": 0,
        "crossing_cnt": 0,
        "tunnel_m": 0.0,
        "duration_min": round(duration_min, 2),
        "avg_speed_kmh": round(avg_speed_kmh, 2),
    }
    return {
        "timestamp": start.isoformat(),
        "mode": mode or "unknown",
        "origin": {"lat": points[0]["lat"], "lon": points[0]["lon"]},
        "destination": {"lat": points[-1]["lat"], "lon": points[-1]["lon"]},
        "features": features,
    }


def build_user_histories(max_users: int = 30, target_modes=None, max_trips_per_user: int = 40):
    if target_modes is None:
        target_modes = ["walk"]
    if not GEOLIFE_DATA_DIR.exists():
        raise FileNotFoundError(f"GeoLife data folder not found: {GEOLIFE_DATA_DIR}")
    histories = {}
    user_dirs = sorted([p for p in GEOLIFE_DATA_DIR.iterdir() if p.is_dir()])
    print(f"Found {len(user_dirs)} user folders.")
    for user_dir in user_dirs[:max_users]:
        user_id = f"geolife_{user_dir.name}"
        traj_dir = user_dir / "Trajectory"
        if not traj_dir.exists():
            continue
        records = []
        for plt_path in sorted(traj_dir.glob("*.plt")):
            points = parse_plt_file(plt_path)
            if len(points) < 10:
                continue
            mode = infer_mode_from_points(points)
            if "walk" in target_modes and mode != "walk_inferred":
                continue
            rec = build_history_record(points, mode)
            if rec:
                records.append(rec)
            if len(records) >= max_trips_per_user:
                break
        if records:
            histories[user_id] = records
            print(f"{user_id}: {len(records)} records")
    return histories


if __name__ == "__main__":
    histories = build_user_histories(max_users=30, target_modes=["walk"], max_trips_per_user=40)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(histories, f, indent=2)
    print(f"\nSaved histories to: {OUTPUT_PATH}")
    print(f"Users with records: {len(histories)}")
    if histories:
        first = next(iter(histories))
        print(f"Example user_id: {first}")
        print(f"Example records: {len(histories[first])}")
