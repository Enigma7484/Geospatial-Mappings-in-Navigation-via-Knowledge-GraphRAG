import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import numpy as np

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "user_histories.json"


def get_data_path() -> Path:
    env_path = os.getenv("GEOROUTE_USER_HISTORY_PATH")
    if env_path:
        p = Path(env_path)
        return p if p.is_absolute() else Path(__file__).resolve().parent.parent / p
    return DEFAULT_DATA_PATH


def parse_dt(dt_str: Optional[str]) -> datetime:
    if not dt_str or dt_str == "string":
        return datetime.utcnow()
    try:
        clean = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        return datetime.utcnow()


def get_time_bucket(hour: int) -> str:
    if 6 <= hour < 11:
        return "morning"
    if 11 <= hour < 16:
        return "afternoon"
    if 16 <= hour < 20:
        return "evening"
    return "night"


def get_season(month: int) -> str:
    if month in [12, 1, 2]:
        return "winter"
    if month in [3, 4, 5]:
        return "spring"
    if month in [6, 7, 8]:
        return "summer"
    return "fall"


def get_request_context(request_datetime: Optional[str]) -> Dict[str, Any]:
    dt = parse_dt(request_datetime)
    day_type = "weekday" if dt.weekday() < 5 else "weekend"
    time_bucket = get_time_bucket(dt.hour)
    season = get_season(dt.month)
    rush_hour = day_type == "weekday" and (7 <= dt.hour <= 9 or 16 <= dt.hour <= 18)
    return {
        "timestamp": dt.isoformat(),
        "hour": dt.hour,
        "day_name": dt.strftime("%A"),
        "day_type": day_type,
        "time_bucket": time_bucket,
        "season": season,
        "rush_hour": rush_hour,
    }


def load_user_history(user_id: str) -> List[Dict[str, Any]]:
    data_path = get_data_path()
    if not data_path.exists():
        return []
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get(user_id, [])


