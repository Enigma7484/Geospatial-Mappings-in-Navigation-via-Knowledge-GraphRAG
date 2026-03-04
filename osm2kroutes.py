import osmnx as ox
import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd
from collections import Counter
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# ----------------------------
# 1) Toronto Setup
# ----------------------------
orig_address = "University of Toronto, Toronto, Canada"
dest_address = "Nathan Phillips Square, Toronto, Canada"

user_pref = "prefer scenic calm walk, avoid busy roads, fewer intersections, more residential streets"

DIST_METERS = 6000
K_ROUTES = 10

# ----------------------------
# 2) Build Toronto Walking Graph
# ----------------------------
orig_point = ox.geocode(orig_address)  # (lat, lon)
dest_point = ox.geocode(dest_address)

G = ox.graph_from_point(orig_point, dist=DIST_METERS, network_type="walk")
G = ox.distance.add_edge_lengths(G)

# Add bearings (for turn counting)
try:
    G = ox.bearing.add_edge_bearings(G)  # newer OSMnx
except Exception:
    G = ox.add_edge_bearings(G)          # older OSMnx

# Project graph to meters for distance/geometry operations
G_proj = ox.project_graph(G)

print("Nodes:", len(G.nodes), "Edges:", len(G.edges))

orig_node = ox.distance.nearest_nodes(G, X=orig_point[1], Y=orig_point[0])
dest_node = ox.distance.nearest_nodes(G, X=dest_point[1], Y=dest_point[0])

routes = list(ox.k_shortest_paths(G, orig_node, dest_node, k=K_ROUTES, weight="length"))
print("Got routes:", len(routes))

# ----------------------------
# 2b) Parks / green areas from OSM (for proximity scoring)
# ----------------------------
tags = {
    "leisure": ["park", "garden", "playground"],
    "landuse": ["grass", "recreation_ground"],
    "natural": ["wood"]
}

try:
    parks = ox.features_from_point(orig_point, tags=tags, dist=DIST_METERS)
except Exception:
    parks = ox.geometries_from_point(orig_point, tags=tags, dist=DIST_METERS)

# keep only polygons (parks as areas)
parks = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()

# project parks into same CRS as projected graph
nodes_proj = ox.graph_to_gdfs(G_proj, nodes=True, edges=False)
parks_proj = parks.to_crs(nodes_proj.crs)

# union geometry for fast distance checks
parks_union = parks_proj.geometry.unary_union

# ----------------------------
# 3) Helpers
# ----------------------------
def normalize_highway_tag(hwy):
    if isinstance(hwy, list):
        return hwy[0]
    return hwy if hwy else "unknown"

def route_edge_data_min_len(GX, route):
    """For each consecutive (u,v) pick the edge with minimum length (safe for MultiDiGraph)."""
    edges = []
    for u, v in zip(route[:-1], route[1:]):
        ed = GX.get_edge_data(u, v)
        if isinstance(ed, dict):
            best = min(ed.values(), key=lambda d: d.get("length", float("inf")))
            edges.append(best)
        else:
            edges.append(ed)
    return edges

def count_turns(GX, route):
    """Count turns using edge bearings (rough proxy)."""
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
        # wrap-around: 350 -> 10 is 20 degrees, not 340
        diff = min(diff, 360 - diff)
        if diff > 45:
            turns += 1

    return turns

