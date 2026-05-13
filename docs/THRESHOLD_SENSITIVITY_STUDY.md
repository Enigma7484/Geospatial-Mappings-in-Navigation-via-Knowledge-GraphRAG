# Threshold Sensitivity Study

This study checks whether the current OSM-derived pseudo-history pipeline depends on one hand-picked segmentation/filtering threshold setting. It does **not** establish a direct comparison against external route-recommendation systems. Its role is to make the data-quality story more defensible before moving to a same-data public benchmark.

## Script

```powershell
python scripts\evaluate_threshold_sensitivity.py --max-configs 5
```

Outputs:

- `data/threshold_sensitivity.json`
- `data/threshold_sensitivity.csv`

## Threshold Configurations

| Config | Max time gap min | Split max jump m | Min distance km | Speed range km/h | Filter max jump m |
|---|---:|---:|---:|---:|---:|
| current | 10 | 500 | 0.2 | 1-80 | 500 |
| stricter_gap | 5 | 500 | 0.2 | 1-80 | 500 |
| stricter_jump | 10 | 250 | 0.2 | 1-80 | 250 |
| stricter_distance | 10 | 500 | 0.5 | 1-80 | 500 |
| lower_speed_ceiling | 10 | 500 | 0.2 | 1-25 | 500 |

## Results

| Config | Pseudo-segments | Useful segments | Map-matched segments | Map-match success rate | Median GPS-to-route median m | Median route-distance ratio | Strict usable | Exploratory usable |
|---|---:|---:|---:|---:|---:|---:|---|---|
| current | 11 | 11 | 11 | 1.000 | 6.993 | 2.372 | false | true |
| stricter_gap | 12 | 12 | 12 | 1.000 | 6.720 | 2.360 | false | true |
| stricter_jump | 11 | 11 | 11 | 1.000 | 6.993 | 2.372 | false | true |
| stricter_distance | 11 | 10 | 10 | 1.000 | 7.407 | 2.360 | false | true |
| lower_speed_ceiling | 11 | 9 | 9 | 1.000 | 6.317 | 2.347 | false | true |

## Interpretation

The result is stable and honest:

- All tested configurations remain exploratory-usable.
- All tested configurations fail strict usability because median route-distance ratio stays above the strict ceiling of `2.0`.
- GPS-to-route distance remains low across configurations, between about `6.3 m` and `7.4 m`.
- The main failure mode is not nearest-path distance; it is route overbuilding from approximate nearest-node plus shortest-path stitching.

This supports the claim that the current OSM public trace pipeline is useful for exploratory pseudo-history experiments, but not yet strong enough for a final route-fidelity claim.

## Paper Use

Use this study to show:

> We tested segmentation and filtering sensitivity rather than relying on a single chosen threshold. Across five threshold settings, map matching remains successful and GPS-to-route distance remains low, but strict usability fails consistently due to route-distance ratio. We therefore treat OSM public GPS traces as exploratory pseudo-history signals and separate reconstruction quality from ranking quality.

Do not use it to claim:

> The OSM public GPS traces are clean user histories.

## Next Improvements

The next technical target is reducing route-distance ratio:

1. Split long or high-ratio segments after map matching.
2. Simplify repeated loops or backtracking in reconstructed route node sequences.
3. Try a proper HMM/map-matching package or OSRM/Valhalla map matching.
4. Report route-overlap metrics against public trajectory datasets where true paths or accepted map-matched paths are available.

