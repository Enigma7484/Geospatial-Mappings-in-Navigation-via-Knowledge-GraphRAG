# Background Flow

This document explains the background research pipeline from OSM public GPS trackpoints to profile-aware route ranking and evaluation.

## 1. OSM Trace Probe

**Code:** `scripts/osm_history_probe.py`  
**Inputs:** A Toronto/UofT bounding box and the OSM public GPS trackpoints endpoint.  
**Outputs:** Raw GPX files and probe summaries in `data/osm_history_probe/`.

The probe requests public GPS trackpoints from OpenStreetMap for a fixed bounding box:

```text
west=-79.405, south=43.645, east=-79.375, north=43.670
```

For each page, it saves:

- `osm_trackpoints_page_0.gpx`, `osm_trackpoints_page_1.gpx`, ...
- `trackpoints_preview.json`
- `summary.json`

Research interpretation:

- These points are public OSM trace samples in an area.
- They may contain timestamps and track/segment structure.
- They are not guaranteed to be clean per-user histories.
- They should be described as OSM-derived historical movement signals.

## 2. Timestamp and Segment Analysis

**Code:** `scripts/analyze_osm_trackpoints.py`  
**Inputs:** Raw GPX files from the probe.  
**Output:** `data/osm_history_probe/trackpoints_analysis.json`.

The analysis script:

1. Parses all GPX files.
2. Extracts latitude, longitude, timestamp, track index, and segment index where available.
3. Measures timestamp coverage.
4. Sorts timestamped points.
5. Builds pseudo-segments using continuity rules.
6. Filters useful movement-looking segments.

Pseudo-segment split rules:

- Start a new segment when the time gap exceeds 10 minutes.
- Start a new segment when the spatial jump exceeds 500 meters.
- Keep only segments with at least 5 points.

Useful-segment filter:

- Distance at least 0.2 km.
- Average speed between 1 and 80 km/h.

Research interpretation:

- A useful pseudo-segment is evidence of local movement continuity.
- It is not proof of one real user or one real trip.
- This step estimates whether OSM public GPS signals are exploratory-useful for building pseudo-history profiles.

## 3. Approximate Map Matching

**Code:** `scripts/build_osm_trace_histories.py`  
**Inputs:** Useful pseudo-segments from OSM public GPS trackpoints.  
**Outputs:** Map-matching diagnostics inside `data/osm_trace_quality_report.json`.

For each useful pseudo-segment:

1. Build a local OSM walking graph around the segment bounding box.
2. Find nearest OSM graph nodes for every GPS point.
3. Deduplicate consecutive repeated nearest nodes.
4. Connect consecutive matched nodes using shortest paths by OSM edge length.
5. Concatenate shortest-path pieces into a reconstructed OSM route.
6. Drop failed segments where too few nodes or paths are recovered.

Diagnostics include:

- Number of segment points.
- Number of matched points.
- Number of unique matched nodes.
- Attempted node-pair paths.
- Successful node-pair paths.
- Pair success rate.
- Reconstructed route node count.

Research interpretation:

- This is approximate map matching, not a probabilistic or HMM map matcher.
- Strong GPS-to-route distance indicates the reconstructed line stays close to sampled points.
- A high route-distance ratio can indicate overbuilding, loops, or shortest-path stitching artifacts.

## 4. Route Feature Extraction

**Code:** `app/routing.py`, called by `scripts/build_osm_trace_histories.py` and the FastAPI backend.  
**Inputs:** OSM graph, projected graph, nearby park polygons, reconstructed route node list.  
**Outputs:** Route-level feature dictionary.

The feature extractor computes:

- Distance.
- Road-type composition.
- Walking-way exposure.
- Residential/service/major-road exposure.
- Intersections.
- Turns from edge bearings.
- Park proximity.
- Lighting exposure.
- Signals and crossings.
- Tunnel exposure.
- OSM-only safety proxy.
- Natural-language summary.
- Route coordinates.

