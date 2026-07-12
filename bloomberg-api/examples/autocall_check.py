"""Autocall determination across an observation schedule.

HARD GUARD: only trigger-automatic calls are determinable from market data.
Issuer-elective notes (contingent_yield_note with callType="issuer" in the
prospectus-extraction taxonomy) redeem when the issuer says so — a level can
never prove that. This module refuses to guess.

Per-row autocall levels come from the schedule (handles step-downs). Once
called, the note is dead: the scan stops — later coupons don't exist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import polars as pl

from lifecycle_coupon_check import Underlier, worst_performance

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ObservationRow:
    observation_date: date
    autocall_level: float | None    # fraction of initial; None during non-call period
    call_premium: float | None      # snowball step-up; None/0 = redeems at par


class NotAutocallableError(ValueError):
    """Raised when asked to determine calls for a non-automatic note."""


def autocall_scan(closes: pl.DataFrame, underliers: list[Underlier],
                  schedule: list[ObservationRow], *, call_type: str | None) -> pl.DataFrame:
    if call_type != "automatic":
        raise NotAutocallableError(
            f"callType={call_type!r}: only trigger-automatic calls are determinable "
            "from market levels. Issuer-elective/no-call notes need a redemption "
            "notice, not a data check.")

    obs_dates = [r.observation_date for r in schedule]
    worst = worst_performance(closes, underliers, obs_dates)
    levels = pl.DataFrame([{"date": r.observation_date,
                            "autocall_level": r.autocall_level,
                            "call_premium": r.call_premium} for r in schedule])
    merged = levels.join(worst, on="date", how="left").sort("date")

    rows: list[dict[str, object]] = []
    for r in merged.iter_rows(named=True):
        if r["autocall_level"] is None:                       # non-call period
            rows.append({**r, "status": "NOT CALLABLE (non-call period)"})
            continue
        if r["worst_perf"] is None:
            rows.append({**r, "status": "UNDETERMINED (missing level — check postponement)"})
            continue
        if r["worst_perf"] >= r["autocall_level"]:            # "at or above"
            rows.append({**r, "status": "CALLED"})
            logger.info("indicative autocall on %s (worst %s at %.4f >= %.4f)",
                        r["date"], r["worst_security"], r["worst_perf"], r["autocall_level"])
            return pl.DataFrame(rows)                         # note is dead — stop
        rows.append({**r, "status": "NOT CALLED"})
    return pl.DataFrame(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from historical_data import HistoryClient

    underliers = [Underlier("NDX Index", 29446.18),
                  Underlier("RTY Index", 2921.029),
                  Underlier("KRE US Equity", 72.35)]
    schedule = [ObservationRow(date(2026, 12, 11), 1.00, None),
                ObservationRow(date(2027, 1, 11), 1.00, None)]

    with HistoryClient() as bbg:
        closes = bbg.get_history([u.security for u in underliers], ["PX_LAST"],
                                 start=date(2026, 12, 11), end=date(2027, 1, 11))
    # The Citi note is issuer-callable → this raises NotAutocallableError, by design:
    print(autocall_scan(closes, underliers, schedule, call_type="automatic"))
