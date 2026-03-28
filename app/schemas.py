from pydantic import BaseModel
from typing import List, Optional


class RankRoutesRequest(BaseModel):
    origin: str
    destination: str
    preference: str
    dist_meters: int = 6000
    k_routes: int = 5


class RouteResponse(BaseModel):
    rank: int
    score: float
    distance_km: float
    major_pct: float
    walk_pct: float
    residential_pct: float
    service_pct: float
    intersections: int
    turns: int
    park_near_pct: float
    min_park_dist_m: Optional[float]
    safety_score: float
    lit_pct: float
    signal_cnt: int
    crossing_cnt: int
    tunnel_m: float
    summary: str
    coordinates: List[List[float]]


class RankRoutesResponse(BaseModel):
    origin: str
    destination: str
    preference: str
    routes: List[RouteResponse]