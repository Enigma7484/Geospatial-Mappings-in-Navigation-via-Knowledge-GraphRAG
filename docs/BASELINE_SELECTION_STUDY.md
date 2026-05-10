# Baseline Selection Study

This document broadens the baseline search for **Dynamic OSM-Based Profile Routing from Public GPS Trace Signals**. The goal is not to force one comparison. The goal is to identify which related work is closest by task, dataset availability, code availability, and metric alignment.

## Our Current Task

Current prototype task:

- Generate OSM walking-route candidates for an origin/destination.
- Extract OSM route features.
- Build dynamic profiles from OSM-derived historical movement signals / pseudo-history records.
- Rank candidates using random, shortest-distance, profile, prompt/SBERT, or hybrid modes.
- Evaluate against a held-out pseudo-route by selecting the generated candidate closest in normalized feature space.

Current caveat:

- OSM public GPS traces are not clean per-user histories.
- Current trace reconstruction is exploratory-useful but not strict-clean.
- Prompt/SBERT and hybrid cannot be evaluated on the current OSM pseudo-history file because no preference text exists.

## Candidate Paper Audit

| Paper title | Year / venue | Problem type | Dataset used | Is dataset public? | Is code public? | Metrics used | Same task as ours? | Can we directly compare? | If not, what kind of comparison is valid? | Main-baseline judgment |
|---|---:|---|---|---|---|---|---|---|---|---|
| Personalized Route Recommendation Based on User Habits for Vehicle Navigation | 2024, IDST / ACM ICPS; arXiv preprint | Personalized vehicle route sorting from historical navigation behavior | Private navigation-service logs: about 10,000 private-car users, one month, large candidate-route set across Chinese cities | No, appears private/company data | Unknown. ResearchGate text says code was uploaded to GitHub, but I did not verify a repository URL. TODO: locate official code link or mark no. | mean inconsistency rate (`mean_IR`), AUC; baselines include minimum ETA, LightGBM, DCN-v2 | Partial | No with current data. Direct metric/data reproduction is blocked by private navigation logs and candidate route labels. | Conceptual comparison and metric inspiration. We can say our profile ranking is closest in spirit, but not claim a direct win. We can implement analogous baselines: shortest/ETA-like, LightGBM if enough labels, neural ranker later. | Strong conceptual baseline, weak reproducibility baseline. Should not be the only main baseline unless we obtain comparable logged route-choice data. |
| Empowering A* Search Algorithms with Neural Networks for Personalized Route Recommendation / NASR | 2019, KDD | Personalized route recovery/search for origin-destination queries using neuralized A* | Beijing taxi, Porto taxi, Beijing bicycle trajectories; map matched to OSM road networks | Partial. Porto taxi is public; Beijing taxi/bicycle availability unclear from paper. | Yes. BIGSCity/NASR GitHub is public. | Precision, Recall, F1-score, Edit Distance (EDT); route recovery from source/destination with hidden intermediate path | Partial | Partially, but not with current OSM pseudo-history setup. Direct comparison requires converting our task to route recovery and using overlapping-location/path metrics. | Valid comparison: evaluate our generated top route against held-out path using Precision/Recall/F1/EDT on a public trajectory dataset, probably Porto. Valid role: top-tier methodological reference and possible future benchmark if we adapt data and metrics. | Best top-tier baseline candidate if we shift evaluation to route recovery on public/public-ish data. Too heavy for current prototype-only comparison. |
| Personalized route recommendation using big trajectory data | 2015, ICDE | Personalized driving route recommendation from big taxi trajectories and driver preference costs | Beijing taxi GPS: more than 50 billion GPS records from 52,211 taxis; 32M+ taxi trajectories after trip construction | No / unknown. The paper uses a large proprietary or unavailable Beijing taxi corpus; no public release found. | Unknown / likely no official code found | Preference-model KL divergence, runtime, F-value/F-ratio satisfaction vs Google/Bing/Baidu map routes | Partial | No. Dataset scale and cost model are not available; metrics depend on travel time/fuel cost modeling and commercial-map comparisons. | Valid comparison: conceptual framing for trajectory-derived driver preference, multi-cost route choice, and non-personalized map-service baselines. Could borrow F-ratio idea only if we define our own satisfaction function. | Important historical baseline, but not practical as main experimental baseline for this project. |
| Constructing Popular Routes from Uncertain Trajectories / RICK | 2012, KDD | Top-k popular route construction from uncertain / low-frequency trajectories | Foursquare check-ins in Manhattan and Beijing taxi trajectories; paper simulates uncertain trajectories by resampling | Yes for at least data linked from Microsoft Research page; exact current accessibility of Dropbox data should be verified. | Unknown. No official code found in this pass. | NDTW, maximum distance (MD), effectiveness/efficiency for top-k inferred routes | Partial | Not directly for personalized ranking. It is route inference from uncertain trajectories, not profile-aware candidate ranking. | Valid comparison: reconstruction-quality baseline or related-work anchor for uncertain trajectory handling. We can compare reconstruction metrics conceptually, not profile-ranking performance. | Strong related work for trace reconstruction and honesty about uncertainty. Not a main route-ranking baseline. |
| Context Trails: A Dataset to Study Contextual and Route Recommendation | 2025, ACM RecSys | Public dataset for tourism recommendation, route recommendation, and contextual recommendation | Context Trails: user interactions with touristic venues, itineraries/trails/routes, contextual features such as weather/opening hours | Yes. UAM page states dataset is available on Zenodo. | Yes. UAM page links ContextTrailsExperiments GitHub. | Multiple recommender-system task metrics across classical, route, and contextual recommendation; exact metrics require final paper pass | Partial / no | Not directly with current OSM walking-route ranking. It is tourism POI/itinerary recommendation, not OSM route-path candidate ranking from GPS traces. | Valid comparison: public-dataset alternative for contextual route recommendation. Could use it if we reframe toward itinerary/trail recommendation or add contextual recommendation baselines. | Best public dataset/code candidate, but task mismatch is substantial. Good for dataset inspiration, not main baseline for current routing prototype. |
| Context-Aware Personalized Route Recommendations for Bicycle Users Using Large-Scale Mobility Data | 2024, IEEE COMPSAC | Context-aware personalized bicycle route recommendation | Large-scale bicycle mobility data; details require IEEE full paper access | Unknown | Unknown | Unknown from accessible metadata; TODO: inspect full paper | Partial | Unknown / likely no, unless data/code are public | Valid comparison: literature positioning for context-aware route recommendation and bicycle-specific personalization. | Candidate to investigate further, but not enough public information yet for main baseline selection. |
| Personalized and Context-aware Route Planning for Edge-assisted Vehicles | 2024-era preprint/PDF | Personalized vehicle route planning using GNN + DRL and driver behavior classes | Real-world road network and simulated/edge-assisted vehicle context via SUMO; historical driver behavior used for preference classes | Unknown / likely not packaged as public benchmark | Unknown | Preference satisfaction improvement, travel-time reduction, comparisons to generic and shortest-distance routing | Partial | No with current data. It is simulation/RL route planning, not OSM trace-derived candidate ranking. | Valid comparison: conceptual baseline for profile/context-aware routing and for reporting shortest-distance/generic planner comparisons. | Good recent positioning paper, not direct experimental baseline. |
| A Knowledge Graph-Enhanced Hidden Markov Model for Personalized Travel Routing: Integrating Spatial and Semantic Data in Urban Environments | 2025, Smart Cities | Personalized travel/tour routing using knowledge graph + HMM over spatial/semantic POI data | Urban POI/semantic route data; exact dataset and release status require full paper pass | Unknown | Unknown | Route-quality/personalized travel-routing metrics; TODO: extract exact metrics from paper | Partial / no | No with current OSM route-candidate ranking. More POI/travel-routing than road/path ranking. | Valid comparison: semantic/KG motivation, especially because our project title mentions GraphRAG. | Useful for future KG framing, not the current main baseline. |
| PathGPT: Reframing Path Recommendation as a Natural Language Generation Task with Retrieval-Augmented Language Models | 2025, arXiv | LLM/RAG path generation from historical trajectories and natural-language constraints | Publicly available taxi trajectory datasets reported for Beijing, Chengdu, Harbin, Porto after map matching | Partial yes. Paper claims publicly available taxi trajectory datasets; exact processed data release/code should be verified. | Unknown. Papers With Code did not show a verified repo in this pass; third-party lists mention code but need verification. | Precision and Recall for generated path vs fastest/shortest ground truth; baseline models include CSSRNN and NeuroMLR variants | Partial | No with current data; possible future comparison if we move to natural-language path generation and use their datasets/metrics. | Valid comparison: prompt/RAG route generation framing. Could be relevant to our prompt/SBERT mode, but their task generates full paths, while ours ranks generated OSM candidates. | Interesting recent LLM baseline, but too different and not yet verified enough for main baseline. |
| Constraint-Aware Route Recommendation from Natural Language via Hierarchical LLM Agents / RouteLLM | 2025, arXiv | Natural-language constraint-aware route recommendation using hierarchical LLM agents | Not confirmed from abstract page; likely constructed route/POI benchmark or custom evaluation | Unknown | Unknown | Route quality and preference/constraint satisfaction over classical methods, from abstract | Partial | No with current pseudo-history data. It addresses natural-language route constraints, not trace-derived profile ranking. | Valid comparison: future prompt-based/LLM-agent extension, especially if GUI accepts natural-language preferences. | Good future-work comparison; not main baseline for current evaluation. |
| PathGen-LLM: A Large Language Model for Dynamic Path Generation in Complex Transportation Networks | 2025, Mathematics / MDPI | LLM path generation in transportation networks | Beijing taxi/subway and Porto path datasets; Beijing data appears custom/private; Porto likely public | Partial / unknown | Unknown | Next-token accuracy, Precision, Recall, F1, MAE/RMSE for travel time, inference speed | Partial | No with current OSM pseudo-history ranking. Possible if we adopt path-generation metrics and public Porto data. | Valid comparison: recent path-generation metrics and shortest-path vs learned path baselines. | Useful recent reference, but not main baseline unless we reframe as path generation. |

