from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import numpy as np

from .schemas import RankRoutesRequest, RankRoutesResponse, RouteResponse

print("Starting FastAPI app...")

app = FastAPI(title="GeoRoute Preference API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://YOUR-FRONTEND.vercel.app",
    ],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "GeoRoute Preference API is running"}

@app.post("/rank-routes", response_model=RankRoutesResponse)
def rank_routes(payload: RankRoutesRequest):
    # Lazy imports so startup stays light
    from .routing import generate_rankable_routes
    from .ranking import rank_route_texts

    route_feature_dicts, route_texts = generate_rankable_routes(
        origin=payload.origin,
        destination=payload.destination,
        dist_meters=payload.dist_meters,
        k_routes=payload.k_routes,
    )

    scores = rank_route_texts(route_texts, payload.preference)
    ranking = np.argsort(-scores)

    routes = []
    for rank_num, idx in enumerate(ranking, start=1):
        feat = route_feature_dicts[idx]
        routes.append(
            RouteResponse(
                rank=rank_num,
                score=float(scores[idx]),
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
        routes=routes,
    )