These features are the shared representation used by both profile construction and route ranking.

## 5. Pseudo-History Profile Construction

**Code:** `scripts/build_osm_trace_histories.py` and `app/profile.py`  
**Inputs:** Reconstructed OSM pseudo-segments with extracted features.  
**Outputs:** `data/user_histories_osm_trace.json`.

Each successful pseudo-segment becomes a history record:

- `timestamp`: segment start time.
- `mode`: `osm_pseudo_trace`.
- `source`: `osm_public_gps_trackpoints`.
- `origin`: first GPS point.
- `destination`: last GPS point.
- `features`: OSM route features plus reconstruction diagnostics such as raw trace distance, speed, route-distance ratio, and GPS-to-route distance.

When the backend or evaluation code builds a dynamic profile:

1. Parse the current request timestamp.
2. Assign temporal context: weekday/weekend, time bucket, season, rush hour.
3. Enrich history records with their temporal context.
4. Select records that match the current context.
5. Average selected route features.
6. Convert averages into feature weights.
7. Apply context adjustments for rush hour, evening/night, weekend, summer, or winter.

Research interpretation:

- These are pseudo-history profiles unless clean user identity is available.
- The profile summarizes repeated movement-feature tendencies from OSM-derived historical movement signals.

## 6. Candidate Route Generation

**Code:** `app/routing.py`  
**Inputs:** Request origin, destination, graph radius, requested number of candidates.  
**Outputs:** Candidate route feature dictionaries and route summary texts.

For live route ranking:

1. Resolve origin and destination by geocoding or direct coordinates.
2. Build an OSM walking graph around the origin.
3. Add edge lengths and bearings.
4. Fetch park/green-area polygons.
5. Annotate graph edges with alternative costs:
   - `length`
   - `scenic_weight`
   - `safe_weight`
   - `simple_weight`
6. Generate k-shortest-path pools under each cost.
7. Interleave unique routes across pools to improve diversity.
8. Extract features and summaries for every candidate.

## 7. Route Ranking

**Code:** `app/main.py`, `app/profile.py`, `app/ranking.py`  
**Inputs:** Candidate route features, optional preference text, optional user/pseudo-user history.  
**Output:** Ranked route list from `/rank-routes`.

Ranking modes:

- `prompt`: encode route summaries and user preference with SBERT, then rank by cosine similarity.
- `profile`: build dynamic profile weights from history and rank by feature-weight score.
- `hybrid`: compute both scores and combine as `0.75 * profile_score + 0.25 * sbert_score`.

The endpoint returns:

- Combined score.
- Component scores where applicable.
- Route features.
- Route summary.
- Route coordinates for mapping.
- Profile summary when profile or hybrid mode is used.

## 8. Evaluation

**Code:** `scripts/build_osm_trace_histories.py`, `scripts/evaluate_geolife_profiles.py`  
**Outputs:** `data/osm_trace_quality_report.json`, `data/osm_trace_ranking_eval.json`, `data/evaluation_results.json`.

The OSM trace pipeline reports two evaluation layers:

1. **Reconstruction quality**
   - Timestamp coverage.
   - Pseudo-segments found.
   - Useful segments found.
   - Useful segment rate.
   - Map-match success rate.
   - GPS-to-route distance.
   - Route-distance ratio.
   - Prototype threshold checks.

2. **Preliminary ranking sanity check**
   - Leave-one-out style evaluation over pseudo-history records.
   - Previous records are used as training history.
   - One record is held out as the observed pseudo-route.
   - Candidate pool contains the held-out route plus recent previous examples.
   - Relevance is computed by feature similarity to the held-out route.
   - Metrics: Hit@1, Hit@3, MRR, NDCG@3.

Research interpretation:

- This is a useful early signal for whether profile ranking behaves plausibly.
- It is not yet a final comparison against top-tier personalized route recommendation baselines.
- Phase 3 should add explicit baselines such as random, shortest-distance, prompt/SBERT, profile, and hybrid ranking.
