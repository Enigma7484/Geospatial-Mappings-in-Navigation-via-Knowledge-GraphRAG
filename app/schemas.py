from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal


class RankRoutesRequest(BaseModel):
    origin: Any
    destination: Any
    preference: Optional[str] = None
    user_id: Optional[str] = None
    request_datetime: Optional[str] = None
    dist_meters: int = Field(default=4000, ge=500)
    k_routes: int = Field(default=5, ge=1)
    ranking_mode: Literal["prompt", "profile", "hybrid"] = "profile"


class RouteResponse(BaseModel):
    rank: int
    combined_score: float
    profile_score: Optional[float] = None
    sbert_score: Optional[float] = None
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
    origin: Any
    destination: Any
    preference: Optional[str] = None
    user_id: Optional[str] = None
    ranking_mode: str
    context: Dict[str, Any]
    profile_summary: Optional[str] = None
    routes: List[RouteResponse]
