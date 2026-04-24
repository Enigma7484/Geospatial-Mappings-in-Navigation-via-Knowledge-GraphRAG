import osmnx as ox
import numpy as np
from collections import Counter

# ----------------------------
# Graph + park helpers
# ----------------------------

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
        else:
            edges.append(ed)
    return edges

def annotate_edge_generation_costs(G, G_proj, parks_union):
    """
    Add generation-side edge weights so route generation itself can prefer:
    - scenic routes
    - safer-feeling routes
    - simpler routes
    """
    major_set = {
        "primary", "secondary", "tertiary", "trunk",
        "primary_link", "secondary_link", "tertiary_link", "trunk_link"
    }
    walk_set = {"footway", "path", "pedestrian", "steps", "living_street", "cycleway", "track"}
    residential_set = {"residential", "unclassified"}
    service_set = {"service"}

    for u, v, key, data in G.edges(keys=True, data=True):
        length = float(data.get("length", 1.0) or 1.0)
        hwy = normalize_highway_tag(data.get("highway"))

        # Get projected twin edge for park distance calculations
        proj_data = G_proj.get_edge_data(u, v, key)
        geom_proj = None
        if proj_data:
            geom_proj = proj_data.get("geometry", None)

        near_park = False
        park_dist = None
        if parks_union is not None and geom_proj is not None:
            try:
                park_dist = geom_proj.distance(parks_union)
                near_park = park_dist <= 75  # meters
            except Exception:
                park_dist = None

        # ----------------------------
        # Scenic generation weight
        # lower cost = more likely to be generated
        # ----------------------------
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

        # ----------------------------
        # Safe / calm generation weight
        # ----------------------------
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

        # ----------------------------
        # Simple generation weight
        # Fewer complex intersections / easier streets
        # ----------------------------
        target_deg = G.degree[v] if v in G.nodes else 2
        intersection_penalty = max(target_deg - 2, 0) * 12.0  # meters-equivalent

        simple_cost = length + intersection_penalty
        if hwy in major_set:
            simple_cost += 18.0
        if hwy in service_set:
            simple_cost += 10.0
        if hwy in residential_set:
            simple_cost -= 4.0
        if hwy in walk_set:
            simple_cost -= 6.0

        # Keep weights positive
        data["scenic_weight"] = max(1.0, scenic_cost)
        data["safe_weight"] = max(1.0, safe_cost)
        data["simple_weight"] = max(1.0, simple_cost)

def interleave_unique_route_lists(route_lists, max_routes):
    """
    Interleave route pools from different weighting strategies and remove duplicates.
    """
    out = []
    seen = set()

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
    """
    Generate route candidates under multiple edge weights, not just pure shortest-path.
    """
    per_mode_k = max(k_routes, 4)

    route_pools = []

    weights = [
        "length",
        "scenic_weight",
        "safe_weight",
        "simple_weight",
    ]

    for weight_name in weights:
        try:
            routes = list(
                ox.k_shortest_paths(
                    G,
                    orig_node,
                    dest_node,
                    k=per_mode_k,
                    weight=weight_name,
                )
            )
            route_pools.append(routes)
        except Exception:
            route_pools.append([])

    routes = interleave_unique_route_lists(route_pools, max_routes=max(k_routes * 2, k_routes))

    # final fallback
    if not routes:
            routes = generate_diverse_candidate_routes(G, orig_node, dest_node, k_routes)

    return routes[: max(k_routes, len(routes))]

def count_turns(GX, route):
    turns = 0
    bearings = []

    for u, v in zip(route[:-1], route[1:]):
        ed = GX.get_edge_data(u, v)
        if isinstance(ed, dict):
            edge = min(ed.values(), key=lambda d: d.get("length", float("inf")))
        else:
            edge = ed

        b = edge.get("bearing", None)
        if b is not None:
            bearings.append(float(b))

    for i in range(1, len(bearings)):
        diff = abs(bearings[i] - bearings[i - 1])
        diff = min(diff, 360 - diff)
        if diff > 45:
            turns += 1

    return turns


def safety_proxy_features(
    G,
    G_proj,
    route,
    total_len,
    major_pct,
    service_pct,
    walk_pct,
    residential_pct,
):
    """
    OSM-only comfort/safety proxy (NOT real crime).
    Returns a 0-100 score where higher = calmer / safer-feeling.
    Uses:
      - lit=yes length %
      - traffic signals / crossings normalized per km
      - tunnel %
      - walk-friendly / residential / major-road exposure
    """
    edges_proj = route_edge_data_min_len(G_proj, route)

    lit_m = 0.0
    tunnel_m = 0.0

    for e in edges_proj:
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

    # Node-based proxies
    signal_cnt = 0
    crossing_cnt = 0

    for n in route:
        nd = G.nodes.get(n, {})
        hw = nd.get("highway", None)
        if isinstance(hw, list):
            hw = hw[0]

        if hw == "traffic_signals":
            signal_cnt += 1
        if hw == "crossing":
            crossing_cnt += 1

        cr = nd.get("crossing", None)
        if cr is not None:
            crossing_cnt += 1

    signal_per_km = signal_cnt / max(distance_km, 0.1)
    crossing_per_km = crossing_cnt / max(distance_km, 0.1)

    # 0-100 interpretable proxy
    # Higher = calmer / safer-feeling for walking
    safety_score = (
        50.0
        + 0.25 * lit_pct
        + 0.15 * walk_pct
        + 0.10 * residential_pct
        - 0.25 * major_pct
        - 0.12 * service_pct
        - 2.00 * crossing_per_km
        - 1.00 * signal_per_km
        - 0.08 * tunnel_pct
    )

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
    coords = []
    for node in route:
        y = G.nodes[node]["y"]
        x = G.nodes[node]["x"]
        coords.append([y, x])  # Leaflet likes [lat, lon]
    return coords


