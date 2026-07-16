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
import math
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
    if not schedule:
        raise ValueError("autocall schedule must be non-empty")
    if len({row.observation_date for row in schedule}) != len(schedule):
        raise ValueError("autocall observation dates must be unique")
    if any(
        row.autocall_level is not None
        and (not math.isfinite(row.autocall_level) or row.autocall_level < 0)
        for row in schedule
    ):
        raise ValueError("autocall levels must be finite and non-negative when present")
    if any(
        row.call_premium is not None
        and (not math.isfinite(row.call_premium) or row.call_premium < 0)
        for row in schedule
    ):
        raise ValueError("call premiums must be finite and non-negative when present")
    has_trigger = any(row.autocall_level is not None for row in schedule)
    effective_call_type = "automatic" if call_type is None and has_trigger else call_type
    if call_type is None and has_trigger:
        logger.warning("callType is null; inferring automatic from the trigger schedule")
    if effective_call_type != "automatic":
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
    call_state_unknown = False
    for r in merged.iter_rows(named=True):
        if call_state_unknown:
            rows.append({**r, "status": "UNDETERMINED (prior call observation unresolved)"})
            continue
        if r["autocall_level"] is None:                       # non-call period
            rows.append({**r, "status": "NOT CALLABLE (non-call period)"})
            continue
        if r["worst_perf"] is None:
            rows.append({**r, "status": "UNDETERMINED (missing level — check postponement)"})
            call_state_unknown = True
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
        history = bbg.get_history([u.security for u in underliers], ["PX_LAST"],
                                  start=date(2026, 12, 11), end=date(2027, 1, 11))
    closes = history.data
    if history.errors.height:
        logger.warning("Bloomberg history returned %d item errors", history.errors.height)
    print(autocall_scan(closes, underliers, schedule, call_type="automatic"))
