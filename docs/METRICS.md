# Metrics

This document defines the current data-quality, reconstruction-quality, and ranking metrics used by the prototype.

## Notation

Let:

- `P` be all parsed GPS trackpoints.
- `P_t` be trackpoints with valid timestamps.
- `S` be all reconstructed pseudo-segments.
- `S_u` be useful pseudo-segments after filtering.
- `M` be map-matching attempts.
- `M_s` be successful map-matching attempts.
- `r_i` be the reconstructed OSM route for segment `i`.
- `g_i` be the raw GPS polyline or point sequence for segment `i`.
- `C_q` be candidate routes for evaluation query `q`.
- `y_q` be the held-out observed or oracle candidate for query `q`.

## Timestamp Coverage

**Definition:** Fraction of parsed GPS trackpoints with valid timestamps.

```text
timestamp_coverage = |P_t| / |P|
```

**Purpose:** Measures whether the OSM public GPS trace data has enough temporal information to support continuity-based pseudo-segmentation.

**Interpretation:**

- High coverage supports temporal segmentation.
- Low coverage means segmentation must rely on spatial continuity or external metadata.
- This does not prove clean user identity.

## Useful Segment Rate

**Definition:** Fraction of pseudo-segments that pass movement-usefulness filters.

```text
useful_segment_rate = |S_u| / max(|S|, 1)
```

Current useful-segment filters:

- Segment distance at least 0.2 km.
- Average speed between 1 and 80 km/h.
- In `scripts/build_osm_trace_histories.py`, maximum segment jump must be at most 500 m.

**Purpose:** Estimates whether the raw OSM-derived historical movement signals contain enough movement-like sequences for pseudo-history construction.

**Interpretation:**

- A high rate means many pseudo-segments look movement-like under current heuristics.
- A low rate means the trace sample may be too sparse, fragmented, or noisy.
- It is a heuristic data-quality metric, not a user-history validity guarantee.

## Map-Match Success Rate

**Definition:** Fraction of useful pseudo-segments that successfully produce a reconstructed OSM route.

```text
map_match_success_rate = |M_s| / max(|M|, 1)
```

A segment is successful when:

- GPS points can be matched to at least two OSM graph nodes.
- Shortest paths can connect enough deduplicated matched nodes.
- The reconstructed route has at least two nodes.
- Route features can be extracted.

**Purpose:** Measures the reliability of the approximate nearest-node plus shortest-path reconstruction pipeline.

**Interpretation:**

- High success means most useful segments can be transformed into route-like OSM paths.
- Low success suggests graph coverage, GPS sparsity, topology, or matching issues.
- Success alone does not mean the route geometry is faithful; use GPS-to-route distance and route-distance ratio too.

## GPS-to-Route Distance

**Definition:** Distance from observed GPS points to the reconstructed OSM route geometry after projection into a meter-based CRS.

Current outputs:

```text
gps_to_route_mean_m
gps_to_route_median_m
```

For each point `p` in segment `g_i`:

```text
d(p, r_i) = projected distance from p to reconstructed route line
```

Then compute mean and median across points.

**Purpose:** Measures geometric closeness between sampled GPS points and the reconstructed route.

**Interpretation:**

- Lower is better.
- Low median GPS-to-route distance means typical points lie close to the reconstructed OSM path.
- Mean can be pulled upward by outlier points.
- Strong GPS-to-route distance with poor route-distance ratio may mean the route passes near points but contains excessive detours or overbuilt connectors.

## Route-Distance Ratio

**Definition:** Ratio between reconstructed OSM route length and raw GPS trace distance.

```text
route_distance_ratio = reconstructed_route_distance_km / max(raw_trace_distance_km, 0.001)
```

**Purpose:** Detects overbuilding or underbuilding in approximate map matching.

**Interpretation:**

- Near `1.0`: reconstructed route length is close to raw trace length.
- Much greater than `1.0`: reconstructed route may contain detours, loops, repeated connectors, or shortest-path stitching artifacts.
- Much less than `1.0`: reconstructed route may be oversimplified or skipping observed movement.

The current prototype threshold stores a target range of `[0.5, 2.0]`, while the implemented check currently allows median ratio up to `2.5`. This should be made consistent in Phase 4.

## Hit@1

**Definition:** Fraction of evaluation queries where the observed/oracle candidate is ranked first.

```text
Hit@1 = (1 / Q) * sum_q I(rank_q(y_q) <= 1)
```

**Purpose:** Measures exact top-choice recovery.

**Interpretation:**

- Higher is better.
- Sensitive to candidate-set construction and oracle definition.
- In the current OSM pseudo-history evaluation, the oracle is the held-out record inserted into the candidate set.

## Hit@3

**Definition:** Fraction of evaluation queries where the observed/oracle candidate appears in the top 3.

```text
Hit@3 = (1 / Q) * sum_q I(rank_q(y_q) <= 3)
```

**Purpose:** Measures whether the system surfaces the relevant route near the top, allowing some ranking ambiguity.

**Interpretation:**

- Higher is better.
- Useful for route recommendation because multiple routes may be plausible.
- Less strict than Hit@1.

## Mean Reciprocal Rank (MRR)

**Definition:** Mean reciprocal rank of the observed/oracle candidate.

```text
MRR = (1 / Q) * sum_q 1 / rank_q(y_q)
```

**Purpose:** Rewards placing the observed/oracle route high in the ranking, with a strong penalty as it moves downward.

**Interpretation:**

- `1.0` means every oracle is ranked first.
- Values decline as oracle ranks worsen.
- More informative than Hit@1 when the oracle is usually near the top but not always first.

## NDCG@3

**Definition:** Normalized Discounted Cumulative Gain at rank 3.

For ranked relevance values `rel_1, rel_2, rel_3`:

```text
DCG@3 = sum_{j=1..3} rel_j / log2(j + 1)
NDCG@3 = DCG@3 / IDCG@3
```

where `IDCG@3` is the DCG@3 of the ideal ranking sorted by descending relevance.

**Current relevance definition:** In `scripts/build_osm_trace_histories.py`, candidate relevance is based on normalized feature-space similarity to the held-out pseudo-route:

```text
relevance = 1 - normalized_feature_distance / max_distance
```

**Purpose:** Measures graded ranking quality, not only whether a single oracle candidate appears in the top positions.

**Interpretation:**

- Higher is better.
- Useful when several candidate routes are similar to the held-out route.
- Depends heavily on the relevance definition; the current feature-similarity relevance is preliminary.

## Mean Feature Distance

**Definition:** Average feature-space distance from the held-out observed route to the ranked or selected candidate route, after feature normalization.

Planned for Phase 3 baseline evaluation:

```text
mean_feature_distance = mean_q distance(normalized_features(selected_q), normalized_features(heldout_q))
```

**Purpose:** Measures how close a selected route is to the observed/pseudo-observed route in interpretable feature space.

**Interpretation:**

- Lower is better.
- Complements rank metrics by quantifying route-feature mismatch.
- Should be reported alongside Hit@K/MRR/NDCG to avoid hiding poor route similarity behind rank-only metrics.

## Metric Honesty Notes

- Current OSM-derived ranking metrics are preliminary sanity checks, not final user-choice validation.
- The held-out pseudo-route is produced by the same approximate reconstruction pipeline, so evaluation is not independent ground truth.
- OSM public GPS traces should be called OSM-derived historical movement signals or pseudo-history profiles unless clean user identity is proven.
- Final evaluation should compare against explicit baselines: random, shortest-distance, prompt/SBERT, profile, and hybrid.
