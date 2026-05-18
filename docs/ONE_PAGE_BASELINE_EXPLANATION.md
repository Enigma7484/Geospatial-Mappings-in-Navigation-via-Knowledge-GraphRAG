# One-Page Baseline Explanation

## What This System Does

This project builds an interpretable OSM route-ranking system. For an origin-destination query, it generates route candidates from OpenStreetMap, extracts route-level features, builds contextual pseudo-history profiles from OSM-derived historical movement signals or public trajectory records, and reranks the candidates with profile, prompt, or hybrid scoring.

The current claim is not that OSM public traces are clean per-user histories. The claim is that profile-aware OSM candidate reranking can be evaluated transparently with reconstruction diagnostics and public-data baselines.

## Closest Conceptual Baseline

**Personalized Route Recommendation Based on User Habits for Vehicle Navigation** is the closest conceptual baseline.

Why it is close:

- It studies personalized route sorting.
- It uses historical navigation behavior.
- It compares personalized ranking against minimum-ETA and learned ranking baselines.
- It asks a similar high-level question: can historical behavior improve route ordering?

Why it is not directly comparable yet:

- It uses private navigation-service logs.
- It assumes cleaner user-history and route-choice labels than OSM public traces provide.
- Its metric setup depends on those private route-choice labels.

Valid comparison role:

- Conceptual motivation for profile-based route sorting.
- Metric and baseline inspiration.
- Not the main direct numerical baseline unless comparable private or collected route-choice data becomes available.

## Closest Top-Tier Technical Baseline

**NASR: Empowering A* Search Algorithms with Neural Networks for Personalized Route Recommendation** is the closest top-tier technical benchmark target.

Why it matters:

- It is KDD 2019.
- It addresses origin-destination route recovery/search.
- It reports recognized path-level metrics such as precision, recall, F1, and edit distance.
- It uses trajectory data and road graphs, which aligns better with a public Porto trajectory benchmark.

Why we do not claim to beat it yet:

- NASR changes route search itself, while the current system reranks generated OSM candidates.
- A fair comparison requires matched data, splits, graph construction, and metrics.
- The current paper has a 100-query Porto benchmark, but not a reproduced NASR baseline.

Valid comparison role:

- Main future external baseline.
- The Porto benchmark is the bridge toward this comparison.

## Current Fair Claim

The strongest current claim is:

> On a public Porto trajectory benchmark, a trajectory-derived vehicle profile improves over shortest-distance and generic profile ranking on several ranking metrics, while path metrics identify map matching and candidate generation as the next technical bottlenecks.

This is stronger and safer than claiming:

> We directly outperform NASR.

The current paper establishes the system, evaluation protocol, and public-dataset evidence needed to move toward that stronger external comparison.

## What Must Improve Next

1. Reproduce an external baseline, ideally NASR-style route recovery under matched Porto data/splits.
2. Improve map matching further so path overlap improves, not only route-distance ratio.
3. Scale beyond 100 successful queries after the external-baseline wrapper is in place.
4. Keep prompt/SBERT results separate unless real or clearly collected preference text exists.
5. Preserve the GUI/API demo as the product-facing proof that the method can be inspected and used, not only scored offline.
