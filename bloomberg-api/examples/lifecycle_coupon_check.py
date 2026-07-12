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
    terms = pl.DataFrame([{"security": u.security, "initial": u.initial_level}
                          for u in underliers])
    perf = (closes.filter(pl.col("date").is_in(obs_dates))
                  .join(terms, on="security", how="inner")
                  .with_columns(perf=pl.col("PX_LAST") / pl.col("initial")))
    return (perf.sort("perf")
                .group_by("date", maintain_order=False)
                .agg(n=pl.len(),
                     worst_perf=pl.col("perf").first(),
                     worst_security=pl.col("security").first())
                .with_columns(
                    worst_perf=pl.when(pl.col("n") == len(underliers))
                                 .then(pl.col("worst_perf")).otherwise(None),
                    worst_security=pl.when(pl.col("n") == len(underliers))
                                     .then(pl.col("worst_security")).otherwise(None))
                .drop("n")
                .sort("date"))


def coupon_schedule(worst: pl.DataFrame, terms: CouponTerms) -> pl.DataFrame:
    """Walk observations in order, tracking missed coupons for memory notes.

    Output per observation: paid?, amount (incl. catch-up), missed_so_far.
    A null worst_perf (missing data / disruption) is NOT a miss — it's
    undetermined, flagged for postponement handling per the note's terms.
    """
    rows: list[dict[str, object]] = []
    missed = 0
    for r in worst.sort("date").iter_rows(named=True):
        if r["worst_perf"] is None:
            rows.append({**r, "status": "UNDETERMINED (missing level — check postponement)",
                         "amount": None, "missed_so_far": missed})
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
        closes = bbg.get_history([u.security for u in underliers], ["PX_LAST"],
                                 start=min(obs), end=max(obs))
    result = coupon_schedule(worst_performance(closes, underliers, obs), terms)
    print(result)   # indicative — official determination is the calc agent's
