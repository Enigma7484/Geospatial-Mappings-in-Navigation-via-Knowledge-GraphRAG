#!/usr/bin/env python3
"""Calculate a transparent monthly value case for a MyWay customer."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class Scenario:
    active_units: float
    trips_per_unit: float
    minutes_saved_per_trip: float
    value_per_hour: float
    miles_saved_per_trip: float
    cost_per_mile: float
    monthly_interventions: float
    intervention_reduction_rate: float
    cost_per_intervention: float
    monthly_revenue_retained: float
    evidence_confidence: float
    monthly_price: float
    monthly_implementation_cost: float
    one_time_setup_cost: float


SCENARIOS = {
    "individual": Scenario(
        active_units=1,
        trips_per_unit=40,
        minutes_saved_per_trip=0.5,
        value_per_hour=25,
        miles_saved_per_trip=0,
        cost_per_mile=0.725,
        monthly_interventions=0,
        intervention_reduction_rate=0,
        cost_per_intervention=0,
        monthly_revenue_retained=0,
        evidence_confidence=0.5,
        monthly_price=4.99,
        monthly_implementation_cost=0,
        one_time_setup_cost=0,
    ),
    "small_fleet": Scenario(
        active_units=25,
        trips_per_unit=120,
        minutes_saved_per_trip=1.0,
        value_per_hour=28,
        miles_saved_per_trip=0.03,
        cost_per_mile=0.725,
        monthly_interventions=40,
        intervention_reduction_rate=0.20,
        cost_per_intervention=15,
        monthly_revenue_retained=0,
        evidence_confidence=0.50,
        monthly_price=99,
        monthly_implementation_cost=100,
        one_time_setup_cost=1500,
    ),
    "campus": Scenario(
        active_units=500,
        trips_per_unit=8,
        minutes_saved_per_trip=0.5,
        value_per_hour=20,
        miles_saved_per_trip=0,
        cost_per_mile=0.725,
        monthly_interventions=80,
        intervention_reduction_rate=0.20,
        cost_per_intervention=12,
        monthly_revenue_retained=0,
        evidence_confidence=0.40,
        monthly_price=49,
        monthly_implementation_cost=50,
        one_time_setup_cost=1000,
    ),
    "enterprise_fleet": Scenario(
        active_units=200,
        trips_per_unit=160,
        minutes_saved_per_trip=0.75,
        value_per_hour=32,
        miles_saved_per_trip=0.02,
        cost_per_mile=0.725,
        monthly_interventions=300,
        intervention_reduction_rate=0.15,
        cost_per_intervention=15,
        monthly_revenue_retained=0,
        evidence_confidence=0.55,
        monthly_price=1499,
        monthly_implementation_cost=500,
        one_time_setup_cost=7500,
    ),
}


def calculate(scenario: Scenario) -> dict[str, float | None]:
    trips = scenario.active_units * scenario.trips_per_unit
    time_value = (
        trips * scenario.minutes_saved_per_trip / 60 * scenario.value_per_hour
    )
    distance_value = trips * scenario.miles_saved_per_trip * scenario.cost_per_mile
    intervention_value = (
        scenario.monthly_interventions
        * scenario.intervention_reduction_rate
        * scenario.cost_per_intervention
    )
    raw_value = (
        time_value
        + distance_value
        + intervention_value
        + scenario.monthly_revenue_retained
    )
    risk_adjusted_value = raw_value * scenario.evidence_confidence
    monthly_investment = (
        scenario.monthly_price + scenario.monthly_implementation_cost
    )
    net_value = risk_adjusted_value - monthly_investment
    roi_pct = (
        net_value / monthly_investment * 100 if monthly_investment > 0 else None
    )
    value_capture_pct = (
        scenario.monthly_price / risk_adjusted_value * 100
        if risk_adjusted_value > 0
        else None
    )
    monthly_cash_after_recurring = risk_adjusted_value - monthly_investment
    payback_months = (
        scenario.one_time_setup_cost / monthly_cash_after_recurring
        if scenario.one_time_setup_cost > 0 and monthly_cash_after_recurring > 0
        else 0.0 if scenario.one_time_setup_cost == 0 else None
    )

    return {
        "monthly_trips": trips,
        "time_value": time_value,
        "distance_value": distance_value,
        "intervention_value": intervention_value,
        "revenue_retained": scenario.monthly_revenue_retained,
        "raw_monthly_value": raw_value,
        "risk_adjusted_monthly_value": risk_adjusted_value,
        "monthly_investment": monthly_investment,
        "net_monthly_value": net_value,
        "customer_roi_pct": roi_pct,
        "vendor_value_capture_pct": value_capture_pct,
        "setup_payback_months": payback_months,
        "price_at_10pct_value": risk_adjusted_value * 0.10,
        "price_at_15pct_value": risk_adjusted_value * 0.15,
        "price_at_20pct_value": risk_adjusted_value * 0.20,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate monthly MyWay customer value. Defaults are illustrative, not "
            "measured product claims; replace them with pilot data."
        )
    )
    parser.add_argument("--scenario", choices=SCENARIOS, default="small_fleet")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    for field_name in Scenario.__dataclass_fields__:
        parser.add_argument(
            f"--{field_name.replace('_', '-')}",
            dest=field_name,
            type=float,
            default=None,
        )
    return parser


def _money(value: float | None) -> str:
    return "n/a" if value is None else f"${value:,.2f}"


def main() -> None:
    args = _parser().parse_args()
    scenario = SCENARIOS[args.scenario]
    overrides = {
        name: getattr(args, name)
        for name in Scenario.__dataclass_fields__
        if getattr(args, name) is not None
    }
    scenario = replace(scenario, **overrides)

    if not 0 <= scenario.evidence_confidence <= 1:
        raise SystemExit("evidence-confidence must be between 0 and 1")
    if not 0 <= scenario.intervention_reduction_rate <= 1:
        raise SystemExit("intervention-reduction-rate must be between 0 and 1")
    if any(value < 0 for value in asdict(scenario).values()):
        raise SystemExit("scenario values cannot be negative")

    results = calculate(scenario)
    if args.json:
        print(
            json.dumps(
                {"scenario": args.scenario, "inputs": asdict(scenario), "results": results},
                indent=2,
            )
        )
        return

    print(f"MyWay monthly value case: {args.scenario}")
    print("Illustrative until inputs are replaced with customer pilot measurements.\n")
    print(f"Monthly trips:                 {results['monthly_trips']:,.0f}")
    print(f"Time value:                    {_money(results['time_value'])}")
    print(f"Distance value:                {_money(results['distance_value'])}")
    print(f"Intervention value:            {_money(results['intervention_value'])}")
    print(f"Risk-adjusted monthly value:   {_money(results['risk_adjusted_monthly_value'])}")
    print(f"Monthly investment:            {_money(results['monthly_investment'])}")
    print(f"Net monthly value:             {_money(results['net_monthly_value'])}")
    roi = results["customer_roi_pct"]
    print(f"Customer ROI:                  {'n/a' if roi is None else f'{roi:,.1f}%'}")
    payback = results["setup_payback_months"]
    print(f"Setup payback:                 {'n/a' if payback is None else f'{payback:,.1f} months'}")
    print(
        "Value-based monthly range:    "
        f"{_money(results['price_at_10pct_value'])} - "
        f"{_money(results['price_at_20pct_value'])}"
    )


if __name__ == "__main__":
    main()
