from __future__ import annotations

import pytest

from metric_oracle import MetricError, liquidity_metrics, returns_metrics, risk_metrics


def prices(values: list[float], dividends: list[float] | None = None) -> list[dict[str, object]]:
    dates = ["2025-01-02", "2025-07-02", "2026-01-02", "2026-07-02"]
    dividends = dividends or [0.0] * len(values)
    return [
        {"date": date, "close": close, "dividend": dividend, "volume": 1000.0}
        for date, close, dividend in zip(dates, values, dividends)
    ]


def test_reinvested_total_return_and_exact_real_return() -> None:
    result = returns_metrics(
        prices([100.0, 100.0, 110.0, 110.0], [0.0, 10.0, 0.0, 0.0]),
        inflation=0.03,
    )

    assert result["price_return"] == pytest.approx(0.10)
    assert result["total_return"] == pytest.approx(0.21)
    assert result["dividend_contribution"] == pytest.approx(0.11)
    assert result["real_cagr"] == pytest.approx(
        (1.0 + result["cagr"]) / 1.03 - 1.0
    )


def test_identical_benchmark_has_beta_one_and_zero_tracking_error() -> None:
    series = prices([100.0, 102.0, 99.0, 104.0])
    result = risk_metrics(series, benchmark_rows=series, risk_free=0.02, periods_per_year=252)

    assert result["relative"]["beta"] == pytest.approx(1.0)
    assert result["relative"]["tracking_error"] == pytest.approx(0.0)
    assert result["relative"]["information_ratio"] is None


def test_benchmark_alignment_requires_identical_return_intervals() -> None:
    security = [
        {"date": "2026-01-02", "close": 100.0},
        {"date": "2026-01-03", "close": 101.0},
        {"date": "2026-01-05", "close": 102.0},
        {"date": "2026-01-06", "close": 103.0},
    ]
    benchmark = [
        {"date": "2026-01-02", "close": 100.0},
        {"date": "2026-01-04", "close": 101.0},
        {"date": "2026-01-05", "close": 102.0},
        {"date": "2026-01-06", "close": 103.0},
    ]

    with pytest.raises(MetricError, match="common return intervals"):
        risk_metrics(security, benchmark_rows=benchmark)


def test_var_is_positive_loss_and_flat_series_has_undefined_sharpe() -> None:
    volatile = risk_metrics(prices([100.0, 90.0, 95.0, 80.0]))
    assert volatile["var"]["sign"] == "positive_loss"
    assert volatile["var"]["historical"] >= 0

    flat = risk_metrics(prices([100.0, 100.0, 100.0, 100.0]))
    assert flat["annualized_volatility"] == 0.0
    assert flat["sharpe"] is None


def test_liquidity_rounds_up_and_keeps_partial_final_day() -> None:
    result = liquidity_metrics(250_000, 1_000_000, 0.10)

    assert result["days_to_liquidate"] == 3
    assert result["timeline"][-1]["executed_shares"] == pytest.approx(50_000)
    assert result["timeline"][-1]["remaining_shares"] == 0.0


def test_duplicate_dates_and_ambiguous_participation_fail() -> None:
    duplicate = [
        {"date": "2026-01-02", "close": 100.0},
        {"date": "2026-01-02", "close": 101.0},
    ]
    with pytest.raises(MetricError, match="duplicate date"):
        returns_metrics(duplicate)

    with pytest.raises(MetricError, match="decimal between 0 and 1"):
        liquidity_metrics(1000, 10000, 10)