## Final Recommendation Table

| Paper | Best role | Dataset public? | Metrics match? | Direct comparison possible? | Recommendation |
|---|---|---|---|---|---|
| Personalized Route Recommendation Based on User Habits for Vehicle Navigation | Closest conceptual baseline for user-history route sorting | No, appears private/company data | Partial: mean_IR/AUC do not match current Hit@K/MRR/NDCG, but baseline structure is useful | No | Use as the primary conceptual baseline, not as a direct experimental baseline. Implement analogous baselines only after better labels/data. |
| NASR / Empowering A* Search Algorithms with Neural Networks for Personalized Route Recommendation | Top-tier route-recovery/search benchmark | Partial: Porto public; Beijing datasets unclear | Partial: Precision/Recall/F1/EDT can be adopted if we evaluate route recovery | Partial future comparison | Best candidate for a future direct technical benchmark if we convert evaluation to route recovery on public data. |
| Personalized route recommendation using big trajectory data | Historical personalized trajectory-routing reference | No / unknown | Weak: KL, F-ratio, runtime do not match current ranking metrics | No | Cite for early personalized trajectory-routing framing; not practical as main baseline. |
| RICK / Constructing Popular Routes from Uncertain Trajectories | Uncertain trajectory reconstruction baseline | Yes-ish: Microsoft page links data; verify current availability | Partial: NDTW/MD align more with reconstruction than ranking | No for ranking; partial for reconstruction | Use as reconstruction-related work and possible future map-matching/top-k route inference comparison. |
| Context Trails | Public dataset/code candidate for contextual route recommendation | Yes | Unknown/partial: recommender metrics likely differ | No for current OSM routing | Use as public contextual-route dataset reference; not direct baseline unless task is reframed to tourism trails. |
| Context-aware bicycle route recommendation 2024 | Recent context-aware personalization reference | Unknown | Unknown | Unknown | Investigate further only if bicycle/pedestrian route personalization becomes central. |
| Personalized/context-aware route planning for edge-assisted vehicles | Recent GNN+DRL context-aware routing reference | Unknown | Partial: satisfaction/travel time rather than Hit@K | No | Cite for recent context-aware route planning and generic-vs-personalized framing. |
| PathGPT / PathGen-LLM / RouteLLM | Recent LLM/prompt route-generation direction | Partial/unknown | Partial for prompt mode only | No with current data | Keep as future-work / prompt-based comparison, not current main baseline. |

