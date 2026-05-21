import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib import error, request

import numpy as np


_model = None
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Windows can fail to initialize PyTorch DLLs when the transformer stack imports
# torch indirectly under heavier CPU-thread defaults. Keep the SBERT baseline
# deterministic and CPU-only for the research prototype.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _read_project_env_var(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, raw_value = clean.split("=", 1)
        if key.strip() == name:
            return raw_value.strip().strip('"').strip("'") or None
    return None


def get_prompt_ranker() -> str:
    ranker = os.getenv("GEOROUTE_PROMPT_RANKER", "auto").strip().lower()
    if ranker not in {"auto", "gemini", "sbert", "lexical"}:
        return "auto"
    if ranker == "auto":
        return "gemini" if get_gemini_api_key() else "sbert"
    return ranker


def get_gemini_api_key() -> str | None:
    return _read_project_env_var("GEMINI_API_KEY") or _read_project_env_var("GOOGLE_API_KEY")


def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def get_model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(1)
        _model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    return _model


def _minmax(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    if scores.size == 0:
        return scores
    mn = scores.min()
    mx = scores.max()
    if np.isclose(mx, mn):
        return np.ones_like(scores) * 0.5
    return (scores - mn) / (mx - mn)


def lexical_rank_route_texts(route_texts: list[str], user_pref: str) -> np.ndarray:
    query_terms = Counter(re.findall(r"[a-z0-9]+", user_pref.lower()))
    if not query_terms:
        return np.ones(len(route_texts), dtype=float) * 0.5

    scores = []
    query_norm = np.sqrt(sum(v * v for v in query_terms.values()))
    for text in route_texts:
        route_terms = Counter(re.findall(r"[a-z0-9]+", text.lower()))
        route_norm = np.sqrt(sum(v * v for v in route_terms.values()))
        if route_norm == 0:
            scores.append(0.0)
            continue
        dot = sum(query_terms[t] * route_terms.get(t, 0) for t in query_terms)
        scores.append(dot / (query_norm * route_norm))
    return _minmax(np.asarray(scores, dtype=float))


def sbert_rank_route_texts(route_texts: list[str], user_pref: str) -> np.ndarray:
    model = get_model()
    emb_routes = model.encode(route_texts, normalize_embeddings=True)
    emb_user = model.encode([user_pref], normalize_embeddings=True)
    return np.asarray(emb_routes @ emb_user[0], dtype=float)


def _route_payload(route_feature_dicts: list[dict[str, Any]], route_texts: list[str]) -> list[dict[str, Any]]:
    payload = []
    for idx, (features, text) in enumerate(zip(route_feature_dicts, route_texts)):
        payload.append(
            {
                "route_index": idx,
                "summary": text,
                "features": {
                    "distance_km": features.get("distance_km"),
                    "major_pct": features.get("major_pct"),
                    "walk_pct": features.get("walk_pct"),
                    "residential_pct": features.get("residential_pct"),
                    "service_pct": features.get("service_pct"),
                    "intersections": features.get("intersections"),
                    "turns": features.get("turns"),
                    "park_near_pct": features.get("park_near_pct"),
                    "min_park_dist_m": features.get("min_park_dist_m"),
                    "safety_score": features.get("safety_score"),
                    "lit_pct": features.get("lit_pct"),
                    "signal_cnt": features.get("signal_cnt"),
                    "crossing_cnt": features.get("crossing_cnt"),
                    "tunnel_m": features.get("tunnel_m"),
                },
            }
        )
    return payload


def _extract_json_object(text: str) -> dict[str, Any]:
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean)
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _parse_gemini_scores(response_body: dict[str, Any], route_count: int) -> np.ndarray:
    candidates = response_body.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no candidates.")

    parts = candidates[0].get("content", {}).get("parts") or []
    text = "\n".join(str(part.get("text", "")) for part in parts).strip()
    if not text:
        raise ValueError("Gemini returned an empty text response.")

    parsed = _extract_json_object(text)
    raw_scores = parsed.get("scores")
    if not isinstance(raw_scores, list):
        raise ValueError("Gemini response did not contain a scores list.")

    scores = np.zeros(route_count, dtype=float)
    seen = set()
    for item in raw_scores:
        if not isinstance(item, dict):
            continue
        idx = int(item.get("route_index"))
        if idx < 0 or idx >= route_count:
            continue
        scores[idx] = float(item.get("score"))
        seen.add(idx)

    if len(seen) != route_count:
        raise ValueError(f"Gemini scored {len(seen)} of {route_count} routes.")
    return _minmax(scores)


def gemini_rank_routes(
    route_feature_dicts: list[dict[str, Any]],
    route_texts: list[str],
    user_pref: str,
) -> np.ndarray:
    api_key = get_gemini_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    model = get_gemini_model()
    prompt = {
        "user_preference": user_pref,
        "routes": _route_payload(route_feature_dicts, route_texts),
        "instructions": (
            "Score each route from 0 to 1 for how well it satisfies the user preference. "
            "Use the route features as the source of truth. Return JSON only in the exact "
            "shape {\"scores\":[{\"route_index\":0,\"score\":0.0,\"reason\":\"...\"}]}."
        ),
    }
    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "You are a route preference ranking service. "
                            "Do not include markdown. Return strict JSON only.\n\n"
                            f"{json.dumps(prompt, ensure_ascii=False)}"
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    data = json.dumps(body).encode("utf-8")
    req = request.Request(
        GEMINI_ENDPOINT.format(model=model),
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))) as resp:
            response_body = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Gemini API request failed: {exc.reason}") from exc

    return _parse_gemini_scores(response_body, len(route_texts))


def rank_route_texts(
    route_texts: list[str],
    user_pref: str,
    route_feature_dicts: list[dict[str, Any]] | None = None,
) -> np.ndarray:
    ranker = get_prompt_ranker()

    if ranker == "gemini":
        if route_feature_dicts is None:
            route_feature_dicts = [{"summary": text} for text in route_texts]
        return gemini_rank_routes(route_feature_dicts, route_texts, user_pref)
    if ranker == "lexical":
        return lexical_rank_route_texts(route_texts, user_pref)
    return sbert_rank_route_texts(route_texts, user_pref)
