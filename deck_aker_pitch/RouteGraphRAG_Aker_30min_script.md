# RouteGraphRAG Aker Pitch: 30-Minute Script

## Timing Plan

| Section | Slides | Time |
|---|---:|---:|
| Opening and product thesis | 1-2 | 4 min |
| Product walkthrough | 3-4 | 7 min |
| Architecture deep dive | 5-6 | 8 min |
| Evaluation and caveats | 7 | 4 min |
| Production roadmap | 8 | 4 min |
| Close and discussion setup | 9 | 3 min |

---

## Slide 1: RouteGraphRAG

**Time: 2 minutes**

Thanks for taking the time. I wanted to use this project as the deep dive because it sits right at the intersection of product, data systems, ML ranking, and engineering judgment.

The short version is: RouteGraphRAG is a preference-aware route-ranking system. It takes noisy geospatial signals, builds an interpretable route representation over OpenStreetMap, and ranks route candidates based on a combination of user preference text, dynamic historical profile signals, and route-level features.

The reason I think this is relevant to Aker is that the core pattern is broader than navigation. It is really about taking messy operational data, converting it into a structured knowledge layer, and then using AI to help people make better decisions with evidence attached.

For the interview, I’ll walk through this in six parts: the product thesis, the user-facing flow, the data and reconstruction layer, the system architecture, evaluation, and what I would productionize next.

**Transition:** The first thing I want to ground is the product idea: this is not just a map problem.

---

## Slide 2: A route is an operational decision, not a polyline

**Time: 2 minutes**

The product thesis is that a route is not just geometry. It is a decision under constraints.

For a person walking through a city, the shortest path is not always the best path. Someone might prefer parks, avoid major roads, minimize turns, avoid poorly lit segments, or choose something more familiar at night. So the route needs to be ranked against context and preference, not only distance.

The system has three layers.

First, messy data: public OSM traces, incomplete labels, temporal context, and noisy reconstruction.

Second, structured memory: route features, dynamic profile weights, and summaries derived from the same route representation.

Third, ranked action: candidate routes with component scores and diagnostics, so the system can explain why something was ranked.

That is the connection to Aker’s platform work. In real estate operations or investment workflows, the core challenge is often not “can we call a model?” It is “can we turn messy internal and external signals into a trustworthy decision system?”

**Transition:** Now I’ll show what the product looks like from the API and user-decision point of view.

---

## Slide 3: Ask like a human. Rank like a system.

**Time: 4 minutes**

Here is the product surface.

A user can ask something like: “Prefer quieter walking routes near parks and away from major roads.”

The backend receives origin, destination, preference text, timestamp, user ID, and ranking mode. The timestamp matters because profile preferences can be contextual. A person’s weekday rush-hour route behavior may differ from weekend or evening behavior.

Candidate generation happens first. The system uses OSMnx to build a local walking graph and generates diverse route candidates under different costs: shortest length, scenic weighting, safety-oriented weighting, and simpler paths.

Then ranking can happen in three modes.

Prompt mode uses SBERT semantic similarity between the user’s preference and route summaries.

Profile mode builds a dynamic profile from prior pseudo-history records and scores candidates against learned feature preferences.

Hybrid mode combines both. In the current backend, the weighting is 0.75 profile and 0.25 prompt/SBERT.

The important engineering choice is that every returned route includes component scores, extracted features, summary text, coordinates, and profile explanation. That makes the output inspectable instead of just giving a black-box rank.

**A line to use if asked about why SBERT and not an LLM:** I used SBERT here because the task is semantic matching between short preference text and generated route summaries. It is cheap, deterministic enough for baseline comparison, and easier to evaluate than a generative model in this stage.

**Transition:** The next slide shows why this is hard: the data is not clean.

---

## Slide 4: The model only earns trust if the reconstruction does

**Time: 3 minutes**

This visual shows the actual route-field artifact generated from the current repository data.

