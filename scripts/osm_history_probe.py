import argparse
import json
import time
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = BACKEND_ROOT / "data" / "osm_history_probe"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OSM_API = "https://api.openstreetmap.org/api/0.6/trackpoints"
TORONTO_UOFT_BBOX = {"west": -79.405, "south": 43.645, "east": -79.375, "north": 43.670}


def bbox_to_string(bbox: Dict[str, float]) -> str:
    return f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}"


def fetch_trackpoints_page(bbox: Dict[str, float], page: int = 0) -> str:
    params = {"bbox": bbox_to_string(bbox), "page": page}
    headers = {"User-Agent": "georoute-research-probe/0.1 (student research)", "Accept": "application/gpx+xml, application/xml, text/xml"}
    print(f"Fetching OSM GPS trackpoints page={page} bbox={params['bbox']}")
    r = requests.get(OSM_API, params=params, headers=headers, timeout=60)
    r.raise_for_status()
    return r.text


def parse_gpx_trackpoints(xml_text: str) -> List[Dict[str, Any]]:
    points = []
    root = ET.fromstring(xml_text)
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    for trkpt in root.iter(f"{ns}trkpt"):
        lat, lon = trkpt.attrib.get("lat"), trkpt.attrib.get("lon")
        if lat is None or lon is None:
            continue
        time_el = trkpt.find(f"{ns}time")
        points.append({"lat": float(lat), "lon": float(lon), "timestamp": time_el.text if time_el is not None else None})
    return points


def probe_trackpoints(bbox: Dict[str, float], max_pages: int = 3) -> Dict[str, Any]:
    all_points, page_summaries = [], []
    for page in range(max_pages):
        try:
            xml_text = fetch_trackpoints_page(bbox, page=page)
            raw_path = OUT_DIR / f"osm_trackpoints_page_{page}.gpx"
            raw_path.write_text(xml_text, encoding="utf-8")
            points = parse_gpx_trackpoints(xml_text)
            print(f"Page {page}: {len(points)} points")
            page_summaries.append({"page": page, "raw_file": str(raw_path), "num_points": len(points)})
            all_points.extend(points)
            time.sleep(1)
            if len(points) == 0:
                break
        except Exception as e:
            print(f"Failed page {page}: {repr(e)}")
            page_summaries.append({"page": page, "error": repr(e)})
            break
    preview_path = OUT_DIR / "trackpoints_preview.json"
    preview_path.write_text(json.dumps(all_points[:1000], indent=2), encoding="utf-8")
    summary = {"bbox": bbox, "pages_requested": max_pages, "pages": page_summaries, "total_points_parsed": len(all_points), "preview_json": str(preview_path), "note": "OSM public GPS trackpoints may not provide clean per-user route history; this probe checks area-level trace usefulness."}
    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nSaved:")
    print(f"- {summary_path}")
    print(f"- {preview_path}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe OSM public GPS trackpoints for exploratory pseudo-history signals. "
            "These public trackpoints are area-level movement signals, not clean per-user histories."
        )
    )
    parser.add_argument("--max-pages", type=int, default=3, help="Number of OSM trackpoint pages to request.")
    parser.add_argument("--west", type=float, default=TORONTO_UOFT_BBOX["west"])
    parser.add_argument("--south", type=float, default=TORONTO_UOFT_BBOX["south"])
    parser.add_argument("--east", type=float, default=TORONTO_UOFT_BBOX["east"])
    parser.add_argument("--north", type=float, default=TORONTO_UOFT_BBOX["north"])
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    bbox = {"west": args.west, "south": args.south, "east": args.east, "north": args.north}
    print(json.dumps(probe_trackpoints(bbox, max_pages=args.max_pages), indent=2))
