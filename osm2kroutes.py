import osmnx as ox
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# ----------------------------
# 1) Inputs
# ----------------------------
orig_address = "Dhaka University, Dhaka"
dest_address = "Ramna Park, Dhaka"

user_pref = "calm walk, avoid busy roads, prefer footpaths and parks, fewer major roads"

# How big an area to download around the origin (meters)
DIST_METERS = 5000

# How many candidate routes to generate
K_ROUTES = 10

# ----------------------------
# 2) Build a smaller walking graph (faster + better plots)
# ----------------------------
orig_point = ox.geocode(orig_address)  # (lat, lon)
dest_point = ox.geocode(dest_address)

G = ox.graph_from_point(orig_point, dist=DIST_METERS, network_type="walk")
G = ox.distance.add_edge_lengths(G)

print("Nodes:", len(G.nodes), "Edges:", len(G.edges))

orig_node = ox.distance.nearest_nodes(G, X=orig_point[1], Y=orig_point[0])
dest_node = ox.distance.nearest_nodes(G, X=dest_point[1], Y=dest_point[0])

# ----------------------------
# 3) Generate K candidate routes (OSMnx supports MultiDiGraph)
# ----------------------------
routes = list(ox.k_shortest_paths(G, orig_node, dest_node, k=K_ROUTES, weight="length"))
print("Got routes:", len(routes))
print("Example route length (nodes):", len(routes[0]))

# ----------------------------
# 4) Feature extraction helpers
# ----------------------------
def normalize_highway_tag(hwy):
    # OSM 'highway' can be a list or string
    if isinstance(hwy, list):
        return hwy[0]
    return hwy if hwy is not None else "unknown"

def route_edge_data_min_len(G, route):
    """
    For each consecutive (u,v) pair, pick the edge with the minimum length.
    This is safe for MultiDiGraph where there can be multiple edges between u and v.
    """
    edges = []
    for u, v in zip(route[:-1], route[1:]):
        ed = G.get_edge_data(u, v)

        # MultiDiGraph: dict of key -> attr dict
        if isinstance(ed, dict):
            best = min(ed.values(), key=lambda d: d.get("length", float("inf")))
            edges.append(best)
        else:
            # Non-multigraph (rare here), already attr dict
            edges.append(ed)
    return edges

def route_features_to_text(G, route):
    edges = route_edge_data_min_len(G, route)

    total_len = 0.0
    hwy_counts = Counter()

    major_road_m = 0.0
    walk_friendly_m = 0.0

    # You can tune these sets later
    major_set = {"primary", "secondary", "tertiary", "trunk"}  # big roads
    walk_friendly = {"footway", "path", "pedestrian", "steps", "living_street"}

    for e in edges:
        length = e.get("length", 0.0) or 0.0
        total_len += length

        hwy = normalize_highway_tag(e.get("highway", "unknown"))
        hwy_counts[hwy] += 1

        if hwy in major_set:
            major_road_m += length
        if hwy in walk_friendly:
            walk_friendly_m += length

    major_pct = 100.0 * major_road_m / total_len if total_len > 0 else 0.0
    walk_pct = 100.0 * walk_friendly_m / total_len if total_len > 0 else 0.0

    top_types = ", ".join([f"{t}" for t, _ in hwy_counts.most_common(4)])

    # Make the text more discriminative so SBERT can rank routes better
    text = (
        f"Walking route of {total_len/1000:.2f} km. "
        f"Top ways: {top_types}. "
        f"{walk_pct:.1f}% on footpaths/paths/pedestrian ways. "
        f"{major_pct:.1f}% on major roads. "
        f"Prefer calm routes with more footpaths and fewer major roads."
    )
    return text, total_len, major_pct, walk_pct

# ----------------------------
# 5) Build route descriptions
# ----------------------------
route_texts = []
route_meta = []

for i, r in enumerate(routes):
    txt, dist_m, major_pct, walk_pct = route_features_to_text(G, r)
    route_texts.append(txt)
    route_meta.append({
        "idx": i,
        "dist_m": dist_m,
        "major_pct": major_pct,
        "walk_pct": walk_pct
    })

# ----------------------------
# 6) SBERT rank routes by preference prompt
# ----------------------------
model = SentenceTransformer("all-MiniLM-L6-v2")  # strong + fast baseline

emb_routes = model.encode(route_texts, normalize_embeddings=True)
emb_user = model.encode([user_pref], normalize_embeddings=True)

scores = cosine_similarity(emb_user, emb_routes)[0]
ranking = np.argsort(-scores)  # descending
topk = ranking[:5]

print("\nTop-5 ranked routes:")
for rank, idx in enumerate(topk, 1):
    m = route_meta[idx]
    print(
        f"{rank}) Route {idx}: score={scores[idx]:.3f}, "
        f"dist={m['dist_m']/1000:.2f} km, "
        f"walk_friendly={m['walk_pct']:.1f}%, "
        f"major={m['major_pct']:.1f}%"
    )
    print("   ", route_texts[idx])

# ----------------------------
# 7) Plot the best route
# ----------------------------
best_idx = int(topk[0])
best_route = routes[best_idx]

fig, ax = ox.plot_graph_route(G, best_route, route_linewidth=4, node_size=0, bgcolor="white")
plt.show()