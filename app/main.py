from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import os

from .schemas import RankRoutesRequest, RankRoutesResponse, RouteResponse

print("Starting FastAPI app...")

MAX_DIST_METERS = int(os.getenv("GEOROUTE_MAX_DIST_METERS", "4000"))
MAX_K_ROUTES = int(os.getenv("GEOROUTE_MAX_K_ROUTES", "5"))

app = FastAPI(title="GeoRoute Preference API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def minmax(arr):
    arr = np.asarray(arr, dtype=float)
    mn = arr.min()
    mx = arr.max()
    if np.isclose(mx, mn):
        return np.ones_like(arr) * 0.5
    return (arr - mn) / (mx - mn)


@app.get("/")
def root():
    return {"message": "GeoRoute Preference API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/runtime")
def runtime():
    from .routing import build_graph_and_parks_cached, generate_rankable_routes_cached

    return {
        "status": "ok",
        "limits": {
            "max_dist_meters": MAX_DIST_METERS,
            "max_k_routes": MAX_K_ROUTES,
        },
        "cache": {
            "graphs": build_graph_and_parks_cached.cache_info()._asdict(),
            "routes": generate_rankable_routes_cached.cache_info()._asdict(),
        },
    }


@app.post("/rank-routes", response_model=RankRoutesResponse)
def rank_routes(payload: RankRoutesRequest):
    from .routing import generate_rankable_routes
    from .profile import (
        get_request_context,
        load_user_history,
        build_dynamic_profile,
        summarize_profile,
        score_routes_with_profile,
    )
    from .ranking import rank_route_texts

    context = get_request_context(payload.request_datetime)

    if payload.dist_meters > MAX_DIST_METERS:
        raise HTTPException(
            status_code=400,
            detail=f"dist_meters must be <= {MAX_DIST_METERS} on this deployment.",
        )
    if payload.k_routes > MAX_K_ROUTES:
        raise HTTPException(
            status_code=400,
            detail=f"k_routes must be <= {MAX_K_ROUTES} on this deployment.",
        )

    route_feature_dicts, route_texts = generate_rankable_routes(
        origin=payload.origin,
        destination=payload.destination,
        dist_meters=payload.dist_meters,
        k_routes=payload.k_routes,
    )

    if not route_feature_dicts:
        raise HTTPException(status_code=404, detail="No route candidates could be generated.")

    profile_summary = None
    profile_scores = None
    sbert_scores = None

    if payload.ranking_mode in {"prompt", "hybrid"}:
        if not payload.preference:
            raise HTTPException(
                status_code=400,
                detail="ranking_mode='prompt' or 'hybrid' requires a non-empty 'preference'.",
            )
        try:
            sbert_scores = minmax(rank_route_texts(route_texts, payload.preference))
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Prompt ranking dependencies are not installed on this deployment. "
                    "Use ranking_mode='profile' or deploy with requirements.txt."
                ),
            ) from exc

    if payload.ranking_mode in {"profile", "hybrid"}:
        if not payload.user_id:
            raise HTTPException(
                status_code=400,
                detail="ranking_mode='profile' or 'hybrid' requires a non-empty 'user_id'.",
            )

        history = load_user_history(payload.user_id)
        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"No historical profile found for user_id='{payload.user_id}'.",
            )

        profile = build_dynamic_profile(history, context)
        profile_summary = summarize_profile(profile)
        profile_scores = score_routes_with_profile(route_feature_dicts, profile)

    if payload.ranking_mode == "prompt":
        combined = sbert_scores
    elif payload.ranking_mode == "profile":
        combined = profile_scores
    elif payload.ranking_mode == "hybrid":
        combined = 0.75 * profile_scores + 0.25 * sbert_scores
    else:
        raise HTTPException(status_code=400, detail="Invalid ranking_mode.")

    ranking = np.argsort(-combined)

    routes = []
    for rank_num, idx in enumerate(ranking, start=1):
        feat = route_feature_dicts[idx]
        routes.append(
            RouteResponse(
                rank=rank_num,
                combined_score=float(combined[idx]),
                profile_score=float(profile_scores[idx]) if profile_scores is not None else None,
                sbert_score=float(sbert_scores[idx]) if sbert_scores is not None else None,
                distance_km=feat["distance_km"],
                major_pct=feat["major_pct"],
                walk_pct=feat["walk_pct"],
                residential_pct=feat["residential_pct"],
                service_pct=feat["service_pct"],
                intersections=feat["intersections"],
                turns=feat["turns"],
                park_near_pct=feat["park_near_pct"],
                min_park_dist_m=feat["min_park_dist_m"],
                safety_score=feat["safety_score"],
                lit_pct=feat["lit_pct"],
                signal_cnt=feat["signal_cnt"],
                crossing_cnt=feat["crossing_cnt"],
                tunnel_m=feat["tunnel_m"],
                summary=feat["summary"],
                coordinates=feat["coordinates"],
            )
        )

    return RankRoutesResponse(
        origin=payload.origin,
        destination=payload.destination,
        preference=payload.preference,
        user_id=payload.user_id,
        ranking_mode=payload.ranking_mode,
        context=context,
        profile_summary=profile_summary,
        routes=routes,
    )