def build_graph_and_parks(origin: str, dist_meters: int):
    orig_point = ox.geocode(origin)

    G = ox.graph_from_point(orig_point, dist=dist_meters, network_type="walk")
    G = ox.distance.add_edge_lengths(G)

    try:
        G = ox.bearing.add_edge_bearings(G)
    except Exception:
        G = ox.add_edge_bearings(G)

    G_proj = ox.project_graph(G)

    tags = {
        "leisure": ["park", "garden", "playground"],
        "landuse": ["grass", "recreation_ground"],
        "natural": ["wood"]
    }

    try:
        parks = ox.geometries_from_point(orig_point, tags=tags, dist=dist_meters)
    except Exception:
        parks = ox.features_from_point(orig_point, tags=tags, dist=dist_meters)

    if len(parks) > 0:
        parks = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()

    if len(parks) > 0:
        nodes_proj = ox.graph_to_gdfs(G_proj, nodes=True, edges=False)
        parks_proj = parks.to_crs(nodes_proj.crs)
        parks_union = parks_proj.geometry.unary_union
    else:
        parks_union = None

    annotate_edge_generation_costs(G, G_proj, parks_union)

    return G, G_proj, parks_union


def compute_route_features(G, G_proj, parks_union, route):
    edges = route_edge_data_min_len(G, route)
    edges_proj = route_edge_data_min_len(G_proj, route)

    total_len = 0.0
    major_m = 0.0
    walk_m = 0.0
    residential_m = 0.0
    service_m = 0.0
    hwy_counts = Counter()

    major_set = {
        "primary", "secondary", "tertiary", "trunk",
        "primary_link", "secondary_link", "tertiary_link", "trunk_link"
    }
    walk_set = {
        "footway", "path", "pedestrian", "steps", "living_street",
        "cycleway", "track"
    }
    residential_set = {"residential", "unclassified"}
    service_set = {"service"}

    for e in edges:
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

    NEAR_PARK_M = 50
    near_park_m = 0.0
    min_park_dist = float("inf")

    if parks_union is not None:
        for e in edges_proj:
            length = e.get("length", 0.0) or 0.0
            geom = e.get("geometry", None)
            if geom is None:
                continue

            d = geom.distance(parks_union)
            if np.isfinite(d):
                min_park_dist = min(min_park_dist, d)
                if d <= NEAR_PARK_M:
                    near_park_m += length

    park_near_pct = 100.0 * near_park_m / total_len if total_len > 0 else 0.0
    min_park_dist = None if min_park_dist == float("inf") else float(min_park_dist)

    safety = safety_proxy_features(
        G,
        G_proj,
        route,
        total_len,
        major_pct,
        service_pct,
        walk_pct,
        residential_pct,
    )

    top_types = ", ".join([t for t, _ in hwy_counts.most_common(5)])

    summary = (
        f"Walking route of {total_len/1000:.2f} km. "
        f"Top ways: {top_types}. "
        f"{walk_pct:.1f}% on footpaths. "
        f"{residential_pct:.1f}% residential streets. "
        f"{service_pct:.1f}% service roads. "
        f"{major_pct:.1f}% major roads. "
        f"Approx {intersections} intersections and {turns} turns. "
        f"{park_near_pct:.1f}% near parks, closest park "
        f"{min_park_dist if min_park_dist is not None else -1:.0f}m. "
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


def generate_rankable_routes(origin: str, destination: str, dist_meters: int, k_routes: int):
    G, G_proj, parks_union = build_graph_and_parks(origin, dist_meters)

    orig_point = ox.geocode(origin)
    dest_point = ox.geocode(destination)

    orig_node = ox.distance.nearest_nodes(G, X=orig_point[1], Y=orig_point[0])
    dest_node = ox.distance.nearest_nodes(G, X=dest_point[1], Y=dest_point[0])

    routes = list(ox.k_shortest_paths(G, orig_node, dest_node, k=k_routes, weight="length"))

    route_feature_dicts = []
    route_texts = []

    for route in routes:
        feat = compute_route_features(G, G_proj, parks_union, route)
        route_feature_dicts.append(feat)
        route_texts.append(feat["summary"])

    return route_feature_dicts, route_texts