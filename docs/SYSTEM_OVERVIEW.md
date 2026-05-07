# System Overview

This document audits the current repository for the research prototype **Dynamic OSM-Based Profile Routing from Public GPS Trace Signals**. It describes what is present in this checkout and how the pieces fit together.

## High-Level Purpose

The system ranks OpenStreetMap walking-route candidates using three modes:

- `prompt`: semantic similarity between route summaries and a natural-language preference.
- `profile`: dynamic profile weights inferred from historical or pseudo-history route records.
- `hybrid`: weighted combination of profile score and prompt/SBERT score.

The research prototype also includes scripts for probing OSM public GPS trackpoints, reconstructing movement-like pseudo-segments, converting them into pseudo-history profiles, and running preliminary ranking sanity checks.

## Repository Root

| File or directory | Purpose |
|---|---|
| `README.md` | General setup and usage notes for the FastAPI route-ranking backend. Some sections describe a broader project vision; use the code/docs in this audit for the current implemented state. |
| `requirements.txt` | Python dependencies for the backend and scripts, including FastAPI, OSMnx, geospatial packages, scikit-learn, and sentence-transformers. |
| `.gitattributes` | Git metadata configuration. |
| `.gitignore` | Ignore rules for local/generated files. |
| `.venv/` | Local Python virtual environment; not part of the research method. |
| `.vscode/` | Local editor configuration. |
| `app/` | FastAPI application and route/profile/ranking logic. |
| `scripts/` | Data processing, OSM probing, pseudo-history generation, and evaluation scripts. |
| `data/` | Generated user histories, OSM probe artifacts, quality reports, and evaluation outputs. |
| `docs/` | Research notes, generated documentation, diagrams, and existing draft artifacts. |
| `plots/` | Generated visual plots/screenshots from experiments. |
| `geolife_raw/` | Expected location for the raw GeoLife trajectory dataset. |
| `misc/` | Earlier exploratory scripts for KG/RAG and OSM route-ranking experiments. |
| `cache/` | Local cache directory, likely used by geospatial tooling or experiments. |

No React frontend files were visible in the current `rg --files` scan of this checkout. The backend CORS configuration is open enough to support a separate React frontend, but the frontend source is not documented here because it is not present in the scanned workspace.

## Backend Application: `app/`

| File | Purpose |
|---|---|
| `app/__init__.py` | Marks `app` as a Python package. |
| `app/schemas.py` | Defines Pydantic request/response models for `/rank-routes`. `RankRoutesRequest` accepts origin, destination, optional preference text, optional `user_id`, request time, graph radius, number of candidates, and `ranking_mode`. `RouteResponse` exposes rank, scores, route features, summary, and coordinates. |
| `app/main.py` | FastAPI entry point. Defines `/` health check and `/rank-routes`. The endpoint generates candidate routes, builds request context, optionally scores candidates with SBERT, optionally builds a dynamic profile from history, combines scores according to `ranking_mode`, sorts candidates, and returns ranked route responses. |
| `app/routing.py` | OSM route-generation and feature-extraction engine. It geocodes inputs, builds an OSM walking graph with OSMnx, fetches nearby park polygons, annotates edges with custom scenic/safe/simple costs, generates diverse candidate routes, computes OSM-derived route features, produces route summaries, and returns route coordinates. |
| `app/profile.py` | Loads user history records, constructs temporal context from the request timestamp, selects contextually similar records, computes average historical feature preferences, builds dynamic feature weights, summarizes the profile in text, and scores candidate routes against the profile. |
| `app/ranking.py` | Lazy-loads `sentence-transformers/all-MiniLM-L6-v2` and computes cosine similarity between route summaries and user preference text for prompt-based ranking. |

## Core Backend Flow

