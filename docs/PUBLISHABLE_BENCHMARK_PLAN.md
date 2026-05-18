# Publishable Benchmark Plan

The professor's target is correct: a conference-ready paper needs a fair comparison on the **same data** with **recognized metrics** against **credible baselines**. The current OSM pseudo-history evaluation is useful, but it is not yet enough to claim that our method beats prior work.

## Current Position

Current experiment:

- Data: OSM public GPS trackpoints in a Toronto/UofT bounding box.
- History signal: OSM-derived historical movement signals / pseudo-history profiles.
- Task: Generate OSM route candidates for a held-out origin/destination and rank them.
- Metrics: Hit@1, Hit@3, MRR, NDCG@3, feature distance, path F1, NDTW, edit distance, max path distance.

This is an internal fair comparison because all baselines see the same generated candidate pool. It is **not** a direct paper-to-paper comparison because prior systems use different datasets and task definitions.

## Best External Benchmark Direction

The strongest publishable direction is a NASR-compatible route-recovery benchmark:

| Requirement | Target |
|---|---|
| Public data | Porto taxi trajectories, from the ECML/PKDD 2015 Taxi Service Trajectory Prediction Challenge / public mirrors |
| Road network | OpenStreetMap road graph for Porto |
| Task | Given origin, destination, optional context/history, recover or rank the route closest to the observed trajectory |
| Metrics | Precision, Recall, F1, Edit Distance; optionally NDTW and max path distance |
| Baselines | Shortest path, random candidate, profile ranker, prompt/SBERT ablation if text exists or is controlled synthetic, hybrid, and a learned ranker only if enough labels exist |
| External reference | NASR / KDD 2019 for route-recovery task and metrics |

Why Porto:

- It is public and widely used in route/trajectory papers.
- NASR reports using Porto taxi data along with Beijing taxi and Beijing bicycle datasets.
- It lets us move from exploratory public OSM traces to a recognized public trajectory benchmark.

## Role Of Closest Papers

| Paper | Valid role | Same-data comparison now? | What we need |
|---|---|---|---|
| Personalized Route Recommendation Based on User Habits for Vehicle Navigation | Closest conceptual personalized route-ranking baseline | No | Their data is private navigation-service logs. We can borrow baseline structure and metrics, but not claim direct superiority. |
| NASR / KDD 2019 | Main technical benchmark target | Possible future | Use Porto, map-match to OSM, evaluate with Precision/Recall/F1/Edit Distance on route recovery. |
| RICK / KDD 2012 | Reconstruction/uncertain-trajectory reference | Partial future | Add NDTW/max-distance style reconstruction metrics and possibly compare to an uncertain-route reconstruction method. |
| PathGPT / recent LLM route papers | Future prompt/LLM framing | No | Need natural-language constraints or controlled preference text on a public benchmark. |

## What Would Let Us Say "We Beat X"

We can only say our system beats another method if all of these hold:

1. Same dataset or a recognized public benchmark.
2. Same train/test split or clearly reproduced split.
3. Same task definition.
4. Same metrics.
5. A runnable or faithfully reimplemented baseline.
6. Statistical comparison or confidence intervals when possible.

Until then, the correct wording is:

> We compare against internal baselines and align our metrics with prior route-recommendation and uncertain-trajectory work.

Not:

> We directly outperform NASR or the User Habits system.

## Proposed Publication Roadmap

### Stage 1: Current OSM Prototype Evidence

Goal:

- Show the end-to-end system works.
- Show profile ranking improves over shortest-distance on some internal metrics.
- Show reconstruction uncertainty honestly.
- Sell the GUI/API as a working research prototype.

Status:

- Done enough for a project milestone.
- Not enough for a strong conference claim.

### Stage 2: Porto Public Benchmark

Goal:

- Build a Porto trajectory evaluation set.
- Map-match or otherwise convert trajectories into comparable route references.
- Generate OSM route candidates for each origin/destination.
- Evaluate all methods using Precision, Recall, F1, Edit Distance, NDTW, and ranking metrics.

Minimum baselines:

- Random.
- Shortest path.
- Profile ranking.
- Feature-distance nearest candidate.
- Prompt/SBERT only if preference text is created through a controlled protocol and labeled as synthetic.
- Hybrid only when both profile and prompt inputs exist.

Stronger baselines:

- LightGBM ranker once enough labeled route-choice/candidate examples exist.
- NASR official code or a NASR-compatible reproduced baseline if setup is feasible.

Current implementation status:

- Added `scripts/evaluate_porto_candidate_baselines.py`.
- Default input path: `data/porto/train.csv`.
- Outputs:
  - `data/porto_candidate_baseline_comparison.json`
  - `data/porto_candidate_baseline_comparison.csv`
- If the Porto CSV is missing, the script writes a status report with `status = missing_dataset`.
- The first implemented Porto baselines are random, shortest-distance, and profile ranking.
- The current Porto evaluator also reports `oracle_feature_upper_bound` and `oracle_path_upper_bound` rows. These are upper bounds for the generated candidate pool, not deployable methods.
- A trajectory-derived vehicle profile baseline has been added. It uses contextual historical Porto features but emphasizes driving-relevant signals rather than walking signals or stated human preferences.
- Prompt/SBERT and hybrid are explicitly skipped on Porto until preference text exists and is labeled as synthetic or collected.
- A 100-query Porto run has been completed with bootstrap confidence intervals, adaptive anchor reconstruction, a trajectory-derived vehicle profile, and an internal learned feature-ranker baseline. This is real public-dataset output, but it is not a direct NASR comparison until the official external baseline is reproduced under matched data/splits.

