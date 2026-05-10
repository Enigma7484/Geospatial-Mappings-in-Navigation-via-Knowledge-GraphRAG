# Framework Flowchart Background

This document explains each box in `docs/framework_diagram.mmd`.

## 1. OSM Public GPS Trackpoints

The pipeline begins with public GPS trackpoints from OpenStreetMap. These are area-level public trace signals, not guaranteed clean per-user histories. The project should describe them as **OSM-derived historical movement signals** unless clean user identity and trip grouping are established.

Current code:

- `scripts/osm_history_probe.py`
- Raw outputs under `data/osm_history_probe/`

## 2. Temporal/Spatial Segmentation

The raw trackpoints are parsed and grouped into movement-like pseudo-segments using timestamp gaps and spatial jumps. A segment is split when the time gap or point-to-point distance is too large.

Current code:

- `scripts/analyze_osm_trackpoints.py`
- `scripts/build_osm_trace_histories.py`

Purpose:

- Estimate whether the public trace sample has enough temporal continuity.
- Build candidate pseudo-trips for exploratory profile construction.

Caution:

- Pseudo-segments are not proof of one real trip or one real user.

## 3. Approximate Map Matching

Each useful pseudo-segment is matched to a local OSM walking graph. The current method maps GPS points to nearest graph nodes, removes consecutive duplicate nodes, and connects node pairs using shortest paths.

Current code:

- `reconstruct_route_from_segment()` in `scripts/build_osm_trace_histories.py`

Diagnostics:

- matched points
- unique matched nodes
- pair success rate
- route nodes
- GPS-to-route distance
- route-distance ratio

Caution:

- This is approximate map matching, not a full probabilistic map matcher.
- Current strict usability fails because median route-distance ratio is above the strict target.

## 4. Route Feature Extraction

The reconstructed OSM route is converted into an interpretable route-feature vector. The same feature extractor is used for generated candidate routes.

Current code:

- `app/routing.py`

Features include:

- distance
- major-road percentage
- walking-way percentage
- residential percentage
- service-road percentage
- intersections
- turns
- park proximity
- safety proxy
- lighting percentage
- traffic signals
- crossings
- tunnel length

Caution:

- `safety_score` is an OSM-only proxy from map tags. It is not a real safety or crime model.

## 5. Dynamic Profile Construction

Pseudo-history records are converted into a dynamic profile for a request context. The profile module parses the request timestamp, selects contextually similar history records, averages route features, and turns those averages into feature weights.

Current code:

- `app/profile.py`

Context fields:

- hour
- day name
- weekday/weekend
- time bucket
- season
- rush-hour flag

Output:

- profile weights
- profile traits
- profile summary text

## 6. Candidate Route Generation

For each route-ranking request or route-candidate evaluation query, the backend generates candidate walking routes from OSM for the origin and destination.

Current code:

- `generate_rankable_routes()` in `app/routing.py`

Candidate generation uses multiple route costs:

- shortest length
- scenic weight
- safe weight
- simple-navigation weight

The resulting routes are interleaved to avoid returning only near-duplicate shortest paths.

## 7. Ranking Modes

The generated candidates can be ranked in several ways.

Current code:

- `app/main.py`
- `app/profile.py`
- `app/ranking.py`
- `scripts/evaluate_route_candidate_baselines.py`

Modes:

- **Random:** baseline chance ordering.
- **Shortest Distance:** non-personalized distance baseline.
- **Profile:** dynamic pseudo-history profile scoring.
- **Prompt/SBERT:** semantic similarity between route summaries and preference text.
- **Hybrid:** backend-style weighted combination of profile and prompt/SBERT scores.

Current limitation:

- Prompt/SBERT and hybrid are skipped for the current OSM pseudo-history evaluation because the records do not include preference text.

## 8. Evaluation Metrics

The evaluation has two layers.

### Reconstruction Quality

These metrics test whether OSM public GPS traces can be turned into plausible pseudo-history records:

- timestamp coverage
- useful segment rate
- map-match success rate
- GPS-to-route distance
- route-distance ratio
- strict/exploratory usability
- failed checks
- per-segment diagnostics

Current result:

- strict prototype usable: `false`
- exploratory usable: `true`
- strict failure reason: route-distance ratio exceeds the strict target

### Ranking Quality

These metrics test whether a ranking method surfaces generated candidates close to the held-out observed pseudo-route:

- Hit@1
- Hit@3
- MRR
- NDCG@3
- mean feature distance

Current corrected evaluator:

- `scripts/evaluate_route_candidate_baselines.py`

Important distinction:

- `scripts/evaluate_baselines.py` is the older history-record ranking sanity check.
- `scripts/evaluate_route_candidate_baselines.py` is the stronger route-candidate ranking evaluation.