def enrich_history_context(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []
    for rec in records:
        dt = parse_dt(rec.get("timestamp"))
        rec_ctx = {
            **rec,
            "context": {
                "hour": dt.hour,
                "day_type": "weekday" if dt.weekday() < 5 else "weekend",
                "time_bucket": get_time_bucket(dt.hour),
                "season": get_season(dt.month),
                "rush_hour": (dt.weekday() < 5 and (7 <= dt.hour <= 9 or 16 <= dt.hour <= 18)),
            },
        }
        enriched.append(rec_ctx)
    return enriched


def context_match_score(entry_ctx: Dict[str, Any], current_ctx: Dict[str, Any]) -> int:
    score = 0
    if entry_ctx["time_bucket"] == current_ctx["time_bucket"]:
        score += 3
    if entry_ctx["day_type"] == current_ctx["day_type"]:
        score += 2
    if entry_ctx["season"] == current_ctx["season"]:
        score += 1
    if entry_ctx["rush_hour"] == current_ctx["rush_hour"]:
        score += 2
    return score


def select_contextual_history(records: List[Dict[str, Any]], current_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not records:
        return []
    enriched = enrich_history_context(records)
    scored = [(context_match_score(rec["context"], current_ctx), rec) for rec in enriched]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]
    if best_score <= 0:
        return enriched
    selected = [rec for s, rec in scored if s >= max(best_score - 1, 1)]
    return enriched if len(selected) < 3 else selected


def safe_mean(records: List[Dict[str, Any]], feature: str, default: float = 0.0) -> float:
    vals = []
    for rec in records:
        val = rec.get("features", {}).get(feature)
        if val is not None:
            try:
                vals.append(float(val))
            except Exception:
                pass
    return float(np.mean(vals)) if vals else default


def build_dynamic_profile(records: List[Dict[str, Any]], current_ctx: Dict[str, Any]) -> Dict[str, Any]:
    selected = select_contextual_history(records, current_ctx)
    avg = {
        "distance_km": safe_mean(selected, "distance_km", 2.0),
        "major_pct": safe_mean(selected, "major_pct", 20.0),
        "walk_pct": safe_mean(selected, "walk_pct", 50.0),
        "residential_pct": safe_mean(selected, "residential_pct", 20.0),
        "service_pct": safe_mean(selected, "service_pct", 5.0),
        "intersections": safe_mean(selected, "intersections", 50.0),
        "turns": safe_mean(selected, "turns", 10.0),
        "park_near_pct": safe_mean(selected, "park_near_pct", 10.0),
        "safety_score": safe_mean(selected, "safety_score", 50.0),
        "lit_pct": safe_mean(selected, "lit_pct", 0.0),
        "signal_cnt": safe_mean(selected, "signal_cnt", 10.0),
        "crossing_cnt": safe_mean(selected, "crossing_cnt", 10.0),
        "tunnel_m": safe_mean(selected, "tunnel_m", 0.0),
    }
    weights = {
        "park_near_pct": 0.5 + avg["park_near_pct"] / 100.0,
        "safety_score": 0.4 + avg["safety_score"] / 100.0,
        "walk_pct": 0.4 + avg["walk_pct"] / 100.0,
        "residential_pct": 0.3 + avg["residential_pct"] / 100.0,
        "major_pct": 0.6 + (1.0 - min(avg["major_pct"] / 100.0, 1.0)),
        "service_pct": 0.3 + (1.0 - min(avg["service_pct"] / 20.0, 1.0)),
        "turns": 0.5 + (1.0 - min(avg["turns"] / 25.0, 1.0)),
        "intersections": 0.5 + (1.0 - min(avg["intersections"] / 120.0, 1.0)),
        "distance_km": 0.5 + (1.0 - min(avg["distance_km"] / 6.0, 1.0)),
        "lit_pct": 0.2 + avg["lit_pct"] / 100.0,
        "signal_cnt": 0.2 + (1.0 - min(avg["signal_cnt"] / 40.0, 1.0)),
        "crossing_cnt": 0.2 + (1.0 - min(avg["crossing_cnt"] / 40.0, 1.0)),
        "tunnel_m": 0.3 + (1.0 - min(avg["tunnel_m"] / 300.0, 1.0)),
    }
    if current_ctx["rush_hour"]:
        weights["major_pct"] += 0.4
        weights["intersections"] += 0.25
        weights["signal_cnt"] += 0.25
        weights["crossing_cnt"] += 0.25
    if current_ctx["time_bucket"] in {"evening", "night"}:
        weights["safety_score"] += 0.4
        weights["lit_pct"] += 0.4
        weights["tunnel_m"] += 0.3
    if current_ctx["day_type"] == "weekend":
        weights["park_near_pct"] += 0.3
        weights["residential_pct"] += 0.2
    if current_ctx["season"] == "summer":
        weights["park_near_pct"] += 0.2
    if current_ctx["season"] == "winter":
        weights["distance_km"] += 0.2
        weights["turns"] += 0.2
        weights["intersections"] += 0.2
    traits = []
    if weights["park_near_pct"] >= 1.0:
        traits.append("scenic/green preference")
    if weights["safety_score"] >= 1.0 or weights["lit_pct"] >= 0.8:
        traits.append("safety-sensitive")
    if weights["major_pct"] >= 1.2:
        traits.append("avoids busy roads")
    if weights["turns"] >= 1.0 or weights["intersections"] >= 1.0:
        traits.append("prefers simpler navigation")
    if weights["distance_km"] >= 1.0:
        traits.append("prefers efficient/direct routes")
    return {
        "context": current_ctx,
        "num_history_records": len(records),
        "num_context_records": len(selected),
        "avg_features": avg,
        "weights": weights,
        "traits": traits,
    }


def summarize_profile(profile: Dict[str, Any]) -> str:
    ctx = profile["context"]
    avg = profile["avg_features"]
    traits = profile["traits"]
    ctx_line = f"For {ctx['day_type']} {ctx['time_bucket']} trips in {ctx['season']}" + (" during rush hour" if ctx["rush_hour"] else "")
    trait_text = ", ".join(traits) if traits else "balanced route preferences"
    return (
        f"{ctx_line}, this user appears to have {trait_text}. "
        f"Based on {profile['num_context_records']} relevant historical trips "
        f"(out of {profile['num_history_records']} total), they tend to choose routes "
        f"with about {avg['park_near_pct']:.1f}% park proximity, "
        f"{avg['major_pct']:.1f}% major-road exposure, "
        f"{avg['turns']:.1f} turns, "
        f"{avg['intersections']:.1f} intersections, and "
        f"a safety proxy of {avg['safety_score']:.1f}/100."
    )


def _minmax(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=float)
    mn = arr.min()
    mx = arr.max()
    if np.isclose(mx, mn):
        return np.ones_like(arr) * 0.5
    return (arr - mn) / (mx - mn)


def score_routes_with_profile(route_feature_dicts: List[Dict[str, Any]], profile: Dict[str, Any]) -> np.ndarray:
    weights = profile["weights"]
    distance = _minmax(np.array([r["distance_km"] for r in route_feature_dicts]))
    major = _minmax(np.array([r["major_pct"] for r in route_feature_dicts]))
    walk = _minmax(np.array([r["walk_pct"] for r in route_feature_dicts]))
    residential = _minmax(np.array([r["residential_pct"] for r in route_feature_dicts]))
    service = _minmax(np.array([r["service_pct"] for r in route_feature_dicts]))
    intersections = _minmax(np.array([r["intersections"] for r in route_feature_dicts]))
    turns = _minmax(np.array([r["turns"] for r in route_feature_dicts]))
    park = _minmax(np.array([r["park_near_pct"] for r in route_feature_dicts]))
    safety = _minmax(np.array([r["safety_score"] for r in route_feature_dicts]))
    lit = _minmax(np.array([r["lit_pct"] for r in route_feature_dicts]))
    signals = _minmax(np.array([r["signal_cnt"] for r in route_feature_dicts]))
    crossings = _minmax(np.array([r["crossing_cnt"] for r in route_feature_dicts]))
    tunnel = _minmax(np.array([r["tunnel_m"] for r in route_feature_dicts]))
    raw = (
        weights["park_near_pct"] * park
        + weights["safety_score"] * safety
        + weights["walk_pct"] * walk
        + weights["residential_pct"] * residential
        + weights["lit_pct"] * lit
        - weights["major_pct"] * major
        - weights["service_pct"] * service
        - weights["turns"] * turns
        - weights["intersections"] * intersections
        - weights["distance_km"] * distance
        - weights["signal_cnt"] * signals
        - weights["crossing_cnt"] * crossings
        - weights["tunnel_m"] * tunnel
    )
    return _minmax(raw)
