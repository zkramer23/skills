"""Issuer lookup for approved-counterparty checks.

Structured notes are often issued by financing shells (MSFL, Citigroup Global
Markets Holdings) and guaranteed by the parent — approval and ratings checks
belong to the GUARANTOR. Resolve the ultimate parent, then rate it.
"""

from __future__ import annotations

import logging

import polars as pl

from reference_data import BlpapiClient, RefResult

logger = logging.getLogger(__name__)

ISSUER_FIELDS = ["ISSUER", "ULT_PARENT_TICKER_EXCHANGE", "COUNTRY_ISO",
                 "RTG_MOODY", "RTG_SP", "RTG_FITCH", "SECURITY_NAME"]


def issuer_profile(bbg: BlpapiClient, securities: list[str]) -> pl.DataFrame:
    """Wide issuer/rating profile per security (note Corp ticker, /cusip/, or equity)."""
    result: RefResult = bbg.get_reference(securities, ISSUER_FIELDS)
    if result.errors.height:
        for e in result.errors.iter_rows(named=True):
            logger.warning("issuer lookup issue %s %s: %s",
                           e["security"], e["field"], e["message"])
    if not result.data.height:
        return pl.DataFrame()
    return result.data.pivot(on="field", index="security", values="value")


def check_approved(profile: pl.DataFrame, approved_parents: set[str]) -> pl.DataFrame:
    """Flag securities whose ULTIMATE PARENT is not on the approved list."""
    return profile.with_columns(
        approved=pl.col("ULT_PARENT_TICKER_EXCHANGE")
                   .str.split(" ").list.first()          # "MS UN" → "MS"
                   .is_in(sorted(approved_parents)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    approved = {"MS", "C", "GS", "JPM", "BAC", "UBS", "RY"}
    with BlpapiClient() as bbg:
        profile = issuer_profile(bbg, ["/cusip/17332YQM3"])   # the note itself (Corp)
    print(check_approved(profile, approved))
