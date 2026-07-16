from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from autocall_check import ObservationRow, autocall_scan
from basket_pricing import BasketConstituent, basket_returns
from lifecycle_coupon_check import CouponTerms, Underlier, coupon_schedule, worst_performance


D1 = date(2026, 1, 2)
D2 = date(2026, 2, 2)
UNDERLIERS = [Underlier("A", 100.0), Underlier("B", 100.0)]


def closes(rows: list[tuple[str, date, float | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={"security": pl.String, "date": pl.Date, "PX_LAST": pl.Float64},
        orient="row",
    )


def test_worst_performance_emits_fully_missing_observation() -> None:
    result = worst_performance(
        closes([("A", D1, 90.0), ("B", D1, 80.0)]),
        UNDERLIERS,
        [D1, D2],
    )

    assert result.to_dicts() == [
        {"date": D1, "worst_perf": 0.8, "worst_security": "B"},
        {"date": D2, "worst_perf": None, "worst_security": None},
    ]


def test_worst_performance_rejects_duplicate_security_date() -> None:
    with pytest.raises(ValueError, match="duplicate close rows"):
        worst_performance(
            closes([("A", D1, 90.0), ("A", D1, 95.0)]),
            UNDERLIERS,
            [D1],
        )


def test_memory_coupon_propagates_unknown_state() -> None:
    worst = pl.DataFrame({
        "date": [D1, D2],
        "worst_perf": [None, 1.10],
        "worst_security": [None, "A"],
    })

    result = coupon_schedule(worst, CouponTerms(0.70, 0.01, memory=True))

    assert result["status"].to_list() == [
        "UNDETERMINED (missing level — check postponement)",
        "UNDETERMINED (prior memory-coupon observation unresolved)",
    ]
    assert result["amount"].to_list() == [None, None]


def test_nonmemory_coupon_can_resume_after_unknown_period() -> None:
    worst = pl.DataFrame({
        "date": [D1, D2],
        "worst_perf": [None, 1.10],
        "worst_security": [None, "A"],
    })

    result = coupon_schedule(worst, CouponTerms(0.70, 0.01, memory=False))

    assert result["status"].to_list()[-1] == "PAID"
    assert result["amount"].to_list()[-1] == pytest.approx(0.01)


def test_coupon_schedule_rejects_duplicate_observations() -> None:
    worst = pl.DataFrame({
        "date": [D1, D1],
        "worst_perf": [0.8, 0.9],
        "worst_security": ["A", "A"],
    })

    with pytest.raises(ValueError, match="dates must be unique"):
        coupon_schedule(worst, CouponTerms(0.70, 0.01, memory=True))


def test_autocall_does_not_claim_later_call_after_unknown_call_date() -> None:
    result = autocall_scan(
        closes([
            ("A", D1, None),
            ("B", D1, None),
            ("A", D2, 110.0),
            ("B", D2, 110.0),
        ]),
        UNDERLIERS,
        [ObservationRow(D1, 1.0, None), ObservationRow(D2, 1.0, None)],
        call_type=None,
    )

    assert result["status"].to_list() == [
        "UNDETERMINED (missing level — check postponement)",
        "UNDETERMINED (prior call observation unresolved)",
    ]


def test_autocall_rejects_empty_schedule_cleanly() -> None:
    with pytest.raises(ValueError, match="schedule must be non-empty"):
        autocall_scan(closes([]), UNDERLIERS, [], call_type="automatic")


def test_lifecycle_terms_reject_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        worst_performance(closes([]), [Underlier("A", float("nan"))], [])

    with pytest.raises(ValueError, match="finite and non-negative"):
        coupon_schedule(
            pl.DataFrame({
                "date": [D1],
                "worst_perf": [1.0],
                "worst_security": ["A"],
            }),
            CouponTerms(float("nan"), 0.01, memory=False),
        )

    with pytest.raises(ValueError, match="autocall levels must be finite"):
        autocall_scan(
            closes([]),
            UNDERLIERS,
            [ObservationRow(D1, float("nan"), None)],
            call_type="automatic",
        )


def test_basket_rejects_duplicate_rows_and_reports_actual_weight_sum() -> None:
    basket = [BasketConstituent("A", 100.0, 0.5), BasketConstituent("B", 100.0, 0.5)]
    with pytest.raises(ValueError, match="duplicate close rows"):
        basket_returns(closes([("A", D1, 90.0), ("A", D1, 95.0)]), basket)

    with pytest.raises(ValueError, match="sum to 0.8000"):
        basket_returns(
            closes([("A", D1, 90.0)]),
            [BasketConstituent("A", 100.0, 0.8)],
        )
