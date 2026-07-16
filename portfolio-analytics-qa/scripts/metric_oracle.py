#!/usr/bin/env python3
"""Independent standard-library oracle for common portfolio analytics.

Input series are JSON arrays of {date, close, dividend?, volume?}. All returns
and rates are decimals. VaR is reported as a positive loss.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import date
from pathlib import Path
from statistics import NormalDist
from typing import Any, Mapping, Sequence


class MetricError(ValueError):
    """Raised when metric inputs violate the oracle contract."""


def _number(value: object, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetricError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise MetricError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise MetricError(f"{name} must be >= {minimum}")
    return result


def normalize_series(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    if len(rows) < 2:
        raise MetricError("series requires at least two observations")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise MetricError(f"rows[{index}] must be an object")
        raw_date = str(row.get("date") or "")
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise MetricError(f"rows[{index}].date must be ISO YYYY-MM-DD") from exc
        key = parsed_date.isoformat()
        if key in seen:
            raise MetricError(f"duplicate date {key}")
        seen.add(key)
        normalized.append({
            "date": key,
            "close": _number(row.get("close"), f"rows[{index}].close", minimum=0.0000001),
            "dividend": _number(row.get("dividend", 0.0), f"rows[{index}].dividend"),
            "volume": _number(row.get("volume", 0.0), f"rows[{index}].volume", minimum=0.0),
        })
    if [row["date"] for row in normalized] != sorted(row["date"] for row in normalized):
        raise MetricError("series dates must be sorted ascending")
    return normalized


def build_indices(rows: Sequence[Mapping[str, object]]) -> list[dict[str, float | str]]:
    data = normalize_series(rows)
    start_close = float(data[0]["close"])
    wealth = 100.0
    result: list[dict[str, float | str]] = [{
        "date": str(data[0]["date"]),
        "price_index": 100.0,
        "total_return_index": 100.0,
    }]
    previous_close = start_close
    for row in data[1:]:
        close = float(row["close"])
        dividend = float(row["dividend"])
        gross_return = (close + dividend) / previous_close
        if gross_return <= 0:
            raise MetricError(f"non-positive gross return on {row['date']}")
        wealth *= gross_return
        result.append({
            "date": str(row["date"]),
            "price_index": 100.0 * close / start_close,
            "total_return_index": wealth,
        })
        previous_close = close
    return result


def _returns(
    index: Sequence[Mapping[str, float | str]],
    field: str,
) -> list[tuple[tuple[str, str], float]]:
    result: list[tuple[tuple[str, str], float]] = []
    for previous, current in zip(index, index[1:]):
        interval = (str(previous["date"]), str(current["date"]))
        result.append((interval, float(current[field]) / float(previous[field]) - 1.0))
    return result


def _elapsed_years(start: str, end: str) -> float:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days / 365.25


def _cagr(start_value: float, end_value: float, years: float) -> float | None:
    if years <= 0 or start_value <= 0 or end_value <= 0:
        return None
    return (end_value / start_value) ** (1.0 / years) - 1.0


def _max_drawdown(values: Sequence[float]) -> float:
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def returns_metrics(rows: Sequence[Mapping[str, object]], inflation: float = 0.0) -> dict[str, object]:
    inflation = _number(inflation, "inflation", minimum=-0.999999)
    index = build_indices(rows)
    years = _elapsed_years(str(index[0]["date"]), str(index[-1]["date"]))
    price_return = float(index[-1]["price_index"]) / 100.0 - 1.0
    total_return = float(index[-1]["total_return_index"]) / 100.0 - 1.0
    cagr = _cagr(100.0, float(index[-1]["total_return_index"]), years)
    cumulative_inflation = (1.0 + inflation) ** years - 1.0 if years > 0 else 0.0
    real_total_return = (1.0 + total_return) / (1.0 + cumulative_inflation) - 1.0
    real_cagr = None if cagr is None else (1.0 + cagr) / (1.0 + inflation) - 1.0
    return {
        "units": "decimal",
        "actual_start": index[0]["date"],
        "actual_end": index[-1]["date"],
        "elapsed_years": years,
        "price_return": price_return,
        "total_return": total_return,
        "dividend_contribution": total_return - price_return,
        "cagr": cagr,
        "inflation_annual": inflation,
        "real_total_return": real_total_return,
        "real_cagr": real_cagr,
        "max_drawdown_total_return": _max_drawdown([float(row["total_return_index"]) for row in index]),
        "index": index,
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _horizon_returns(values: Sequence[float], horizon: int) -> list[float]:
    if horizon < 1:
        raise MetricError("horizon must be >= 1")
    if len(values) < horizon:
        raise MetricError("insufficient returns for requested horizon")
    result: list[float] = []
    for start in range(len(values) - horizon + 1):
        gross = 1.0
        for value in values[start : start + horizon]:
            gross *= 1.0 + value
        result.append(gross - 1.0)
    return result


def risk_metrics(
    rows: Sequence[Mapping[str, object]],
    *,
    benchmark_rows: Sequence[Mapping[str, object]] | None = None,
    risk_free: float = 0.0,
    periods_per_year: int = 252,
    confidence: float = 0.95,
    horizon: int = 1,
) -> dict[str, object]:
    risk_free = _number(risk_free, "risk_free", minimum=-0.999999)
    if periods_per_year < 1:
        raise MetricError("periods_per_year must be >= 1")
    if not 0.5 < confidence < 1.0:
        raise MetricError("confidence must be between 0.5 and 1.0")
    index = build_indices(rows)
    dated_returns = _returns(index, "total_return_index")
    values = [value for _, value in dated_returns]
    if len(values) < 2:
        raise MetricError("risk metrics require at least two returns")
    mean_period = statistics.fmean(values)
    volatility = statistics.stdev(values) * math.sqrt(periods_per_year)
    rf_period = (1.0 + risk_free) ** (1.0 / periods_per_year) - 1.0
    annual_excess = (mean_period - rf_period) * periods_per_year
    sharpe = annual_excess / volatility if volatility > 0 else None
    downside = [min(value - rf_period, 0.0) for value in values]
    downside_deviation = math.sqrt(statistics.fmean(value * value for value in downside)) * math.sqrt(periods_per_year)
    sortino = annual_excess / downside_deviation if downside_deviation > 0 else None
    max_drawdown = _max_drawdown([float(row["total_return_index"]) for row in index])
    years = _elapsed_years(str(index[0]["date"]), str(index[-1]["date"]))
    cagr = _cagr(100.0, float(index[-1]["total_return_index"]), years)
    calmar = cagr / abs(max_drawdown) if cagr is not None and max_drawdown < 0 else None

    horizon_values = _horizon_returns(values, horizon)
    tail_quantile = _quantile(horizon_values, 1.0 - confidence)
    historical_var = max(0.0, -tail_quantile)
    z = NormalDist().inv_cdf(1.0 - confidence)
    parametric_quantile = mean_period * horizon + z * statistics.stdev(values) * math.sqrt(horizon)
    parametric_var = max(0.0, -parametric_quantile)

    relative: dict[str, object] | None = None
    if benchmark_rows is not None:
        benchmark_index = build_indices(benchmark_rows)
        benchmark_returns = dict(_returns(benchmark_index, "total_return_index"))
        pairs = [
            (value, benchmark_returns[interval])
            for interval, value in dated_returns
            if interval in benchmark_returns
        ]
        if len(pairs) < 2:
            raise MetricError("benchmark alignment produced fewer than two common return intervals")
        security_values = [pair[0] for pair in pairs]
        benchmark_values = [pair[1] for pair in pairs]
        benchmark_variance = statistics.variance(benchmark_values)
        beta = statistics.covariance(security_values, benchmark_values) / benchmark_variance if benchmark_variance > 0 else None
        correlation = statistics.correlation(security_values, benchmark_values) if statistics.stdev(security_values) > 0 and statistics.stdev(benchmark_values) > 0 else None
        active = [security - benchmark for security, benchmark in pairs]
        tracking_error = statistics.stdev(active) * math.sqrt(periods_per_year)
        active_annual = statistics.fmean(active) * periods_per_year
        information_ratio = active_annual / tracking_error if tracking_error > 0 else None
        alpha = None if beta is None else (
            statistics.fmean(security_values) * periods_per_year
            - (risk_free + beta * (statistics.fmean(benchmark_values) * periods_per_year - risk_free))
        )
        relative = {
            "common_return_intervals": len(pairs),
            "beta": beta,
            "alpha": alpha,
            "correlation": correlation,
            "tracking_error": tracking_error,
            "information_ratio": information_ratio,
        }

    return {
        "units": "decimal",
        "periods_per_year": periods_per_year,
        "risk_free_annual": risk_free,
        "annualized_arithmetic_return": mean_period * periods_per_year,
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "downside_deviation": downside_deviation,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "cagr": cagr,
        "calmar": calmar,
        "var": {
            "sign": "positive_loss",
            "confidence": confidence,
            "horizon_periods": horizon,
            "historical": historical_var,
            "parametric_normal": parametric_var,
        },
        "relative": relative,
    }


def liquidity_metrics(shares: float, adtv: float, participation: float) -> dict[str, object]:
    shares = _number(shares, "shares", minimum=0.0)
    adtv = _number(adtv, "adtv", minimum=0.0000001)
    participation = _number(participation, "participation", minimum=0.0000001)
    if participation > 1.0:
        raise MetricError("participation must be a decimal between 0 and 1")
    daily_capacity = adtv * participation
    days = math.ceil(shares / daily_capacity) if shares else 0
    timeline: list[dict[str, float | int]] = []
    remaining = shares
    for day_number in range(1, days + 1):
        executed = min(remaining, daily_capacity)
        remaining -= executed
        timeline.append({
            "day": day_number,
            "executed_shares": executed,
            "remaining_shares": max(remaining, 0.0),
        })
    return {
        "shares": shares,
        "adtv": adtv,
        "participation": participation,
        "daily_capacity": daily_capacity,
        "days_to_liquidate": days,
        "timeline": timeline,
        "limitations": ["linear capacity only", "no market impact", "no volatility or spread adjustment"],
    }


def _load_rows(path: str) -> list[Mapping[str, object]]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, list):
        raise MetricError(f"{path} must contain a JSON array")
    return value


def _write(value: object, output: str | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False)
    if output:
        Path(output).write_text(text + "\n")
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    returns = subparsers.add_parser("returns")
    returns.add_argument("series")
    returns.add_argument("--inflation", type=float, default=0.0)
    returns.add_argument("--output")
    risk = subparsers.add_parser("risk")
    risk.add_argument("series")
    risk.add_argument("--benchmark")
    risk.add_argument("--risk-free", type=float, default=0.0)
    risk.add_argument("--periods", type=int, default=252)
    risk.add_argument("--confidence", type=float, default=0.95)
    risk.add_argument("--horizon", type=int, default=1)
    risk.add_argument("--output")
    liquidity = subparsers.add_parser("liquidity")
    liquidity.add_argument("--shares", type=float, required=True)
    liquidity.add_argument("--adtv", type=float, required=True)
    liquidity.add_argument("--participation", type=float, required=True)
    liquidity.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "returns":
            result = returns_metrics(_load_rows(args.series), args.inflation)
        elif args.command == "risk":
            benchmark = _load_rows(args.benchmark) if args.benchmark else None
            result = risk_metrics(
                _load_rows(args.series),
                benchmark_rows=benchmark,
                risk_free=args.risk_free,
                periods_per_year=args.periods,
                confidence=args.confidence,
                horizon=args.horizon,
            )
        else:
            result = liquidity_metrics(args.shares, args.adtv, args.participation)
        _write(result, args.output)
    except (OSError, json.JSONDecodeError, MetricError, statistics.StatisticsError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