1. `RankRoutesRequest` arrives at `/rank-routes`.
2. `app.profile.get_request_context()` converts `request_datetime` into hour, day type, season, and rush-hour context.
3. `app.routing.generate_rankable_routes()` builds a walking graph and candidate OSM routes.
4. `app.routing.compute_route_features()` extracts route-level features:
   - `distance_km`
   - `major_pct`
   - `walk_pct`
   - `residential_pct`
   - `service_pct`
   - `intersections`
   - `turns`
   - `park_near_pct`
   - `min_park_dist_m`
   - `safety_score`
   - `lit_pct`
   - `signal_cnt`
   - `crossing_cnt`
   - `tunnel_m`
   - `summary`
   - `coordinates`
5. Depending on `ranking_mode`, routes are scored by SBERT, profile weights, or both.
6. Routes are sorted by descending combined score and returned to the caller.

## Route Feature Meanings

| Feature | Meaning |
|---|---|
| `distance_km` | OSM route length in kilometers. |
| `major_pct` | Percent of route length on major road classes such as primary, secondary, tertiary, and trunk links. |
| `walk_pct` | Percent of route length on walking-oriented ways such as footway, path, pedestrian, steps, living street, cycleway, and track. |
| `residential_pct` | Percent of route length on residential or unclassified streets. |
| `service_pct` | Percent of route length on service roads. |
| `intersections` | Count of route nodes with graph degree greater than 2. |
| `turns` | Approximate count of bearing changes above 45 degrees. |
| `park_near_pct` | Percent of route length within park-proximity threshold in the feature extractor. |
| `min_park_dist_m` | Minimum projected distance from route geometry to nearby park polygon. |
| `safety_score` | OSM-only proxy score combining lighting, road type, crossings, signals, and tunnel exposure. It is not a crime or true safety model. |
| `lit_pct` | Percent of route length on edges tagged `lit=yes`. |
| `signal_cnt` | Count of route nodes tagged as traffic signals. |
| `crossing_cnt` | Count of route nodes tagged as crossings or carrying crossing metadata. |
| `tunnel_m` | Route length in meters tagged as tunnel or tunnel-like passage. |
| `summary` | Natural-language route description used for prompt/SBERT ranking. |
| `coordinates` | Ordered latitude/longitude route coordinates for visualization. |

## Profile Logic

`app/profile.py` expects history records shaped like:

```json
{
  "timestamp": "2023-10-16T13:25:18+00:00",
  "mode": "osm_pseudo_trace",
  "origin": {"lat": 43.645, "lon": -79.382},
  "destination": {"lat": 43.656, "lon": -79.385},
  "features": {
    "distance_km": 2.0,
    "major_pct": 12.0
  }
}
```

By default the backend reads `data/user_histories.json`. The environment variable `GEOROUTE_USER_HISTORY_PATH` can override that path, including to `data/user_histories_osm_trace.json` for OSM-derived pseudo-history experiments.

Dynamic profile construction:

1. Parse the request timestamp.
2. Compute context: day type, time bucket, season, rush-hour flag.
3. Enrich history records with their own temporal context.
4. Select records close to the current context.
5. Average feature values across selected records.
6. Convert averages and context into feature weights.
7. Score candidate routes by rewarding desired features and penalizing avoided features.

## Scripts

