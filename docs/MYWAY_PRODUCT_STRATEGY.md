# MyWay Product Strategy

## Product Position

**MyWay is a preference-aware route reranking engine.** It takes a candidate set from an OSM or commercial routing stack and changes the order using explicit preferences, contextual signals, or learned movement patterns. It is currently an explainable research prototype, not a production replacement for Google Maps, Mapbox, or a fleet optimizer.

That narrower position is commercially useful: a customer can add MyWay after its existing route generator and test whether better-ranked alternatives improve route acceptance, reduce deviations, or reduce manual intervention.

## What The Evidence Supports

The 250-query Porto benchmark gives an initial signal, not a customer ROI claim:

| Result | MyWay vehicle profile | Shortest distance | Interpretation |
|---|---:|---:|---|
| Hit@1 | 21.2% | 8.8% | More observed-like candidates ranked first. |
| Hit@3 | 44.0% | 28.0% | A 16 percentage-point improvement in top-three recovery. |
| MRR | 0.406 | 0.273 | The observed-like candidate appears earlier on average. |
| Path F1 | 0.464 | 0.517 | Shortest distance remains better on this geometry metric. |
| Mean feature distance | 1.918 | 1.900 | No advantage on aggregate feature distance in this run. |

Source: `data/porto_candidate_baseline_comparison_250.json`.

The commercial hypothesis is that higher preference alignment will improve user behavior or operations. The benchmark does **not** yet prove saved time, fuel, safety outcomes, retention, or willingness to pay. Those must be measured in a customer pilot.

## Whitepaper-To-Industry Map

| Whitepaper capability | Industry use case | Buyer | Monthly outcome to measure | Readiness |
|---|---|---|---|---|
| Vehicle-history profile reranking | Driver-preferred route alternatives for local fleets | Fleet operations, dispatch software | Route acceptance, deviations, dispatcher interventions, minutes and distance | Best first pilot; Porto evidence is directionally relevant. |
| Prompt and hybrid reranking | User-stated constraints such as quieter, greener, or simpler routes | Mobility apps, campus apps | Route selection rate, repeat use, preference satisfaction | Demo-ready; real preference-text evaluation is still needed. |
| Interpretable OSM features | Explainable policy routes for field work or municipal mobility | Municipalities, campus operations, insurers | Policy compliance, support tickets, reason-code acceptance | Feature coverage must be audited city by city. |
| Walking-route feature ranking | Tourism and destination walking experiences | Tourism boards, venue and travel apps | Completed itineraries, dwell time, route ratings | Good experience pilot; weak direct cost ROI. |
| Pseudo-history profiles | Cold-start research where clean user logs are unavailable | Research labs, civic innovation teams | Ranking lift over shortest route | Research use only until identity and consent are stronger. |
| Accessibility-oriented attributes | Routes avoiding barriers or difficult segments | Universities, healthcare campuses | Successful trips, assistance requests, reported barriers | Future use case; requires incline, surface, curb, elevator, and verified accessibility data before safety claims. |

## Recommended Beachhead

Start with a **25-vehicle local fleet or campus mobility operator** that already generates candidate routes. Run MyWay in shadow mode for two weeks, then expose alternatives to a small opt-in cohort for four weeks.

Do not start by promising faster routes. The better first promise is:

> MyWay learns which reasonable route alternatives people are more likely to accept, and explains why they were ranked.

## Monthly Value Engineering Model

The model is intentionally auditable:

```text
monthly trips = active units * trips per unit
time value = trips * minutes saved per trip / 60 * value per hour
distance value = trips * miles saved per trip * cost per mile
intervention value = interventions * reduction rate * cost per intervention
raw value = time value + distance value + intervention value + retained revenue
risk-adjusted value = raw value * evidence confidence
customer ROI = (risk-adjusted value - monthly investment) / monthly investment
```

Run it with:

```bash
python scripts/calculate_customer_roi.py --scenario small_fleet
python scripts/calculate_customer_roi.py --scenario campus --json
```

Every default is illustrative. Replace it with customer measurements. The `evidence_confidence` discount prevents an early pilot estimate from being priced like a proven result.

### Illustrative Monthly Cases

