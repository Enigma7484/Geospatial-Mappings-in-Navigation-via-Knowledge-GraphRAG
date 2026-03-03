import osmnx as ox
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# ----------------------------
# 1) Toronto Setup
# ----------------------------

orig_address = "University of Toronto, Toronto, Canada"
dest_address = "Nathan Phillips Square, Toronto, Canada"

# Try different prompts later
user_pref = "prefer scenic calm walk, avoid busy roads, fewer intersections, more residential streets"

DIST_METERS = 6000
K_ROUTES = 10

# ----------------------------
# 2) Build Toronto Walking Graph
# ----------------------------

orig_point = ox.geocode(orig_address)
dest_point = ox.geocode(dest_address)

G = ox.graph_from_point(orig_point, dist=DIST_METERS, network_type="walk")
G = ox.distance.add_edge_lengths(G)

# Add bearings (for turn counting)
try:
    # newer OSMnx
    G = ox.bearing.add_edge_bearings(G)
except Exception:
    # older OSMnx fallback
    G = ox.add_edge_bearings(G)

print("Nodes:", len(G.nodes), "Edges:", len(G.edges))

orig_node = ox.distance.nearest_nodes(G, X=orig_point[1], Y=orig_point[0])
dest_node = ox.distance.nearest_nodes(G, X=dest_point[1], Y=dest_point[0])

routes = list(ox.k_shortest_paths(G, orig_node, dest_node, k=K_ROUTES, weight="length"))
print("Got routes:", len(routes))

# ----------------------------
# 3) Feature Extraction
# ----------------------------

def normalize_highway_tag(hwy):
    if isinstance(hwy, list):
        return hwy[0]
    return hwy if hwy else "unknown"

def route_edge_data_min_len(G, route):
    edges = []
    for u, v in zip(route[:-1], route[1:]):
        ed = G.get_edge_data(u, v)
        if isinstance(ed, dict):
            best = min(ed.values(), key=lambda d: d.get("length", float("inf")))
            edges.append(best)
        else:
            edges.append(ed)
    return edges

def count_turns(G, route):
    turns = 0
    bearings = []

    for u, v in zip(route[:-1], route[1:]):
        data = G.get_edge_data(u, v)
        if isinstance(data, dict):
            edge = min(data.values(), key=lambda d: d.get("length", float("inf")))
        else:
            edge = data

        if "bearing" in edge:
            bearings.append(edge["bearing"])

    for i in range(1, len(bearings)):
        diff = abs(bearings[i] - bearings[i-1])
        if diff > 45:
            turns += 1

    return turns

def route_features_to_text(G, route):

    edges = route_edge_data_min_len(G, route)

    total_len = 0.0
    major_m = 0.0
    walk_m = 0.0
    residential_m = 0.0
    service_m = 0.0
    hwy_counts = Counter()

    major_set = {"primary", "secondary", "tertiary", "trunk",
             "primary_link", "secondary_link", "tertiary_link", "trunk_link"}

    walk_set = {"footway", "path", "pedestrian", "steps", "living_street",
            "cycleway", "track"}

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

    intersections = sum(1 for n in route if G.degree[n] > 2)
    turns = count_turns(G, route)

    text = (
        f"Walking route of {total_len/1000:.2f} km. "
        f"{walk_pct:.1f}% on footpaths. "
        f"{residential_pct:.1f}% residential streets. "
        f"{service_pct:.1f}% service roads. "
        f"{major_pct:.1f}% major roads. "
        f"Approx {intersections} intersections and {turns} turns."
    )

    return text, total_len, major_pct, walk_pct, residential_pct, intersections, turns

# ----------------------------
# 4) Build Route Descriptions
# ----------------------------

route_texts = []
route_meta = []

for i, r in enumerate(routes):
    txt, dist_m, major_pct, walk_pct, res_pct, intersections, turns = route_features_to_text(G, r)
    route_texts.append(txt)
    route_meta.append({
        "idx": i,
        "dist_km": dist_m/1000,
        "major_pct": major_pct,
        "walk_pct": walk_pct,
        "residential_pct": res_pct,
        "intersections": intersections,
        "turns": turns
    })

# Debug: what highway tags are we actually seeing?
all_types = Counter()
for r in routes:
    for e in route_edge_data_min_len(G, r):
        all_types[normalize_highway_tag(e.get("highway"))] += 1

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
    print(f"{rank}) Route {idx} | score={scores[idx]:.3f}")
    print("   ", route_texts[idx])

# ----------------------------
# 6) Plot Best Route
# ----------------------------

best_idx = int(topk[0])
best_route = routes[best_idx]

fig, ax = ox.plot_graph_route(G, best_route, route_linewidth=4, node_size=0, bgcolor="white")
plt.show()