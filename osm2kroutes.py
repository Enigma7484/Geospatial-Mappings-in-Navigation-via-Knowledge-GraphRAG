import osmnx as ox
import networkx as nx
from itertools import islice
from collections import Counter

place = "Dhaka, Bangladesh"   # change this
G = ox.graph_from_place(place, network_type="walk")

# Make sure edge lengths exist (meters)
G = ox.add_edge_lengths(G)

print("Nodes:", len(G.nodes), "Edges:", len(G.edges))

orig_address = "Dhaka University, Dhaka"
dest_address = "Ramna Park, Dhaka"

orig_point = ox.geocode(orig_address)
dest_point = ox.geocode(dest_address)

orig_node = ox.distance.nearest_nodes(G, X=orig_point[1], Y=orig_point[0])
dest_node = ox.distance.nearest_nodes(G, X=dest_point[1], Y=dest_point[0])

orig_node, dest_node

def k_shortest_paths(G, source, target, k=10, weight="length"):
    # shortest_simple_paths returns paths ordered by total weight
    paths = nx.shortest_simple_paths(G, source, target, weight=weight)
    return list(islice(paths, k))

routes = k_shortest_paths(G, orig_node, dest_node, k=10, weight="length")
print("Got routes:", len(routes))
print("Example route length (nodes):", len(routes[0]))

def route_edge_data(G, route):
    # Collect edge attributes along the route
    edges = ox.utils_graph.get_route_edge_attributes(G, route, attribute=None)
    return edges

def normalize_highway_tag(hwy):
    # OSM 'highway' can be a list or string
    if isinstance(hwy, list):
        return hwy[0]
    return hwy

def route_features_to_text(G, route):
    edges = route_edge_data(G, route)
    
    total_len = 0.0
    hwy_counts = Counter()
    major_road_m = 0.0

    major_set = {"primary", "secondary", "tertiary", "trunk"}  # big roads
    walk_friendly = {"footway", "path", "pedestrian", "steps", "living_street"}

    for e in edges:
        length = e.get("length", 0.0) or 0.0
        total_len += length
        
        hwy = normalize_highway_tag(e.get("highway", "unknown"))
        hwy_counts[hwy] += 1
        
        if hwy in major_set:
            major_road_m += length

    major_pct = 100.0 * major_road_m / total_len if total_len > 0 else 0.0

    # Summarize top 3 highway types used
    top_types = ", ".join([f"{t}" for t, _ in hwy_counts.most_common(3)])

    text = (
        f"Walking route of {total_len/1000:.2f} km. "
        f"Mostly uses: {top_types}. "
        f"Approx {major_pct:.1f}% on major roads. "
        f"Prefer footways/paths and avoid major roads if possible."
    )
    return text, total_len, major_pct

route_texts = []
route_meta = []

for i, r in enumerate(routes):
    txt, dist_m, major_pct = route_features_to_text(G, r)
    route_texts.append(txt)
    route_meta.append({"idx": i, "dist_m": dist_m, "major_pct": major_pct})

route_texts[0]

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")  # strong + fast baseline

user_pref = "calm walk, avoid busy roads, prefer footpaths and parks, fewer major roads"

emb_routes = model.encode(route_texts, normalize_embeddings=True)
emb_user = model.encode([user_pref], normalize_embeddings=True)

scores = cosine_similarity(emb_user, emb_routes)[0]  # shape: (num_routes,)

ranking = np.argsort(-scores)  # descending
topk = ranking[:5]

for rank, idx in enumerate(topk, 1):
    m = route_meta[idx]
    print(f"{rank}) Route {idx}: score={scores[idx]:.3f}, dist={m['dist_m']/1000:.2f} km, major={m['major_pct']:.1f}%")
    print("   ", route_texts[idx])