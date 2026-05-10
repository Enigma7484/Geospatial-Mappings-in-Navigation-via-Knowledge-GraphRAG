# Research Gap And Novelty

This memo states the current research position for **Dynamic OSM-Based Profile Routing from Public GPS Trace Signals**. It is intentionally conservative: the project is a research prototype, not a finished claim that public OSM GPS traces are clean per-user histories.

## What Existing Papers Do

Closest prior work falls into three groups:

1. **Personalized route recommendation from user habits**
   - Papers such as *Personalized Route Recommendation Based on User Habits for Vehicle Navigation* use historical navigation behavior, route features, user profiles, and ranking/sorting models.
   - These works are closest conceptually because they compare personalized ranking against non-personalized and learned baselines.
   - The limitation for direct comparison is that their datasets are often private navigation logs with real user route-choice labels.

2. **Personalized route search / route recovery**
   - NASR / *Empowering A* Search Algorithms with Neural Networks for Personalized Route Recommendation* frames route recommendation as origin-destination route recovery and neuralized search.
   - It uses trajectory datasets and metrics such as precision, recall, F1, and edit distance.
   - This is a top-tier methodological reference, but our current system reranks generated OSM candidates rather than learning the route-search process end to end.

3. **Uncertain trajectory reconstruction**
   - RICK / *Constructing Popular Routes from Uncertain Trajectories* focuses on reconstructing likely routes from sparse or uncertain observations.
   - This is relevant to our OSM trace reconstruction quality and honesty about noisy public trace signals.
   - It is not a direct personalized route-ranking baseline.

Recent LLM/contextual route papers are useful for positioning prompt-based or context-aware extensions, but most do not directly match the current OSM pseudo-history ranking task.

## What This System Currently Does

The prototype:

- Probes OSM public GPS trackpoints in a Toronto/UofT bounding box.
- Segments timestamped public trackpoints into movement-like pseudo-segments.
- Approximately map-matches segments to OSM walking routes.
- Extracts route-level OSM features such as distance, road-type percentages, intersections, turns, parks, lighting, crossings, tunnels, and a safety proxy.
- Builds dynamic pseudo-history profiles from earlier OSM-derived historical movement signals.
- Generates OSM walking-route candidates for a held-out origin/destination.
- Ranks candidates using random, shortest-distance, profile, prompt/SBERT, and hybrid baselines.
- Reports reconstruction diagnostics and ranking/path-similarity metrics.

## Gap Between Prior Work And This Project

The main gap is not simply “personalized routing exists.” It is:

> Can public OSM-derived historical movement signals be turned into transparent pseudo-history profiles that support preference-aware OSM route-candidate ranking, while honestly reporting reconstruction uncertainty?

This differs from prior work because:

- We do not assume private navigation logs with clean user choices.
- We focus on OSM walking-route features and an inspectable GUI/API prototype.
- We separate trace reconstruction quality from route-ranking quality.
- We evaluate profile ranking against internal baselines on the same generated candidate pool.

## Baseline We Need To Beat

Near term:

- Random ranking.
- Shortest-distance ranking.
- Prompt/SBERT ranking when preference text exists.
- Profile ranking.
- Hybrid ranking.

Research-facing baseline role:

- Use *Personalized Route Recommendation Based on User Habits for Vehicle Navigation* as the closest conceptual baseline.
- Use NASR as the strongest top-tier future technical benchmark if we move to public route-recovery data and metrics.
- Use RICK as the reconstruction-quality reference for uncertain trajectories.

Do not claim direct superiority over those papers with the current data.

## Why The Current OSM Trace Pipeline Is Exploratory

The OSM public GPS trace data is useful, but not final-clean:

- Public trackpoints are not guaranteed to belong to one verified user.
- Segment continuity is inferred from time gaps and spatial jumps.
- Approximate map matching can overbuild routes.
- The current quality report shows strong GPS-to-route distance but route-distance ratios that can exceed strict thresholds.
- Synthetic preference text is generated from reconstructed route features and must not be treated as original user preference text.

Best wording:

> OSM-derived historical movement signals

or:

> pseudo-history profiles

Avoid:

> clean user history

unless a later dataset actually provides clean user identity and trip labels.

## What Must Improve Before Submission

Highest-priority improvements:

1. Increase evaluation size with more OSM segments or a public trajectory dataset such as Porto.
2. Add threshold-sensitivity experiments for segmentation and map matching.
3. Report reconstruction and ranking results separately.
4. Add route-overlap metrics aligned with NASR-style evaluation.
5. Add uncertainty/reconstruction metrics aligned with RICK-style evaluation.
6. Collect real preference text or run a controlled preference study if prompt/hybrid ranking is a central claim.
7. Add learned baselines such as LightGBM only when there are enough labeled examples to avoid misleading results.

## Defensible Current Claim

Use:

> The prototype shows an end-to-end OSM-based route-candidate ranking workflow that converts public GPS trace signals into pseudo-history profiles, compares profile-aware ranking against internal baselines, and reports reconstruction uncertainty explicitly.

Avoid:

> The system beats prior personalized route recommendation models.

That stronger claim requires dataset and metric alignment with the external baselines.

