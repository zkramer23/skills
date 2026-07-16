"""Worst-of contingent coupon check with memory, over an observation schedule.

Pure lifecycle math (no provider calls inside) — feed it closes from
historical_data.get_history() or a test fixture. Encodes the rules from
references/structured-products.md:

- worst performance undefined if ANY underlier lacks a level that date
- the document's inequality is law ("at or above" → >=)
- memory coupons pay all previously missed periods on a paying observation
- results are INDICATIVE (calc agent's fixing is contractual)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

import polars as pl

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Underlier:
    security: str
    initial_level: float


@dataclass(frozen=True)
class CouponTerms:
    coupon_barrier: float          # fraction of initial, e.g. 0.70
    coupon_per_period: float       # e.g. 0.009333 (0.9333%)
    memory: bool


def worst_performance(closes: pl.DataFrame, underliers: list[Underlier],
                      obs_dates: list[date]) -> pl.DataFrame:
    """date | worst_perf | worst_security — null row when any underlier is missing."""
    if not underliers:
        raise ValueError("underliers must be non-empty")
    securities = [underlier.security for underlier in underliers]
    if any(not security.strip() for security in securities):
        raise ValueError("underlier securities must be non-empty")
    if len(set(securities)) != len(securities):
        raise ValueError("underlier securities must be unique")
    if any(
        not math.isfinite(underlier.initial_level) or underlier.initial_level <= 0
        for underlier in underliers
    ):
        raise ValueError("underlier initial levels must be finite and positive")
    if len(set(obs_dates)) != len(obs_dates):
        raise ValueError("observation dates must be unique")
    required = {"security", "date", "PX_LAST"}
    missing_columns = required.difference(closes.columns)
    if missing_columns:
        raise ValueError(f"closes is missing required columns: {sorted(missing_columns)}")

    ordered_dates = sorted(obs_dates)
    date_frame = pl.DataFrame({"date": ordered_dates}, schema={"date": pl.Date})
    if not ordered_dates:
        return date_frame.with_columns(
            worst_perf=pl.lit(None, dtype=pl.Float64),
            worst_security=pl.lit(None, dtype=pl.String),
        )

    relevant = closes.filter(
        pl.col("date").is_in(ordered_dates) & pl.col("security").is_in(securities)
    )
    duplicates = (
        relevant.group_by(["date", "security"])
        .len()
        .filter(pl.col("len") > 1)
    )
    if duplicates.height:
        keys = duplicates.select("date", "security").to_dicts()
        raise ValueError(f"duplicate close rows for observation keys: {keys}")

    terms = pl.DataFrame([{"security": u.security, "initial": u.initial_level}
                          for u in underliers])
    perf = (relevant.join(terms, on="security", how="inner")
                  .with_columns(perf=pl.col("PX_LAST") / pl.col("initial")))
    counts = perf.group_by("date").agg(
        n_securities=pl.col("security").n_unique(),
        n_levels=pl.col("PX_LAST").count(),
    )
    worst = (
        perf.filter(pl.col("perf").is_not_null())
        .sort(["date", "perf", "security"])
        .group_by("date", maintain_order=True)
        .agg(
            worst_perf=pl.col("perf").first(),
            worst_security=pl.col("security").first(),
        )
    )
    return (
        date_frame.join(counts, on="date", how="left")
        .join(worst, on="date", how="left")
        .with_columns(
            n_securities=pl.col("n_securities").fill_null(0),
            n_levels=pl.col("n_levels").fill_null(0),
        )
        .with_columns(
            worst_perf=pl.when(
                (pl.col("n_securities") == len(underliers))
                & (pl.col("n_levels") == len(underliers))
            ).then(pl.col("worst_perf")).otherwise(None),
            worst_security=pl.when(
                (pl.col("n_securities") == len(underliers))
                & (pl.col("n_levels") == len(underliers))
            ).then(pl.col("worst_security")).otherwise(None),
        )
        .drop("n_securities", "n_levels")
        .sort("date")
    )


def coupon_schedule(worst: pl.DataFrame, terms: CouponTerms) -> pl.DataFrame:
    """Walk observations in order, tracking missed coupons for memory notes.

    Output per observation: paid?, amount (incl. catch-up), missed_so_far.
    A null worst_perf (missing data / disruption) is NOT a miss — it's
    undetermined, flagged for postponement handling per the note's terms.
    """
    if (
        not math.isfinite(terms.coupon_barrier)
        or not math.isfinite(terms.coupon_per_period)
        or terms.coupon_barrier < 0
        or terms.coupon_per_period < 0
    ):
        raise ValueError("coupon barrier and coupon amount must be finite and non-negative")
    required = {"date", "worst_perf", "worst_security"}
    missing_columns = required.difference(worst.columns)
    if missing_columns:
        raise ValueError(f"worst is missing required columns: {sorted(missing_columns)}")
    if worst["date"].null_count():
        raise ValueError("coupon observation dates must be non-null")
    if worst["date"].n_unique() != worst.height:
        raise ValueError("coupon observation dates must be unique")
    if not worst.height:
        return worst.with_columns(
            status=pl.lit(None, dtype=pl.String),
            amount=pl.lit(None, dtype=pl.Float64),
            missed_so_far=pl.lit(None, dtype=pl.Int64),
        )

    rows: list[dict[str, object]] = []
    missed = 0
    memory_state_unknown = False
    for r in worst.sort("date").iter_rows(named=True):
        if memory_state_unknown:
            rows.append({
                **r,
                "status": "UNDETERMINED (prior memory-coupon observation unresolved)",
                "amount": None,
                "missed_so_far": None,
            })
            continue
        if r["worst_perf"] is None:
            rows.append({**r, "status": "UNDETERMINED (missing level — check postponement)",
                         "amount": None, "missed_so_far": missed})
            memory_state_unknown = terms.memory
            continue
        pays = r["worst_perf"] >= terms.coupon_barrier      # "at or above"
        if pays:
            periods = 1 + (missed if terms.memory else 0)
            rows.append({**r, "status": "PAID", "amount": periods * terms.coupon_per_period,
                         "missed_so_far": 0})
            missed = 0
        else:
            missed += 1
            rows.append({**r, "status": "MISSED", "amount": 0.0, "missed_so_far": missed})
    return pl.DataFrame(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from historical_data import HistoryClient

    # Citi worst-of terms (from the prospectus-extraction output)
    underliers = [Underlier("NDX Index", 29446.18),
                  Underlier("RTY Index", 2921.029),
                  Underlier("KRE US Equity", 72.35)]
    terms = CouponTerms(coupon_barrier=0.70, coupon_per_period=0.009333, memory=False)
    obs = [date(2026, 7, 13)]        # first monthly valuation date

    with HistoryClient() as bbg:
        history = bbg.get_history([u.security for u in underliers], ["PX_LAST"],
                                  start=min(obs), end=max(obs))
    closes = history.data
    if history.errors.height:
        logger.warning("Bloomberg history returned %d item errors", history.errors.height)
    result = coupon_schedule(worst_performance(closes, underliers, obs), terms)
    print(result)   # indicative — official determination is the calc agent's