| Scenario | Risk-adjusted value | Proposed monthly investment | Net monthly value | ROI | Decision |
|---|---:|---:|---:|---:|---|
| Individual, time-only | $4.17 | $4.99 | -$0.82 | -16.5% | Consumer value must come from measured comfort or preference satisfaction, not invented time savings. |
| 25-vehicle fleet | $792.62 | $199.00 | $593.62 | 298.3% | Worth a controlled pilot if route acceptance and intervention data are available. |
| Campus, 500 active users | $343.47 | $99.00 | $244.47 | 246.9% | Plausible if assistance/support reductions are measurable. |
| 200-vehicle fleet | $7,666.45 | $1,999.00 | $5,667.45 | 283.5% | Price should rise only after measured proof and production hardening. |

The 2026 US business mileage rate is **$0.725 per mile** and can be used as a transparent proxy when a customer has no better fully loaded vehicle-cost figure. It is not a promise that MyWay reduces mileage. The US Department of Transportation publishes formal travel-time valuation guidance; customer wage, burden, and trip-purpose data are preferable for an actual business case. Sources: [IRS 2026 mileage rate](https://www.irs.gov/newsroom/irs-sets-2026-business-standard-mileage-rate-at-725-cents-per-mile-up-25-cents), [USDOT 2025 benefit-cost guidance](https://www.transportation.gov/sites/dot.gov/files/2024-11/Benefit%20Cost%20Analysis%20Guidance%202025%20Update%20%28Final%29.pdf).

## Proposed Pricing

These are validation prices, not a promise of current production capacity.

| Offer | Price | Included | Best for |
|---|---:|---|---|
| Research Demo | $0 | Public demo, shared free hosting, no SLA | Reviewers and research collaborators |
| MyWay Individual Beta | $4.99/month | Personal preference profile and route comparison | Willingness-to-pay testing only |
| Design Partner | $99/month | Up to 25 active users and 5,000 reranks, shared pilot support | Small controlled pilots |
| Operations | $299/month | Up to 100 active users and 25,000 reranks, outcome dashboard | Small fleets and campuses |
| Scale Pilot | $1,499/month | Up to 500 active users/vehicles and 150,000 reranks, private deployment support | Larger validation programs |
| Enterprise Outcome Contract | $49 base + 10% of verified value | Agreed baseline, measurement plan, cap, and audit rules | Buyers who prefer shared-risk pricing |

Customers should be able to choose:

1. **Predictable tier:** fixed monthly price and usage cap.
2. **Usage model:** $49 platform fee plus $4 per 1,000 reranks after an agreed allowance.
3. **Value model:** $49 base plus 10% of independently verified, risk-adjusted monthly value, capped at the equivalent fixed tier. Move toward 15-20% only after repeated production evidence.

During a validation pilot, let the customer choose the fixed tier or value model and use the lower resulting price. `monthly_implementation_cost` in the calculator represents the customer's internal recurring cost and is included in customer ROI, but it is not vendor revenue or value capture.

Commercial routing is typically metered per request. As of June 2026, Google lists a 10,000-event free cap and then $5 per 1,000 Compute Routes Essentials events in the first paid tier; Mapbox lists 100,000 free Directions requests and then $2 per 1,000 in its first paid tier. MyWay should be priced as an added personalization and measurement layer, not as if it owns the underlying global map and traffic stack. Sources: [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing), [Mapbox pricing](https://www.mapbox.com/pricing).

## Pilot Measurement Contract

Capture a baseline and treatment period for the same cohort. At minimum log:

- Candidate routes shown and their source.
- MyWay ranking and explanation.
- Route selected, route started, completion, and deviations.
- Time, distance, and manual interventions.
- User/vehicle pseudonymous ID, travel mode, and request context.
- Explicit route rating and reason for rejection.
- Model version, map-data date, latency, and failures.

Primary pilot KPIs:

- Route acceptance lift.
- Reduction in route abandonment/deviation.
- Dispatcher or support interventions avoided.
- Preference satisfaction score.
- P95 response latency and successful-request rate.

Do not collect precise movement history without purpose limitation, retention rules, consent where required, and an access/deletion process.

## Data Priorities

The highest-value data is not more raw GPS alone. It is **candidate-set plus choice plus outcome**:

1. Clean origin/destination queries with every candidate offered.
2. The route actually selected and followed.
3. Stable pseudonymous user or vehicle histories.
4. Stated preference text and post-trip satisfaction.
5. Context such as travel mode, time, weather, and traffic.
6. Negative labels: rejected routes and why they were rejected.
7. Accessibility and safety attributes from authoritative local sources before making related claims.

This dataset directly connects algorithm lift to buyer value and gives the paper a stronger real-world evaluation.
