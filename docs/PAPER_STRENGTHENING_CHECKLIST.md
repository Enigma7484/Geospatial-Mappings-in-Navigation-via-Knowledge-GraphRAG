# Paper Strengthening Checklist

- [x] Main claim is reranking, not full route generation.
- [x] Does not claim to beat NASR.
- [x] Porto is primary public benchmark.
- [x] Toronto OSM trace probe is exploratory.
- [x] Same-data comparison issue is explained.
- [x] Metrics are tied to related work.
- [x] Direct external comparison marked pending.
- [x] Oracles labeled diagnostic.
- [x] Prompt/SBERT labeled synthetic/ablation where applicable.
- [x] LLM/GPT role clarified.
- [x] Limitations are explicit.
- [x] Reproducibility commands are correct.
- [x] No fabricated results.

## Remaining Work Before a Stronger Submission

- [ ] Complete a larger Porto run if runtime can be reduced or moved to a longer execution environment.
- [ ] Rerun the updated Porto evaluator to populate the no-temporal trajectory-derived vehicle profile ablation row.
- [ ] Reproduce NASR or another external route-search baseline under matched Porto preprocessing and splits.
- [ ] Improve map matching and candidate generation so path F1/NDTW improve alongside ranking metrics.