The raw signal comes from public OSM GPS trackpoints in a Toronto/UofT bounding box. These are not clean per-user histories. They are public movement signals that may have timestamps and local continuity, but they do not prove identity or clean trip labels.

The pipeline segments those points using temporal and spatial continuity rules, then approximately map-matches them onto the OSM walking graph. From there, each reconstructed route becomes a pseudo-history record with features like distance, road mix, park proximity, turns, lighting, crossings, tunnels, and safety proxy.

The key caveat is that I would never present these as clean user histories. The right wording is “OSM-derived historical movement signals” or “pseudo-history profiles.”

That caveat is not just academic. It changes the product. If the reconstruction is noisy, the API and evaluation need to surface confidence and diagnostics. Otherwise the model may look confident while the underlying data is weak.

**Transition:** With that data reality in mind, here is the system architecture.

---

## Slide 5: One route representation flows through the whole system

**Time: 5 minutes**

This is the core architecture.

Step one is probing OSM public GPS trackpoints. The scripts pull public trackpoint pages for a fixed geographic area.

Step two is segmentation. The system creates pseudo-segments based on time gaps, spatial jumps, minimum point count, minimum distance, and speed bounds.

Step three is map matching. This is approximate rather than probabilistic. It finds nearest OSM graph nodes and stitches them with shortest paths.

Step four is feature extraction. This is one of the most important pieces because it creates the shared representation used by both the profile scorer and the text-based scorer. Features include distance, major-road percentage, walking-path percentage, residential/service exposure, intersections, turns, park proximity, lighting, crossings, signals, tunnels, and safety proxy.

Step five is profile construction. The profile module looks at historical or pseudo-history records, enriches them with temporal context, selects contextually relevant records, averages feature tendencies, and converts them into dynamic weights.

Step six is candidate generation. For a live request, the routing module builds a walking graph and generates multiple candidate routes under different cost functions.

Step seven is ranking. Random and shortest-distance are sanity baselines. Profile, prompt/SBERT, and hybrid are the actual AI ranking modes.

Step eight is evaluation. The project separates reconstruction quality from ranking quality, which I think is essential.

The main architectural principle is that the same route feature object flows through the system. That keeps the system explainable: route summaries are generated from features, profile scores use features, and evaluation can compare feature and path similarity.

**Good technical tradeoff to mention:** I deliberately kept the representation feature-based before adding heavier learned models. With small noisy data, a transparent feature scorer is safer than a learned ranker that may overfit or produce impressive-looking but misleading scores.

**Transition:** The GraphRAG framing is about how that representation becomes useful memory.

---

## Slide 6: The graph is the memory. The language layer is the interface.

**Time: 3 minutes**

The GraphRAG angle is that the graph is not just a visual diagram. It is the memory layer.

Route nodes represent candidate geometry and coordinates. Feature edges represent OSM-derived attributes and tradeoffs. Profile state represents dynamic preference tendencies. Evidence trails attach reconstruction diagnostics and metric context to the answer.

Then the language layer becomes an interface over structured evidence. It can explain, for example, that a route was ranked highly because it avoided major roads, had high walking-path exposure, and matched prior weekend behavior, while also warning that the historical profile came from pseudo-history rather than clean user logs.

This is the part I think maps most directly to internal AI platform work. A useful agent should not only generate text. It should retrieve evidence, understand system state, and expose uncertainty.

**Transition:** Now I’ll talk about what the evaluation currently says and where I would be careful.

---

## Slide 7: Profile ranking gives the best graded signal, but the sample is still small

**Time: 4 minutes**

The current evaluation is a route-candidate ranking comparison.

For each held-out pseudo-history record, the system uses earlier records as profile history, generates fresh OSM route candidates for the held-out origin and destination, chooses an oracle candidate by normalized feature similarity to the reconstructed route, and then compares ranking methods on the same candidate pool.

The profile method has the strongest NDCG@3 in the current run, at 0.727. It also has the strongest path F1, at 0.630. It improves over shortest-distance on several metrics, including Hit@1, MRR, NDCG@3, path F1, NDTW, edit distance, and max path distance.

