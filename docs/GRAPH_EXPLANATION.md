# What Graph Is at Play?

## Main Graph

The main graph is the OpenStreetMap road/path network graph.

- Nodes are intersections, road junctions, and map points.
- Edges are roads, paths, or driveable/walkable segments connecting nodes.
- Edge attributes include length, road type, geometry, lighting tags, crossings, tunnel tags, and related OSM metadata when available.

## How the Graph Is Used

The system uses the OSM graph for:

- Nearest-node map matching from GPS points to graph nodes.
- Shortest-path stitching between matched GPS anchors.
- Candidate route generation for an origin-destination query.
- Route feature extraction from candidate and reconstructed paths.

## What the Current System Is Not Yet

The current system is not a full knowledge graph or GraphRAG system yet. It uses a graph, but that graph is primarily the OSM transportation network. There is not yet a separate semantic knowledge graph retrieval layer driving the ranking.

## Future Semantic Preference Graph

A future extension could build a semantic preference graph such as:

```text
User -> prefers -> scenic route
Route -> near -> park
Route -> has_feature -> low turns
Context -> rush_hour -> changes preference
```

That semantic graph could connect user preferences, route attributes, places, and context. It would make a stronger GraphRAG claim only if the system actually retrieves from that knowledge graph during ranking or explanation.
