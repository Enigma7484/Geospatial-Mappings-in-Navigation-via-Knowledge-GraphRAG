# Dynamic OSM-Based Profile Routing from Public GPS Trace Signals

Research prototype for preference-aware route ranking with OpenStreetMap. The system generates OSM walking-route candidates, extracts interpretable route-level features, builds dynamic pseudo-history profiles from OSM-derived historical movement signals, and compares random, shortest-distance, profile, prompt/SBERT, and hybrid ranking baselines.

This is not a clean per-user trajectory product yet. Public OSM GPS traces are treated as exploratory movement signals and converted into **pseudo-history profiles**. Use that wording in reports and papers unless a later dataset provides verified user identity and trip labels.

## Current Focus

- FastAPI backend for `/rank-routes`.
- OSMnx-based walking-route candidate generation.
- Route feature extraction from OSM tags and geometry.
- OSM public GPS trackpoint probing and pseudo-segmentation.
- Approximate map matching from public trackpoints to OSM routes.
- Dynamic profile scoring from earlier pseudo-history records.
- Route-candidate baseline evaluation with ranking and path-similarity metrics.
- ACM paper scaffold and research documentation.

GeoLife scripts still exist in `scripts/` as legacy experiments, but they are **not the active research pipeline**.

## Repository Layout

```text
app/
  main.py                         FastAPI app and /rank-routes endpoint
  routing.py                      OSM graph building, candidate routes, feature extraction
  profile.py                      Dynamic profile construction and profile scoring
  ranking.py                      SBERT route-summary ranking
  schemas.py                      API request/response models

scripts/
  osm_history_probe.py            Downloads OSM public GPS trackpoint pages
  analyze_osm_trackpoints.py      Analyzes timestamp coverage and pseudo-segments
  build_osm_trace_histories.py    Builds OSM pseudo-history records and quality reports
  evaluate_baselines.py           Older history-record ranking sanity check
  evaluate_route_candidate_baselines.py
                                  Current fair route-candidate baseline evaluation
  build_geolife_histories*.py     Legacy GeoLife scripts, not current main pipeline
  evaluate_geolife_profiles.py    Legacy GeoLife evaluation script

data/
  user_histories_osm_trace.json   Current OSM-derived pseudo-history records
  osm_trace_quality_report.json   Reconstruction/data-quality report
  route_candidate_baseline_comparison.json
  route_candidate_baseline_comparison.csv
  osm_history_probe/              Raw OSM GPX pages and probe summaries

docs/
  SYSTEM_OVERVIEW.md
  BACKGROUND_FLOW.md
  METRICS.md
  BASELINE_SELECTION_STUDY.md
  EXPERIMENTAL_COMPARISON_STUDY.md
  framework_diagram.mmd
  flowchart_background.md

paper/
  main.tex                        ACM paper scaffold
  sections/                       Draft paper sections
  references.bib                  Bibliography scaffold
```

## Setup

Use Python 3.11 on Windows if possible, matching the current tested environment.

```powershell
python -m pip install -r requirements.txt
```

The SBERT baseline depends on PyTorch. The current working CPU version is pinned in `requirements.txt`:

```text
torch==2.5.1
```

If SBERT fails with a Windows DLL error, reinstall the official CPU wheel:

```powershell
python -m pip install --force-reinstall --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip check
```

## Run The API

```powershell
uvicorn app.main:app --reload
```

Open:

- API root: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

Example `/rank-routes` request:

```json
{
  "origin": {"lat": 43.6451, "lon": -79.3824},
  "destination": {"lat": 43.6568, "lon": -79.3853},
  "preference": "Prefer quieter walking routes near parks and away from major roads.",
  "user_id": "osm_trace_toronto",
  "request_datetime": "2023-10-16T13:25:18+00:00",
  "dist_meters": 4000,
  "k_routes": 5,
  "ranking_mode": "hybrid"
}
```

To use the OSM pseudo-history file for profile or hybrid mode:

```powershell
$env:GEOROUTE_USER_HISTORY_PATH="data/user_histories_osm_trace.json"
uvicorn app.main:app --reload
```

## Main OSM Trace Pipeline

1. Probe OSM public GPS trackpoints:

```powershell
python scripts\osm_history_probe.py --max-pages 5
```

2. Build pseudo-history records and reconstruction reports:

```powershell
python scripts\build_osm_trace_histories.py
```

3. Run the current fair route-candidate baseline experiment:

```powershell
python scripts\evaluate_route_candidate_baselines.py
```

Outputs:

- `data/user_histories_osm_trace.json`
- `data/osm_trace_quality_report.json`
- `data/osm_trace_ranking_eval.json`
- `data/route_candidate_baseline_comparison.json`
- `data/route_candidate_baseline_comparison.csv`

