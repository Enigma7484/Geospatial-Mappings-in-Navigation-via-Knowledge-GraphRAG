import os
from functools import lru_cache
from pathlib import Path
import osmnx as ox
import numpy as np
from collections import Counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(os.getenv("GEOROUTE_CACHE_DIR", PROJECT_ROOT / "cache"))
GRAPH_CACHE_SIZE = int(os.getenv("GEOROUTE_GRAPH_CACHE_SIZE", "2"))
ROUTE_CACHE_SIZE = int(os.getenv("GEOROUTE_ROUTE_CACHE_SIZE", "16"))
ENABLE_PARKS = os.getenv("GEOROUTE_ENABLE_PARKS", "1").lower() not in {"0", "false", "no"}

ox.settings.use_cache = True
ox.settings.cache_folder = str(CACHE_DIR)


def resolve_location(location: Any):
    if isinstance(location, dict):
        return (float(location["lat"]), float(location["lon"]))
    if isinstance(location, (list, tuple)) and len(location) == 2:
        return (float(location[0]), float(location[1]))
    return ox.geocode(location)


def normalize_location_key(location: Any):
    if isinstance(location, dict):
        return ("point", round(float(location["lat"]), 5), round(float(location["lon"]), 5))
    if isinstance(location, (list, tuple)) and len(location) == 2:
        return ("point", round(float(location[0]), 5), round(float(location[1]), 5))
    return ("place", str(location).strip().lower())


def resolve_location_key(location_key):
    kind = location_key[0]
    if kind == "point":
        return (float(location_key[1]), float(location_key[2]))
    return ox.geocode(location_key[1])


def normalize_highway_tag(hwy):
    if isinstance(hwy, list):
        return hwy[0]
    return hwy if hwy else "unknown"


def route_edge_data_min_len(GX, route):
    edges = []
    for u, v in zip(route[:-1], route[1:]):
        ed = GX.get_edge_data(u, v)
        if isinstance(ed, dict):
            best = min(ed.values(), key=lambda d: d.get("length", float("inf")))
            edges.append(best)
        elif ed is not None:
            edges.append(ed)
    return edges


def get_edge_by_key_or_min(GX, u, v, key=None):
    ed = GX.get_edge_data(u, v)
    if not isinstance(ed, dict):
        return ed
    if key is not None and key in ed:
        return ed[key]
    return min(ed.values(), key=lambda d: d.get("length", float("inf")))


def annotate_edge_generation_costs(G, G_proj, parks_union):
    major_set = {"primary", "secondary", "tertiary", "trunk", "primary_link", "secondary_link", "tertiary_link", "trunk_link"}
    walk_set = {"footway", "path", "pedestrian", "steps", "living_street", "cycleway", "track"}
    residential_set = {"residential", "unclassified"}
    service_set = {"service"}

    for u, v, key, data in G.edges(keys=True, data=True):
        length = float(data.get("length", 1.0) or 1.0)
        hwy = normalize_highway_tag(data.get("highway"))
        proj_data = get_edge_by_key_or_min(G_proj, u, v, key)
        geom_proj = proj_data.get("geometry", None) if proj_data else None
        near_park = False
        if parks_union is not None and geom_proj is not None:
            try:
                near_park = geom_proj.distance(parks_union) <= 75
            except Exception:
                near_park = False

        scenic_cost = length
        if near_park:
            scenic_cost *= 0.78
        if hwy in walk_set:
            scenic_cost *= 0.92
        if hwy in residential_set:
            scenic_cost *= 0.95
        if hwy in major_set:
            scenic_cost *= 1.35
        if hwy in service_set:
            scenic_cost *= 1.08

        safe_cost = length
        lit = data.get("lit", None)
        if isinstance(lit, list):
            lit = lit[0]
        if isinstance(lit, str) and lit.lower() == "yes":
            safe_cost *= 0.92
        tunnel = data.get("tunnel", None)
        if isinstance(tunnel, list):
            tunnel = tunnel[0]
        if tunnel in ["yes", "building_passage", "culvert"]:
            safe_cost *= 1.25
        if hwy in walk_set:
            safe_cost *= 0.90
        if hwy in residential_set:
            safe_cost *= 0.94
        if hwy in major_set:
            safe_cost *= 1.40
        if hwy in service_set:
            safe_cost *= 1.12

        target_deg = G.degree[v] if v in G.nodes else 2
        simple_cost = length + max(target_deg - 2, 0) * 12.0
        if hwy in major_set:
            simple_cost += 18.0
        if hwy in service_set:
            simple_cost += 10.0
        if hwy in residential_set:
            simple_cost -= 4.0
        if hwy in walk_set:
            simple_cost -= 6.0

        data["scenic_weight"] = max(1.0, scenic_cost)
        data["safe_weight"] = max(1.0, safe_cost)
        data["simple_weight"] = max(1.0, simple_cost)


def interleave_unique_route_lists(route_lists, max_routes):
    out, seen = [], set()
    max_len = max((len(lst) for lst in route_lists), default=0)
    for i in range(max_len):
        for lst in route_lists:
            if i < len(lst):
                route = lst[i]
                key = tuple(route)
                if key not in seen:
                    seen.add(key)
                    out.append(route)
                    if len(out) >= max_routes:
                        return out
    return out


