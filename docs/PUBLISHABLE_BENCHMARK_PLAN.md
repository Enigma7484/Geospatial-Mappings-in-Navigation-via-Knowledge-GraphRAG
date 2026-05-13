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

> We beat NASR or User Habits.

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
- If the Porto CSV is missing, the script writes a placeholder report with `status = missing_dataset`.
- The first implemented Porto baselines are random, shortest-distance, and profile ranking.
- The current Porto evaluator also reports `oracle_feature_upper_bound` and `oracle_path_upper_bound` rows. These are upper bounds for the generated candidate pool, not deployable methods.
- A vehicle-aware unsupervised profile baseline has been added. It uses contextual historical Porto features but emphasizes driving-relevant signals rather than walking signals.
- Prompt/SBERT and hybrid are explicitly skipped on Porto until preference text exists and is labeled as synthetic or collected.
- A scaled prototype run has been completed on 50 sampled Porto queries with bootstrap confidence intervals. This is real public-dataset output, but it is not yet large enough or baseline-complete enough for a paper claim.

Run command:

```powershell
python scripts\evaluate_porto_candidate_baselines.py
```

Prototype-sized run after downloading Porto:

```powershell
python scripts\evaluate_porto_candidate_baselines.py --max-tests 10 --max-rows-to-scan 5000 --sample-stride 100 --k-routes 5 --dist-meters 2500
```

Current 50-query run:

```powershell
python scripts\evaluate_porto_candidate_baselines.py --max-tests 50 --max-rows-to-scan 12000 --sample-stride 50 --k-routes 8 --dist-meters 2500 --bootstrap-samples 1000 --min-anchor-spacing-m 80 --max-anchors 60
```

Larger benchmark runs should increase `--max-tests`, reduce `--sample-stride`, and record runtime/skipped-query diagnostics.

Current 50-query Porto prototype result:

| Method | Hit@1 | Hit@3 | MRR | NDCG@3 | Mean feature distance | Path F1 | NDTW |
|---|---:|---:|---:|---:|---:|---:|---:|
| Oracle feature upper bound | 1.000 | 1.000 | 1.000 | 1.000 | 2.104 | 0.541 | 0.236 |
| Oracle path upper bound | 1.000 | 1.000 | 1.000 | 1.000 | 2.307 | 0.590 | 0.261 |
| Random | 0.180 | 0.620 | 0.441 | 0.605 | 2.317 | 0.514 | 0.225 |
| Shortest-distance | 0.100 | 0.380 | 0.310 | 0.509 | 2.385 | 0.515 | 0.215 |
| Profile | 0.120 | 0.400 | 0.342 | 0.517 | 2.374 | 0.451 | 0.169 |
| Vehicle profile | 0.260 | 0.600 | 0.478 | 0.732 | 2.226 | 0.501 | 0.196 |
| Prompt/SBERT | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| Hybrid | skipped | skipped | skipped | skipped | skipped | skipped | skipped |

Selected 95% bootstrap confidence intervals:

| Method | Hit@1 CI | Hit@3 CI | MRR CI | NDCG@3 CI | Path F1 CI |
|---|---:|---:|---:|---:|---:|
| Random | [0.080, 0.281] | [0.480, 0.760] | [0.367, 0.523] | [0.538, 0.674] | [0.442, 0.586] |
| Shortest-distance | [0.020, 0.200] | [0.240, 0.520] | [0.245, 0.380] | [0.419, 0.604] | [0.445, 0.586] |
| Profile | [0.040, 0.220] | [0.260, 0.540] | [0.273, 0.417] | [0.419, 0.613] | [0.384, 0.516] |
| Vehicle profile | [0.140, 0.400] | [0.440, 0.720] | [0.393, 0.569] | [0.649, 0.808] | [0.435, 0.566] |

Interpretation:

- The vehicle-aware profile improves over shortest-distance and the generic profile on Hit@1, Hit@3, MRR, NDCG@3, and mean feature distance in this 50-query run.
- Random remains close on Hit@3 and path metrics, so this is not yet a decisive superiority result.
- Diverse vehicle candidate generation improves the path-oracle ceiling relative to the earlier five-candidate setup.
- The simplified-anchor reconstruction reduces over-stitching modestly: mean observed route-distance ratio falls from about 2.82 to 2.69, median ratio falls from 2.17 to 2.04, and high-ratio cases fall from 29 to 28 of 50 queries.
- The path oracle still reaches only 0.590 path F1 and 0.261 NDTW. This shows that candidate generation and/or reconstruction quality remains a major bottleneck.
- This result is useful as an engineering milestone, not as a publishable superiority claim.

### Stage 3: Submission-Ready Claim

The paper becomes much stronger if we can say:

> On a public Porto trajectory benchmark using NASR-style route-overlap metrics, our profile-aware OSM candidate reranker improves over shortest-path and non-personalized candidate-ranking baselines while preserving an interpretable GUI/API workflow.

That is a believable conference story because it combines:

- public data,
- recognized metrics,
- transparent feature/profile modeling,
- fair baselines,
- and a usable product/demo layer.

## Immediate Next Engineering Tasks

1. Increase the Porto benchmark to at least 100 successful queries.
2. Improve map matching and reduce route-distance-ratio failures.
3. Generate a more diverse candidate pool so the oracle upper bound improves on path F1/NDTW.
4. Keep the vehicle-aware profile as the main unsupervised internal method for Porto.
5. Reproduce or wrap a credible external baseline, preferably NASR official code if feasible.
6. Update the LaTeX evaluation/results sections with larger Porto public-benchmark results.

## Source Notes

- User Habits paper: https://arxiv.org/abs/2409.14047
- NASR paper: https://arxiv.org/abs/1907.08489
- NASR code: https://github.com/bigscity/NASR
- Porto taxi public dataset page: https://archive.ics.uci.edu/dataset/339/taxi%2Bservice%2Btrajectory%2Bprediction%2Bchallenge%2Becml%2Bpkdd%2B2015
- Porto taxi public mirror: https://figshare.com/articles/dataset/Porto_taxi_trajectories/12302165