## Current Baseline Strategy

Recommended near-term strategy:

1. **Do not claim one paper as directly beaten yet.**
2. Use **Personalized Route Recommendation Based on User Habits for Vehicle Navigation** as the closest conceptual baseline.
3. Use **NASR** as the strongest top-tier methodological benchmark, but only if we can run or emulate route-recovery metrics on public data.
4. Use **RICK** for trace reconstruction and uncertainty framing, not for profile-ranking comparison.
5. Keep our current experimental baselines:
   - random
   - shortest-distance
   - profile
   - prompt/SBERT when preference text exists
   - hybrid when both profile and prompt exist
6. Add route-overlap metrics if we want better alignment with NASR:
   - Precision
   - Recall
   - F1
   - Edit distance
7. Add reconstruction metrics if comparing to RICK:
   - NDTW or dynamic time warping distance
   - maximum route-to-trace distance
   - GPS-to-route median/mean distance
   - route-distance ratio

## Most Defensible Wording

Use:

> We compare against internal baselines under a route-candidate ranking setup and position the method against prior personalized route recommendation and uncertain-trajectory reconstruction work. Direct numerical comparison to prior systems is not yet valid because the closest personalized route-ranking papers use private navigation logs or different route-recovery datasets and metrics.

Avoid:

> We beat NASR / RICK / User Habits.