But I would be careful with the claim. There are only eight successful route-candidate queries in this run, and the underlying histories are pseudo-history records. Prompt and hybrid also use synthetic preference text, so I treat those as ablations rather than evidence of real stated preference performance.

The defensible claim is: the prototype shows an end-to-end OSM route-candidate ranking workflow where dynamic profile ranking improves several internal metrics over shortest distance, while explicitly reporting reconstruction uncertainty.

The claim I would avoid is: this beats prior personalized route recommendation systems. That would require cleaner benchmark alignment and more data.

**Transition:** So what would I do next if this had to become a production platform component?

---

## Slide 8: Ship the decision engine, then earn the right to learn

**Time: 4 minutes**

I would productionize in four layers.

First, caching. OSM graph construction can be expensive, so I would cache graph builds by property area, bounding box, and common request regions. For Aker, this could map naturally to known assets, neighborhoods, or operational regions.

Second, observability. I would log ranking inputs, candidate sets, top-k changes, feature weights, component scores, and reconstruction diagnostics. The goal is replayability. If a route rank changes, I want to know whether it changed because the graph changed, profile changed, preference text changed, or scoring changed.

Third, governance. I would keep pseudo-history, synthetic preference text, and clean user-labeled feedback separate. Mixing those sources is how an AI system accidentally overclaims.

Fourth, learning. I would only introduce supervised rankers after collecting enough accept/reject feedback or route-choice labels. Until then, transparent feature scoring is more honest and easier to debug.

For Aker, the general pattern would be the same across AI platform products: ship a useful decision engine, instrument it, collect feedback, and only then add learned optimization where the data supports it.

**Transition:** I’ll close with why I think this project reflects how I would work on the AI platform team.

---

## Slide 9: I can build the AI platform layer between messy data and operational action

**Time: 3 minutes**

The reason I chose this project is that it demonstrates the kind of full-stack AI engineering I think matters for Aker.

It is end-to-end: data pipeline, FastAPI service, ranker, evaluation, and a demo-ready response format.

It shows systems judgment: caching, latency, reproducibility, deployment cost, and observability all matter.

It shows product translation: the same architecture can support investment diligence, property operations, resident experience, or internal knowledge workflows.

And it shows restraint. I am comfortable saying where the data is weak, where the evaluation is promising but not conclusive, and what would need to happen before making stronger claims.

So the closing pitch is: I can help build AI systems that connect messy operational data to decisions, while keeping the evidence trail visible enough for people to trust and improve them.

**Close:** That is the walkthrough. I’m happy to go deeper on the architecture, the ranking logic, the evaluation design, or how I would adapt this pattern to Aker’s internal platform.

---

## Likely Follow-Up Questions

### Why not use a learned ranker immediately?

Because the dataset is small and noisy. A learned ranker would probably overfit and create false confidence. I would first collect clean route-choice labels or accept/reject feedback, then introduce a supervised ranker such as LightGBM or a neural ranker.

### What was the hardest technical tradeoff?

Balancing an end-to-end product demo with honest data caveats. It is easy to make a route-ranking demo look impressive. It is harder to make the evaluation and diagnostics honest enough that the system could mature into production.

### How would this apply to Aker?

The routing domain is an example. The deeper pattern is: ingest operational signals, build a structured knowledge layer, rank or recommend actions, expose evidence, and collect feedback. That maps to site selection, property operations, resident communications, maintenance prioritization, and internal knowledge tools.

### What would you improve first?

I would improve data quality and evaluation scale. Specifically: add a cleaner public benchmark such as Porto, separate real preference text from synthetic text, improve map matching, and build a replayable evaluation harness that runs after every scoring change.

### What makes this GraphRAG instead of simple routing?

The route graph and feature representation act as the retrieval/evidence layer. Natural-language ranking and explanation are grounded in structured route facts, profile state, and reconstruction diagnostics rather than free-form generation.