def safety_proxy_features(G, G_proj, route, total_len, major_pct, service_pct):
    """
    OSM-only safety proxy (NOT real crime):
    - lit=yes length %
    - traffic signals / crossings count (nodes)
    - tunnel length
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

    # Node-based proxies: traffic signals / crossings
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

        # Sometimes crossing info is stored separately
        cr = nd.get("crossing", None)
        if cr is not None:
            crossing_cnt += 1

    # Weighted score (tune later)
    safety_score = (
        0.6 * lit_pct
        - 0.25 * major_pct
        - 0.15 * service_pct
        - 0.03 * (signal_cnt + crossing_cnt)
        - 0.002 * tunnel_m
    )

    return {
        "lit_pct": lit_pct,
        "signal_cnt": signal_cnt,
        "crossing_cnt": crossing_cnt,
        "tunnel_m": tunnel_m,
        "safety_score": safety_score
    }

def route_features_to_text(G, G_proj, route):
    edges = route_edge_data_min_len(G, route)
    edges_proj = route_edge_data_min_len(G_proj, route)

    total_len = 0.0
    major_m = 0.0
    walk_m = 0.0
    residential_m = 0.0
    service_m = 0.0
    hwy_counts = Counter()

    # Broader categories for Toronto
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

    major_pct = 100 * major_m / total_len if total_len else 0
    walk_pct = 100 * walk_m / total_len if total_len else 0
    residential_pct = 100 * residential_m / total_len if total_len else 0
    service_pct = 100 * service_m / total_len if total_len else 0

    # intersections proxy
    intersections = sum(1 for n in route if G.degree[n] > 2)
    turns = count_turns(G, route)

    # --- Park proximity features (projected geometries) ---
    NEAR_PARK_M = 50
    near_park_m = 0.0
    min_park_dist = float("inf")

    for e in edges_proj:
        length = e.get("length", 0.0) or 0.0
        geom = e.get("geometry", None)
        if geom is None:
            continue

        d = geom.distance(parks_union)  # meters (projected)
        if np.isfinite(d):
            min_park_dist = min(min_park_dist, d)
            if d <= NEAR_PARK_M:
                near_park_m += length

    park_near_pct = 100.0 * near_park_m / total_len if total_len > 0 else 0.0
    min_park_dist = min_park_dist if np.isfinite(min_park_dist) else float("inf")

    # --- Safety proxy ---
    safety = safety_proxy_features(G, G_proj, route, total_len, major_pct, service_pct)

    # Summarize top highway tags
    top_types = ", ".join([t for t, _ in hwy_counts.most_common(5)])

    text = (
        f"Walking route of {total_len/1000:.2f} km. "
        f"Top ways: {top_types}. "
        f"{walk_pct:.1f}% on footpaths. "
        f"{residential_pct:.1f}% residential streets. "
        f"{service_pct:.1f}% service roads. "
        f"{major_pct:.1f}% major roads. "
        f"Approx {intersections} intersections and {turns} turns. "
        f"{park_near_pct:.1f}% near parks (<= {NEAR_PARK_M}m), closest park {min_park_dist:.0f}m. "
        f"Safety proxy {safety['safety_score']:.2f} (lit {safety['lit_pct']:.1f}%, "
        f"signals {safety['signal_cnt']}, crossings {safety['crossing_cnt']}, tunnel {safety['tunnel_m']:.0f}m)."
    )

    return (
        text, total_len, major_pct, walk_pct, residential_pct,
        service_pct, intersections, turns, park_near_pct, min_park_dist, safety, hwy_counts
    )

# ----------------------------
# 4) Build Route Descriptions
# ----------------------------
route_texts = []
route_meta = []

all_types = Counter()

for i, r in enumerate(routes):
    (
        txt, dist_m, major_pct, walk_pct, res_pct,
        service_pct, intersections, turns, park_near_pct, min_park_dist, safety, hwy_counts
    ) = route_features_to_text(G, G_proj, r)

    route_texts.append(txt)
    route_meta.append({
        "idx": i,
        "dist_km": dist_m / 1000,
        "major_pct": major_pct,
        "walk_pct": walk_pct,
        "residential_pct": res_pct,
        "service_pct": service_pct,
        "intersections": intersections,
        "turns": turns,
        "park_near_pct": park_near_pct,
        "min_park_dist_m": None if min_park_dist == float("inf") else float(min_park_dist),
        "safety_score": safety["safety_score"],
        "lit_pct": safety["lit_pct"],
        "signal_cnt": safety["signal_cnt"],
        "crossing_cnt": safety["crossing_cnt"],
        "tunnel_m": safety["tunnel_m"],
    })

    # debug highway tags
    all_types.update(hwy_counts)

print("\nTop highway tags seen:", all_types.most_common(15))

# ----------------------------
# 5) SBERT Ranking
# ----------------------------
model = SentenceTransformer("all-MiniLM-L6-v2")

emb_routes = model.encode(route_texts, normalize_embeddings=True)
emb_user = model.encode([user_pref], normalize_embeddings=True)

scores = cosine_similarity(emb_user, emb_routes)[0]
ranking = np.argsort(-scores)
topk = ranking[:5]

print("\nTop Ranked Routes:")
for rank, idx in enumerate(topk, 1):
    m = route_meta[idx]
    print(
        f"{rank}) Route {idx} | score={scores[idx]:.3f} | "
        f"dist={m['dist_km']:.2f}km | parkNear={m['park_near_pct']:.1f}% | "
        f"safety={m['safety_score']:.2f} | turns={m['turns']} | inters={m['intersections']} | "
        f"major={m['major_pct']:.1f}% | walk={m['walk_pct']:.1f}%"
    )
    print("   ", route_texts[idx])

# ----------------------------
# 6) Plot Best Route
# ----------------------------
best_idx = int(topk[0])
best_route = routes[best_idx]

fig, ax = ox.plot_graph_route(G, best_route, route_linewidth=4, node_size=0, bgcolor="white")
plt.show()