## Current Evaluation Meaning

The current route-candidate evaluation uses leave-one-out testing over OSM pseudo-history records:

1. Earlier records become profile history.
2. The held-out record provides origin, destination, reconstructed route features, and reconstructed route coordinates.
3. The system generates fresh OSM route candidates.
4. The oracle candidate is the generated route closest to the held-out reconstructed route in normalized feature space.
5. Baselines rank the same candidate pool.

Compared baselines:

- `random`
- `shortest_distance`
- `profile`
- `prompt_sbert`
- `hybrid`

Metrics:

- `Hit@1`
- `Hit@3`
- `MRR`
- `NDCG@3`
- mean feature distance
- path precision/recall/F1
- NDTW
- coordinate edit distance
- max path distance

See [docs/EXPERIMENTAL_COMPARISON_STUDY.md](docs/EXPERIMENTAL_COMPARISON_STUDY.md) for current results and interpretation.

## Important Research Caveats

- Do not claim OSM public GPS traces are clean user histories.
- Say **OSM-derived historical movement signals** or **pseudo-history profiles**.
- Synthetic preference text in `data/user_histories_osm_trace.json` is clearly labeled and is only for prompt/SBERT ablation experiments.
- Current results are exploratory, not a direct numerical comparison against prior systems such as NASR, RICK, or Personalized Route Recommendation Based on User Habits.
- The GUI/API demo remains useful, but the research claim depends on baseline alignment, metric clarity, and honest reconstruction diagnostics.

## Research Docs

Use these documents as the research navigation map:

| Document | What it represents |
|---|---|
| [docs/SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md) | Codebase audit. Explains what each app, script, data file, and major module does. Start here when re-orienting to the repository. |
| [docs/BACKGROUND_FLOW.md](docs/BACKGROUND_FLOW.md) | Step-by-step background pipeline: OSM trace probe, segmentation, map matching, feature extraction, profile construction, ranking, and evaluation. |
| [docs/METRICS.md](docs/METRICS.md) | Definitions of reconstruction and ranking metrics, including timestamp coverage, useful segment rate, GPS-to-route distance, route-distance ratio, Hit@K, MRR, and NDCG. |
| [docs/RELATED_WORK_TABLE.md](docs/RELATED_WORK_TABLE.md) | Compact related-work comparison table for the initially selected papers. Useful for paper-writing and professor check-ins. |
| [docs/BASELINE_SELECTION_STUDY.md](docs/BASELINE_SELECTION_STUDY.md) | Broader baseline-selection study. Compares candidate papers by task, dataset availability, code availability, metrics, and whether direct comparison is valid. |
| [docs/EXPERIMENTAL_COMPARISON_STUDY.md](docs/EXPERIMENTAL_COMPARISON_STUDY.md) | Current experiment report. Summarizes route-candidate baseline results, path metrics, reconstruction diagnostics, and honest interpretation. |
| [docs/RESEARCH_GAP_AND_NOVELTY.md](docs/RESEARCH_GAP_AND_NOVELTY.md) | Novelty memo: what prior work does, what this system does, the gap, the defensible baseline story, and what must improve before submission. |
| [docs/framework_diagram.mmd](docs/framework_diagram.mmd) | Mermaid source for the framework diagram: OSM public GPS trackpoints through ranking and evaluation. |
| [docs/flowchart_background.md](docs/flowchart_background.md) | Plain-language explanation of each box in the Mermaid framework diagram. |
| [docs/DEPLOYMENT_RESOURCE_NOTES.md](docs/DEPLOYMENT_RESOURCE_NOTES.md) | Deployment/resource notes for running the project in constrained environments. |

There are also older `.docx` and `.pdf` files in `docs/` from earlier writeups and presentations. Treat the Markdown files above as the current source of truth unless you intentionally update those artifacts.

## Paper Draft

The ACM LaTeX scaffold lives in `paper/`.

```powershell
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The generated PDF is `paper/main.pdf`.

## Legacy GeoLife Notes

GeoLife-related scripts are kept for reference:

- `scripts/build_geolife_histories.py`
- `scripts/build_geolife_histories_osm.py`
- `scripts/evaluate_geolife_profiles.py`

They are not part of the current active experiment path. Do not describe the current project as using GeoLife unless you intentionally revive that dataset and rerun the corresponding pipeline.

## Acknowledgments

- OpenStreetMap contributors and the OSM public GPS trackpoint service.
- OSMnx, NetworkX, GeoPandas, and Shapely for geospatial processing.
- Sentence Transformers and PyTorch for prompt/SBERT ranking.
- FastAPI for the backend API.
