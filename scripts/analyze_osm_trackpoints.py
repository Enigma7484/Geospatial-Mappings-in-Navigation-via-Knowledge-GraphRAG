import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROBE_DIR = BACKEND_ROOT / "data" / "osm_history_probe"
OUTPUT_PATH = PROBE_DIR / "trackpoints_analysis.json"


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


def parse_time(t: Optional[str]):
    if not t:
        return None

    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00"))
    except Exception:
        return None


def parse_gpx_file(path: Path) -> Dict[str, Any]:
    root = ET.parse(path).getroot()

    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    tracks = []
    all_points = []

    # Try track/segment structure first
    for trk_i, trk in enumerate(root.findall(f"{ns}trk")):
        for seg_i, seg in enumerate(trk.findall(f"{ns}trkseg")):
            seg_points = []

            for pt in seg.findall(f"{ns}trkpt"):
                lat = pt.attrib.get("lat")
                lon = pt.attrib.get("lon")
                time_el = pt.find(f"{ns}time")

                if lat is None or lon is None:
                    continue

                p = {
                    "lat": float(lat),
                    "lon": float(lon),
                    "timestamp": time_el.text if time_el is not None else None,
                    "track_index": trk_i,
                    "segment_index": seg_i,
                }

                seg_points.append(p)
                all_points.append(p)

            if seg_points:
                tracks.append(seg_points)

    # Fallback: any trkpt anywhere
    if not all_points:
        for pt in root.iter(f"{ns}trkpt"):
            lat = pt.attrib.get("lat")
            lon = pt.attrib.get("lon")
            time_el = pt.find(f"{ns}time")

            if lat is None or lon is None:
                continue

            all_points.append({
                "lat": float(lat),
                "lon": float(lon),
                "timestamp": time_el.text if time_el is not None else None,
                "track_index": None,
                "segment_index": None,
            })

    return {
        "file": str(path),
        "num_points": len(all_points),
        "num_tracks_or_segments": len(tracks),
        "points": all_points,
        "tracks": tracks,
    }


def summarize_points(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not points:
        return {
            "num_points": 0,
            "has_timestamps": False,
        }

    times = [parse_time(p.get("timestamp")) for p in points]
    valid_times = [t for t in times if t is not None]

    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]

    summary = {
        "num_points": len(points),
        "has_timestamps": len(valid_times) > 0,
        "timestamp_coverage_pct": round(100 * len(valid_times) / len(points), 2),
        "bbox": {
            "south": min(lats),
            "north": max(lats),
            "west": min(lons),
            "east": max(lons),
        },
    }

    if valid_times:
        summary["time_min"] = min(valid_times).isoformat()
        summary["time_max"] = max(valid_times).isoformat()

    return summary


def build_pseudo_segments(points: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    If OSM does not give clean track IDs, create approximate segments using:
    - timestamp gaps
    - spatial jumps

    This is not true user history. It is only a trace-continuity heuristic.
    """
    parsed = []
    for p in points:
        t = parse_time(p.get("timestamp"))
        if t is not None:
            parsed.append({**p, "_dt": t})

    if len(parsed) < 2:
        return []

    parsed.sort(key=lambda p: p["_dt"])

    segments = []
    current = [parsed[0]]

    for prev, curr in zip(parsed[:-1], parsed[1:]):
        gap_min = (curr["_dt"] - prev["_dt"]).total_seconds() / 60.0
        dist_m = haversine_m(prev["lat"], prev["lon"], curr["lat"], curr["lon"])

        # Split if time gap is too big or spatial jump is too large
        if gap_min > 10 or dist_m > 500:
            if len(current) >= 5:
                segments.append(current)
            current = [curr]
        else:
            current.append(curr)

    if len(current) >= 5:
        segments.append(current)

    return segments


def summarize_segment(seg: List[Dict[str, Any]]) -> Dict[str, Any]:
    dist_m = 0.0

    for a, b in zip(seg[:-1], seg[1:]):
        dist_m += haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])

    start = seg[0]["_dt"]
    end = seg[-1]["_dt"]
    duration_min = max((end - start).total_seconds() / 60.0, 0.01)
    avg_speed_kmh = (dist_m / 1000.0) / (duration_min / 60.0)

    return {
        "num_points": len(seg),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "duration_min": round(duration_min, 2),
        "distance_km": round(dist_m / 1000.0, 3),
        "avg_speed_kmh": round(avg_speed_kmh, 2),
        "origin": {
            "lat": seg[0]["lat"],
            "lon": seg[0]["lon"],
        },
        "destination": {
            "lat": seg[-1]["lat"],
            "lon": seg[-1]["lon"],
        },
    }


def main():
    gpx_files = sorted(PROBE_DIR.glob("osm_trackpoints_page_*.gpx"))

    if not gpx_files:
        print(f"No GPX files found in {PROBE_DIR}")
        return

    all_points = []
    file_summaries = []

    for path in gpx_files:
        parsed = parse_gpx_file(path)
        all_points.extend(parsed["points"])

        file_summaries.append({
            "file": str(path),
            "num_points": parsed["num_points"],
            "num_tracks_or_segments": parsed["num_tracks_or_segments"],
            "point_summary": summarize_points(parsed["points"]),
        })

    overall = summarize_points(all_points)

    pseudo_segments = build_pseudo_segments(all_points)
    segment_summaries = [summarize_segment(s) for s in pseudo_segments]

    # Keep useful movement-looking segments
    useful_segments = [
        s for s in segment_summaries
        if s["distance_km"] >= 0.2 and 1 <= s["avg_speed_kmh"] <= 80
    ]

    output = {
        "files_analyzed": len(gpx_files),
        "file_summaries": file_summaries,
        "overall": overall,
        "pseudo_segments_found": len(pseudo_segments),
        "useful_segments_found": len(useful_segments),
        "useful_segments_preview": useful_segments[:25],
        "interpretation": {
            "if_num_tracks_or_segments_is_zero": (
                "The OSM endpoint is likely returning area-level trackpoints without clean trace grouping."
            ),
            "if_useful_segments_found_is_high": (
                "There may be enough temporal continuity to build area-level movement-history signals."
            ),
            "caution": (
                "Pseudo-segments are not guaranteed to correspond to one user or one real trip."
            ),
        },
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("\nAnalysis complete.")
    print(json.dumps({
        "files_analyzed": output["files_analyzed"],
        "total_points": output["overall"]["num_points"],
        "has_timestamps": output["overall"]["has_timestamps"],
        "timestamp_coverage_pct": output["overall"].get("timestamp_coverage_pct"),
        "pseudo_segments_found": output["pseudo_segments_found"],
        "useful_segments_found": output["useful_segments_found"],
        "output_path": str(OUTPUT_PATH),
    }, indent=2))


if __name__ == "__main__":
    main()