Run command:

```powershell
python scripts\evaluate_porto_candidate_baselines.py
```

Prototype-sized run after downloading Porto:

```powershell
python scripts\evaluate_porto_candidate_baselines.py --max-tests 10 --max-rows-to-scan 5000 --sample-stride 100 --k-routes 5 --dist-meters 2500
```

Current 100-query run:

```powershell
python scripts\evaluate_porto_candidate_baselines.py --max-tests 100 --max-rows-to-scan 30000 --sample-stride 20 --k-routes 10 --dist-meters 2500 --bootstrap-samples 1000 --min-anchor-spacing-m 120 --max-anchors 50 --shared-graph-radius-m 8000
```

Larger benchmark runs should increase `--max-tests`, reduce `--sample-stride`, and record runtime/skipped-query diagnostics.

Current 100-query Porto benchmark result:

| Method | Hit@1 | Hit@3 | MRR | NDCG@3 | Mean feature distance | Path F1 | NDTW |
|---|---:|---:|---:|---:|---:|---:|---:|
| Oracle feature upper bound | 1.000 | 1.000 | 1.000 | 0.980 | 1.378 | 0.575 | 0.367 |
| Oracle path upper bound | 1.000 | 1.000 | 1.000 | 1.000 | 1.569 | 0.658 | 0.427 |
| Random | 0.120 | 0.330 | 0.306 | 0.536 | 1.858 | 0.483 | 0.257 |
| Shortest-distance | 0.120 | 0.290 | 0.300 | 0.545 | 1.819 | 0.512 | 0.290 |
| Profile | 0.100 | 0.210 | 0.264 | 0.445 | 1.977 | 0.445 | 0.215 |
| Traj.-vehicle profile | 0.230 | 0.430 | 0.408 | 0.615 | 1.819 | 0.472 | 0.240 |
| Learned feature ranker | 0.216 | 0.454 | 0.401 | 0.597 | 1.725 | 0.477 | 0.269 |
| Prompt/SBERT | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| Hybrid | skipped | skipped | skipped | skipped | skipped | skipped | skipped |

Selected 95% bootstrap confidence intervals:

| Method | Hit@1 CI | Hit@3 CI | MRR CI | NDCG@3 CI | Path F1 CI |
|---|---:|---:|---:|---:|---:|
| Random | [0.060, 0.180] | [0.240, 0.430] | [0.257, 0.364] | [0.492, 0.581] | [0.426, 0.542] |
| Shortest-distance | [0.060, 0.190] | [0.200, 0.370] | [0.249, 0.354] | [0.482, 0.607] | [0.450, 0.571] |
| Profile | [0.050, 0.170] | [0.130, 0.290] | [0.211, 0.319] | [0.383, 0.508] | [0.388, 0.506] |
| Traj.-vehicle profile | [0.150, 0.320] | [0.330, 0.530] | [0.343, 0.475] | [0.561, 0.672] | [0.415, 0.523] |
| Learned feature ranker | [0.144, 0.309] | [0.361, 0.557] | [0.331, 0.470] | [0.533, 0.652] | [0.416, 0.540] |

Interpretation:

- The trajectory-derived vehicle profile improves over shortest-distance and the generic profile on Hit@1, Hit@3, MRR, NDCG@3, and mean feature distance in this 100-query run.
- The learned feature ranker is competitive with the vehicle profile and obtains the best deployable Hit@3 and mean feature distance.
- Adaptive-anchor reconstruction substantially reduces over-stitching: median observed route-distance ratio is 1.222, mean ratio is 1.574, and 20 of 100 evaluated queries remain above ratio 2.0.
- The path oracle reaches 0.658 path F1 and 0.427 NDTW, showing an improved but still limited candidate/reconstruction ceiling.
- Shortest-distance remains strongest among deployable baselines on top-ranked path F1/NDTW, so this is a ranking-metric gain rather than a solved route-recovery result.

### Stage 3: Submission-Ready Claim

The paper becomes much stronger if we can say:

> On a public Porto trajectory benchmark using NASR-style route-overlap metrics, our profile-aware OSM candidate reranker improves over shortest-path and non-personalized candidate-ranking baselines while preserving an interpretable GUI/API workflow.

That is a believable conference story because it combines:

- public data,
- recognized metrics,
- transparent feature/profile modeling,
- fair baselines,
- and a usable product/demo layer.

## Remaining Engineering Tasks

1. Reproduce or wrap a credible external baseline, preferably NASR official code if feasible under matched Porto data/splits.
2. Improve map matching further so path F1/NDTW improve, not only route-distance ratio.
3. Scale beyond 100 successful queries after the external-baseline wrapper is available.
4. Keep the trajectory-derived vehicle profile as the main unsupervised internal method for Porto.
5. Keep prompt/SBERT separate unless real or clearly collected preference text exists.

## Source Notes

- User Habits paper: https://arxiv.org/abs/2409.14047
- NASR paper: https://arxiv.org/abs/1907.08489
- NASR code: https://github.com/bigscity/NASR
- Porto taxi public dataset page: https://archive.ics.uci.edu/dataset/339/taxi%2Bservice%2Btrajectory%2Bprediction%2Bchallenge%2Becml%2Bpkdd%2B2015
- Porto taxi public mirror: https://figshare.com/articles/dataset/Porto_taxi_trajectories/12302165
