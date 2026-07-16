from __future__ import annotations

import math

import pytest

from payoff_engine import (
    SpecError,
    aggregate_performance,
    evaluate_path,
    evaluate_terminal_performance,
    scenario_grid,
    validate_spec,
)


def spec(*, downside: str = "barrier") -> dict[str, object]:
    downside_terms: dict[str, object] = {
        "kind": downside,
        "barrier": 0.70 if downside in {"barrier", "absolute_return"} else None,
        "buffer": 0.20 if downside == "buffer" else None,
        "gearing": 1.0,
    }
    return {
        "schema_version": 1,
        "note_id": "test-note",
        "product_type": "phoenix_autocall",
        "notional": 1000.0,
        "underlier_structure": "worst_of",
        "underliers": [
            {"id": "A", "initial_level": 100.0, "weight": None},
            {"id": "B", "initial_level": 200.0, "weight": None},
        ],
        "terminal": {
            "upside": {
                "kind": "participation",
                "participation_rate": 1.0,
                "cap": 0.25,
                "digital_trigger": None,
                "digital_return": None,
            },
            "downside": downside_terms,
        },
        "income": {"coupon_barrier": 0.70, "coupon_per_period": 0.02, "memory": True},
        "call": {"type": "automatic"},
        "schedule": [
            {"date": "2027-01-15", "coupon_barrier": 0.70, "coupon_amount": 0.02,
             "call_trigger": 1.0, "call_premium": 0.0},
            {"date": "2027-02-15", "coupon_barrier": 0.70, "coupon_amount": 0.02,
             "call_trigger": 0.95, "call_premium": 0.01},
        ],
    }


def test_worst_of_aggregation_and_barrier_boundary() -> None:
    terms = spec()
    assert aggregate_performance(terms, {"A": 90.0, "B": 160.0}) == pytest.approx(0.8)

    at_barrier = evaluate_terminal_performance(terms, 0.70)
    below_barrier = evaluate_terminal_performance(terms, math.nextafter(0.70, 0.0))
    assert at_barrier["redemption"] == pytest.approx(1000.0)
    assert below_barrier["redemption"] == pytest.approx(700.0)


def test_cap_and_buffer_mechanics() -> None:
    capped = evaluate_terminal_performance(spec(), 1.50)
    assert capped["note_return"] == pytest.approx(0.25)

    buffered_terms = spec(downside="buffer")
    assert evaluate_terminal_performance(buffered_terms, 0.80)["redemption"] == pytest.approx(1000.0)
    assert evaluate_terminal_performance(buffered_terms, 0.70)["redemption"] == pytest.approx(900.0)


def test_memory_and_autocall_path_stops_when_called() -> None:
    result = evaluate_path(spec(), [
        {"date": "2027-01-15", "levels": {"A": 60.0, "B": 160.0}},
        {"date": "2027-02-15", "levels": {"A": 100.0, "B": 200.0}},
    ])

    assert [row["coupon_status"] for row in result] == ["MISSED", "PAID"]
    assert result[1]["coupon_payment"] == pytest.approx(40.0)
    assert result[1]["call_status"] == "CALLED"
    assert result[1]["call_redemption"] == pytest.approx(1010.0)


def test_unresolved_call_and_memory_states_propagate() -> None:
    result = evaluate_path(spec(), [
        {"date": "2027-02-15", "levels": {"A": 100.0, "B": 200.0}},
    ])

    assert result[0]["call_status"] == "UNDETERMINED_MISSING_LEVEL"
    assert result[1]["call_status"] == "UNDETERMINED_PRIOR_CALL_STATE"
    assert result[1]["coupon_status"] == "UNDETERMINED_PRIOR_MEMORY_STATE"


def test_official_determination_repairs_later_path_state() -> None:
    result = evaluate_path(
        spec(),
        [{"date": "2027-02-15", "levels": {"A": 100.0, "B": 200.0}}],
        {
            "2027-01-15": {
                "coupon_status": "MISSED",
                "coupon_payment": 0.0,
                "missed_count": 1,
                "call_status": "NOT_CALLED",
            }
        },
    )

    assert result[0]["coupon_status"] == "MISSED"
    assert result[0]["call_status"] == "NOT_CALLED"
    assert result[1]["coupon_status"] == "PAID"
    assert result[1]["coupon_payment"] == pytest.approx(40.0)
    assert result[1]["call_status"] == "CALLED"


def test_invalid_weights_nonfinite_values_and_huge_grid_fail() -> None:
    terms = spec()
    terms["underlier_structure"] = "basket_defined_weight"
    terms["underliers"][0]["weight"] = 0.4  # type: ignore[index]
    terms["underliers"][1]["weight"] = 0.4  # type: ignore[index]
    with pytest.raises(SpecError, match="weights sum"):
        validate_spec(terms)

    with pytest.raises(SpecError, match="finite"):
        evaluate_terminal_performance(spec(), float("nan"))

    with pytest.raises(SpecError, match="100,000"):
        scenario_grid(spec(), 0.0, 1.0, 0.000001)