Current strongest claim:

> The corrected route-candidate evaluation is a prototype baseline study showing that the profile ranker can be compared fairly against random and shortest-distance baselines on the same generated OSM candidate set. Broader paper-to-paper comparison requires dataset and metric alignment.

## Source Notes

- User Habits paper: arXiv summary reports historical navigation data, route/user-profile features, DCR, mean_IR/AUC, and comparisons to minimum ETA, LightGBM, DCN-v2: https://arxiv.org/abs/2409.14047
- ResearchGate full-text preview reports private-car navigation-service logs and mean_IR/AUC details: https://www.researchgate.net/publication/384266404_Personalized_Route_Recommendation_Based_on_User_Habits_for_Vehicle_Navigation
- NASR KDD page and GitHub: https://www.bigscity.com/publications/empowering-a-search-algorithms-with-neural-networks-for-personalized-route-recommendation/ and https://github.com/bigscity/NASR
- NASR arXiv/html provides datasets, metrics, and task setting: https://arxiv.org/abs/1907.08489
- ICDE 2015 big trajectory paper metadata/PDF: https://vbn.aau.dk/en/publications/personalized-route-recommendation-using-big-trajectory-data/ and https://spacetimelab.cn/publication/personalized-route-recommendation-using-big-trajectory-data/personalized-route-recommendation-using-big-trajectory-data.pdf
- RICK / KDD 2012 Microsoft page and PDF: https://www.microsoft.com/en-us/research/publication/constructing-popular-routes-from-uncertain-trajectories/ and https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/KDD12-PopularRoutes.pdf
- Context Trails UAM page/PDF: https://portalcientifico.uam.es/en/ipublic/item/10559507 and https://abellogin.github.io/2025/resource.pdf
- Recent contextual/LLM route papers checked: Context-aware bicycle route recommendation DOI page, Personalized/context-aware edge-assisted route planning PDF, PathGPT arXiv, RouteLLM arXiv, PathGen-LLM MDPI.