| File | Purpose |
|---|---|
| `scripts/osm_history_probe.py` | Queries the OSM public GPS trackpoints endpoint for a Toronto/UofT bounding box. Saves raw GPX pages, a preview JSON, and a probe summary under `data/osm_history_probe/`. |
| `scripts/analyze_osm_trackpoints.py` | Parses downloaded OSM GPX files, summarizes timestamp coverage and bounding boxes, reconstructs temporal/spatial pseudo-segments, filters movement-looking segments, and writes `data/osm_history_probe/trackpoints_analysis.json`. |
| `scripts/build_osm_trace_histories.py` | Builds OSM-derived pseudo-history profiles. It loads OSM public trackpoints, segments them, filters useful segments, constructs local OSM walking graphs, approximately map-matches points to nearest nodes and shortest paths, extracts route features, writes `data/user_histories_osm_trace.json`, writes `data/osm_trace_quality_report.json`, and runs a preliminary leave-one-out profile-ranking sanity check in `data/osm_trace_ranking_eval.json`. |
| `scripts/build_geolife_histories.py` | Parses raw GeoLife `.plt` files, infers walking-like trajectories from speed statistics, builds simple GPS-derived history features, and writes `data/user_histories.json`. |
| `scripts/build_geolife_histories_osm.py` | OSM-enriches GeoLife walking-like trajectories by approximate map matching against OSM walking graphs and extracting the same route features used by the backend. Writes `data/user_histories_osm.json`. |
| `scripts/evaluate_geolife_profiles.py` | Preliminary evaluation for GeoLife-style histories. It generates candidate OSM routes for held-out trips, ranks with profile scoring, selects an oracle candidate by feature similarity to the held-out trip, and writes `data/evaluation_results.json`. |

## Data Artifacts

| File or directory | Purpose |
|---|---|
| `data/user_histories.json` | Default backend history file, generally produced from GeoLife-style trajectory processing. |
| `data/user_histories_osm_trace.json` | Pseudo-history profile records derived from OSM public GPS trackpoints. These should be described as OSM-derived historical movement signals, not clean per-user histories. |
| `data/evaluation_results.json` | Output from GeoLife profile evaluation. |
| `data/osm_trace_quality_report.json` | Quality report for OSM trace reconstruction, including timestamp coverage, segment counts, map-match success, GPS-to-route distance, route-distance ratio, and prototype usability checks. |
| `data/osm_trace_ranking_eval.json` | Preliminary leave-one-out ranking sanity check over OSM pseudo-history records. |
| `data/osm_history_probe/osm_trackpoints_page_*.gpx` | Raw downloaded OSM public GPS trackpoint pages. |
| `data/osm_history_probe/summary.json` | Probe-level summary from OSM public GPS trackpoint download. |
| `data/osm_history_probe/trackpoints_preview.json` | Preview sample of parsed OSM trackpoints. |
| `data/osm_history_probe/trackpoints_analysis.json` | Analysis of timestamp coverage and pseudo-segment usefulness. |

## Existing Docs and Visual Artifacts

| File or directory | Purpose |
|---|---|
| `docs/Related Work and Novelty Memo.docx` | Existing document draft related to novelty/positioning. Not source code; use as prior research-writing material. |
| `docs/Evaluation Metrics Comparison.pdf` | Existing PDF artifact comparing evaluation metrics. |
| `docs/Dynamic Preference-Aware Route Ranking from User History and Temporal Context.docx` | Existing research-document draft. |
| `plots/*.png` | Experiment plots and screenshots from previous runs. They are useful for reports but are generated artifacts rather than executable source. |

## Miscellaneous Experiments

| File | Purpose |
|---|---|
| `misc/osm2kroutes.py` | Earlier standalone Toronto route-ranking prototype. It builds an OSM walking graph, generates k-shortest routes, extracts route features, ranks with SBERT, prints route descriptions, and plots the best route. Much of its logic has been moved into `app/routing.py` and `app/ranking.py`. |
| `misc/text2kg.py` | Exploratory text-to-knowledge-graph helper using spaCy entity extraction plus Wikidata lookup/SPARQL. It is not currently integrated into the FastAPI route-ranking path. |

## Current Research Caveats

- OSM public GPS trackpoints should not be presented as clean user histories unless clean user identity and trip grouping are established.
- The current OSM trace pipeline produces pseudo-history profiles from OSM-derived historical movement signals.
- Map matching is approximate: nearest-node matching plus shortest paths between deduplicated nodes.
- The current ranking evaluation is a sanity check using feature similarity to a held-out pseudo-route, not a final human route-choice benchmark.
- The backend is runnable on Windows, but OSMnx/network calls require internet access and compatible geospatial dependencies.