def generate_diverse_candidate_routes(G, orig_node, dest_node, k_routes):
    per_mode_k = max(k_routes, 4)
    route_pools = []
    for weight_name in ["length", "scenic_weight", "safe_weight", "simple_weight"]:
        try:
            routes = list(ox.k_shortest_paths(G, orig_node, dest_node, k=per_mode_k, weight=weight_name))
            route_pools.append(routes)
        except Exception:
            route_pools.append([])
    routes = interleave_unique_route_lists(route_pools, max_routes=k_routes)
    if not routes:
        routes = list(ox.k_shortest_paths(G, orig_node, dest_node, k=k_routes, weight="length"))
    return routes[:k_routes]


def count_turns(GX, route):
    bearings = []
    for u, v in zip(route[:-1], route[1:]):
        ed = GX.get_edge_data(u, v)
        edge = min(ed.values(), key=lambda d: d.get("length", float("inf"))) if isinstance(ed, dict) else ed
        b = edge.get("bearing", None) if edge else None
        if b is not None:
            bearings.append(float(b))
    turns = 0
    for i in range(1, len(bearings)):
        diff = abs(bearings[i] - bearings[i - 1])
        diff = min(diff, 360 - diff)
        if diff > 45:
            turns += 1
    return turns


def safety_proxy_features(G, G_proj, route, total_len, major_pct, service_pct, walk_pct, residential_pct):
    edges_proj = route_edge_data_min_len(G_proj, route)
    lit_m, tunnel_m = 0.0, 0.0
    for e in edges_proj:
        if e is None:
            continue
        length = e.get("length", 0.0) or 0.0
        lit = e.get("lit", None)
        if isinstance(lit, list):
            lit = lit[0]
        if isinstance(lit, str) and lit.lower() == "yes":
            lit_m += length
        tunnel = e.get("tunnel", None)
        if isinstance(tunnel, list):
            tunnel = tunnel[0]
        if tunnel in ["yes", "building_passage", "culvert"]:
            tunnel_m += length
    lit_pct = 100.0 * lit_m / total_len if total_len > 0 else 0.0
    tunnel_pct = 100.0 * tunnel_m / total_len if total_len > 0 else 0.0
    distance_km = total_len / 1000.0 if total_len > 0 else 1.0
    signal_cnt, crossing_cnt = 0, 0
    for n in route:
        nd = G.nodes.get(n, {})
        hw = nd.get("highway", None)
        if isinstance(hw, list):
            hw = hw[0]
        if hw == "traffic_signals":
            signal_cnt += 1
        if hw == "crossing":
            crossing_cnt += 1
        if nd.get("crossing", None) is not None:
            crossing_cnt += 1
    signal_per_km = signal_cnt / max(distance_km, 0.1)
    crossing_per_km = crossing_cnt / max(distance_km, 0.1)
    safety_score = 50.0 + 0.25 * lit_pct + 0.15 * walk_pct + 0.10 * residential_pct - 0.25 * major_pct - 0.12 * service_pct - 2.00 * crossing_per_km - 1.00 * signal_per_km - 0.08 * tunnel_pct
    safety_score = max(0.0, min(100.0, safety_score))
    return {
        "lit_pct": lit_pct,
        "signal_cnt": signal_cnt,
        "crossing_cnt": crossing_cnt,
        "signal_per_km": signal_per_km,
        "crossing_per_km": crossing_per_km,
        "tunnel_m": tunnel_m,
        "tunnel_pct": tunnel_pct,
        "safety_score": safety_score,
    }


def route_to_coordinates(G, route):
    return [[G.nodes[node]["y"], G.nodes[node]["x"]] for node in route]


def get_parks_union(origin_point, dist_meters, G_proj):
    if not ENABLE_PARKS:
        return None
    tags = {"leisure": ["park", "garden", "playground"], "landuse": ["grass", "recreation_ground"], "natural": ["wood"]}
    try:
        parks = ox.features_from_point(origin_point, tags=tags, dist=dist_meters)
    except Exception:
        try:
            parks = ox.geometries_from_point(origin_point, tags=tags, dist=dist_meters)
        except Exception:
            parks = None
    if parks is None or len(parks) == 0:
        return None
    parks = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    if len(parks) == 0:
        return None
    nodes_proj = ox.graph_to_gdfs(G_proj, nodes=True, edges=False)
    parks_proj = parks.to_crs(nodes_proj.crs)
    try:
        return parks_proj.geometry.union_all()
    except Exception:
        return parks_proj.geometry.unary_union


@lru_cache(maxsize=GRAPH_CACHE_SIZE)
def build_graph_and_parks_cached(origin_key, dist_meters: int):
    orig_point = resolve_location_key(origin_key)
    G = ox.graph_from_point(orig_point, dist=dist_meters, network_type="walk")
    G = ox.distance.add_edge_lengths(G)
    try:
        G = ox.bearing.add_edge_bearings(G)
    except Exception:
        try:
            G = ox.add_edge_bearings(G)
        except Exception:
            pass
    G_proj = ox.project_graph(G)
    parks_union = get_parks_union(orig_point, dist_meters, G_proj)
    annotate_edge_generation_costs(G, G_proj, parks_union)
    return G, G_proj, parks_union


