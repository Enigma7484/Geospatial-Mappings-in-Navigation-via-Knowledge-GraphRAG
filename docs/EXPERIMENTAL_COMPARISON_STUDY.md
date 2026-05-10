# Experimental Comparison Study

This note records the first experimental comparison after the broader baseline-selection study. It uses the corrected route-candidate evaluation in `scripts/evaluate_route_candidate_baselines.py`.

## Evaluation Setup

For each held-out OSM pseudo-history record:

1. Use earlier records as the profile history.
2. Generate fresh OSM walking-route candidates for the held-out origin/destination.
3. Treat the held-out reconstructed route features as the observed reference.
4. Select the generated candidate with minimum normalized feature distance to the observed reference as the oracle candidate.
5. Rank the same generated candidate set with each baseline.

This is not a direct reproduction of any external paper. It is an internal, fair comparison where every baseline sees the same generated OSM candidate pool.

## Baselines Compared

| Baseline | Meaning | Status |
|---|---|---|
| random | Chance ranking over generated OSM candidates. | Ran |
| shortest_distance | Non-personalized shortest-distance route ranking. | Ran |
| profile | Dynamic profile ranking from earlier OSM-derived pseudo-history records. | Ran |
| prompt_sbert | Semantic ranking from labeled synthetic preference text and route summaries. | Ran |
| hybrid | Backend-style profile + prompt/SBERT ranking. | Ran |

The rebuilt OSM pseudo-history records now include `preference_text`, but each record labels it as `synthetic_from_osm_reconstructed_route_features`. This text is only for prompt-baseline ablation experiments. It is not original OSM user-provided preference text.

## Metrics

Ranking metrics:

- `Hit@1`: whether the oracle generated candidate is ranked first.
- `Hit@3`: whether the oracle generated candidate is in the top three.
- `MRR`: reciprocal rank of the oracle generated candidate.
- `NDCG@3`: graded ranking quality using feature-distance-derived relevance.
- `mean_feature_distance`: mean feature distance between each method's top-ranked candidate and the held-out observed reference; lower is better.

Paper-aligned path metrics:

- `path_precision`, `path_recall`, `path_f1`: approximate NASR-style route overlap between the top-ranked generated candidate and the held-out reconstructed route, using a 30 meter point-match threshold.
- `path_ndtw`: RICK-style normalized dynamic time warping between generated route coordinates and held-out reconstructed route coordinates; higher is better.
- `path_edit_distance`: approximate NASR-style edit distance over rounded coordinate tokens; lower is better.
- `path_max_distance_m`: RICK-style maximum nearest-point distance between top-ranked generated route and held-out reconstructed route; lower is better.

Important limitation:

The path metrics now use persisted `reconstructed_route_coordinates` from `data/user_histories_osm_trace.json`. They are stronger than the earlier generated-oracle proxy, but still depend on approximate map matching quality.

## Current Results

Run command:

```powershell
python scripts\evaluate_route_candidate_baselines.py
```

Successful route-candidate queries: `8`

| Method | Status | N | Hit@1 | Hit@3 | MRR | NDCG@3 | Mean feature distance | Path F1 | NDTW | Edit distance | Max path distance m |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random | ran | 8 | 0.375 | 0.750 | 0.583 | 0.668 | 2.622 | 0.597 | 0.330 | 210.8 | 179.7 |
| shortest_distance | ran | 8 | 0.250 | 0.625 | 0.456 | 0.690 | 2.579 | 0.601 | 0.344 | 209.4 | 187.1 |
| profile | ran | 8 | 0.375 | 0.625 | 0.540 | 0.727 | 2.582 | 0.630 | 0.351 | 206.9 | 170.6 |
| prompt_sbert | ran | 8 | 0.250 | 0.500 | 0.481 | 0.673 | 2.552 | 0.604 | 0.340 | 209.8 | 183.8 |
| hybrid | ran | 8 | 0.250 | 0.500 | 0.467 | 0.672 | 2.613 | 0.605 | 0.340 | 209.2 | 185.7 |

Output files:

- `data/route_candidate_baseline_comparison.json`
- `data/route_candidate_baseline_comparison.csv`

## Reconstruction Diagnostics For Held-Out References

These diagnostics describe the held-out OSM pseudo-history records used as observed references:

| Diagnostic | Value |
|---|---:|
| total probed OSM trackpoints | 25,000 |
| useful pseudo-segments | 11 |
| mean observed GPS-to-route median distance m | 6.313 |
| median observed GPS-to-route median distance m | 7.407 |
| mean observed route-distance ratio | 2.480 |
| median observed route-distance ratio | 2.409 |

Interpretation:

- GPS-to-route distance is reasonably strong for these held-out references.
- Route-distance ratio is still high, and it got worse after increasing probe pages. The larger dataset gives more test queries but also more reconstruction noise.
- This supports the current claim that OSM-derived historical movement signals are exploratory-useful but not final-clean per-user histories.

## Initial Interpretation

The profile baseline is not a clean winner across every metric:

- It improves over shortest-distance on `Hit@1`, `MRR`, `NDCG@3`, path F1, NDTW, edit distance, and max path distance.
- It trails random on `Hit@3` in this small run.
- It is roughly tied with shortest-distance on mean feature distance.
- Prompt/SBERT now runs after repairing the local PyTorch DLL issue, but because the preference text is synthetic, prompt and hybrid results should be treated as ablations rather than evidence about real stated user preferences.

This is useful but modest. The defensible reading is:

> On the expanded OSM pseudo-history set, dynamic profile ranking improves several graded/path-similarity metrics over shortest-distance, but the sample remains small and noisy, so this is an exploratory comparison rather than a robust external benchmark claim.

Avoid saying:

> The method beats prior personalized route recommendation systems.

## What This Means For External Paper Comparison

Current experiment role by paper:

| Related work | What we can compare now | What is still missing |
|---|---|---|
| Personalized Route Recommendation Based on User Habits | Baseline family: shortest route vs profile-aware ranking. | Their private navigation logs, mean inconsistency rate labels, LightGBM/DCN-v2 setup. |
| NASR / KDD 2019 | Approximate path overlap and edit distance against held-out reconstructed route geometry. | Public route-recovery benchmark with edge-level matching. |
| RICK / KDD 2012 | Reconstruction diagnostics and NDTW-style route similarity against held-out reconstructed route geometry. | Direct uncertain-trajectory top-k route reconstruction benchmark. |
| Context Trails | No direct comparison yet. | Task reframing to POI/trail/contextual recommendation. |
| Recent LLM route papers | No direct comparison yet. | Preference text or natural-language route constraints in the evaluation set. |

## Next Experimental Steps

Highest-value next steps:

1. Add CLI knobs for stricter/looser pseudo-segment thresholds and report threshold sensitivity.
2. Move to a public trajectory dataset such as Porto for more queries and cleaner comparison to NASR-style metrics.
3. Add collected real preference text or a controlled preference survey; keep it separate from synthetic preference text.
4. Add a simple supervised feature-distance or LightGBM ranker only after there are enough labeled examples to avoid fake-looking results.
5. Keep synthetic preference text clearly labeled and separate from any future collected real preference text.