def build_graph_and_parks(origin, dist_meters: int):
    return build_graph_and_parks_cached(normalize_location_key(origin), int(dist_meters))


def compute_route_features(G, G_proj, parks_union, route):
    edges = route_edge_data_min_len(G, route)
    edges_proj = route_edge_data_min_len(G_proj, route)
    total_len = major_m = walk_m = residential_m = service_m = 0.0
    hwy_counts = Counter()
    major_set = {"primary", "secondary", "tertiary", "trunk", "primary_link", "secondary_link", "tertiary_link", "trunk_link"}
    walk_set = {"footway", "path", "pedestrian", "steps", "living_street", "cycleway", "track"}
    residential_set = {"residential", "unclassified"}
    service_set = {"service"}
    for e in edges:
        if e is None:
            continue
        length = e.get("length", 0.0) or 0.0
        total_len += length
        hwy = normalize_highway_tag(e.get("highway"))
        hwy_counts[hwy] += 1
        if hwy in major_set:
            major_m += length
        if hwy in walk_set:
            walk_m += length
        if hwy in residential_set:
            residential_m += length
        if hwy in service_set:
            service_m += length
    major_pct = 100 * major_m / total_len if total_len else 0.0
    walk_pct = 100 * walk_m / total_len if total_len else 0.0
    residential_pct = 100 * residential_m / total_len if total_len else 0.0
    service_pct = 100 * service_m / total_len if total_len else 0.0
    intersections = sum(1 for n in route if G.degree[n] > 2)
    turns = count_turns(G, route)
    near_park_m, min_park_dist = 0.0, float("inf")
    if parks_union is not None:
        for e in edges_proj:
            if e is None:
                continue
            length = e.get("length", 0.0) or 0.0
            geom = e.get("geometry", None)
            if geom is None:
                continue
            try:
                d = geom.distance(parks_union)
            except Exception:
                continue
            if np.isfinite(d):
                min_park_dist = min(min_park_dist, d)
                if d <= 50:
                    near_park_m += length
    park_near_pct = 100.0 * near_park_m / total_len if total_len > 0 else 0.0
    min_park_dist = None if min_park_dist == float("inf") else float(min_park_dist)
    safety = safety_proxy_features(G, G_proj, route, total_len, major_pct, service_pct, walk_pct, residential_pct)
    top_types = ", ".join([t for t, _ in hwy_counts.most_common(5)])
    summary = (
        f"Walking route of {total_len/1000:.2f} km. Top ways: {top_types}. "
        f"{walk_pct:.1f}% on footpaths. {residential_pct:.1f}% residential streets. "
        f"{service_pct:.1f}% service roads. {major_pct:.1f}% major roads. "
        f"Approx {intersections} intersections and {turns} turns. "
        f"{park_near_pct:.1f}% near parks, closest park {min_park_dist if min_park_dist is not None else -1:.0f}m. "
        f"Safety proxy {safety['safety_score']:.1f}/100."
    )
    return {
        "distance_km": float(total_len / 1000),
        "major_pct": float(major_pct),
        "walk_pct": float(walk_pct),
        "residential_pct": float(residential_pct),
        "service_pct": float(service_pct),
        "intersections": int(intersections),
        "turns": int(turns),
        "park_near_pct": float(park_near_pct),
        "min_park_dist_m": min_park_dist,
        "safety_score": float(safety["safety_score"]),
        "lit_pct": float(safety["lit_pct"]),
        "signal_cnt": int(safety["signal_cnt"]),
        "crossing_cnt": int(safety["crossing_cnt"]),
        "tunnel_m": float(safety["tunnel_m"]),
        "summary": summary,
        "coordinates": route_to_coordinates(G, route),
    }


@lru_cache(maxsize=ROUTE_CACHE_SIZE)
def generate_rankable_routes_cached(origin_key, destination_key, dist_meters: int, k_routes: int):
    G, G_proj, parks_union = build_graph_and_parks_cached(origin_key, int(dist_meters))
    orig_point = resolve_location_key(origin_key)
    dest_point = resolve_location_key(destination_key)
    orig_node = ox.distance.nearest_nodes(G, X=orig_point[1], Y=orig_point[0])
    dest_node = ox.distance.nearest_nodes(G, X=dest_point[1], Y=dest_point[0])
    routes = generate_diverse_candidate_routes(G, orig_node, dest_node, k_routes)
    route_feature_dicts, route_texts = [], []
    for route in routes:
        feat = compute_route_features(G, G_proj, parks_union, route)
        route_feature_dicts.append(feat)
        route_texts.append(feat["summary"])
    return route_feature_dicts, route_texts


def generate_rankable_routes(origin, destination, dist_meters: int, k_routes: int):
    return generate_rankable_routes_cached(
        normalize_location_key(origin),
        normalize_location_key(destination),
        int(dist_meters),
        int(k_routes),
    )
