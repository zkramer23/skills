"""Issuer lookup for approved-counterparty checks.

Structured notes are often issued by financing shells (MSFL, Citigroup Global
Markets Holdings) and guaranteed by the parent — approval and ratings checks
belong to the GUARANTOR. Resolve the ultimate parent, then rate it.
"""

from __future__ import annotations

import logging

import polars as pl

from market_data_types import ReferenceDataProvider, RefResult

logger = logging.getLogger(__name__)

ISSUER_FIELDS = ["ISSUER", "ULT_PARENT_TICKER_EXCHANGE", "COUNTRY_ISO",
                 "RTG_MOODY", "RTG_SP", "RTG_FITCH", "SECURITY_NAME"]


def issuer_profile(bbg: ReferenceDataProvider, securities: list[str]) -> pl.DataFrame:
    """Wide issuer/rating profile per security (note Corp ticker, /cusip/, or equity)."""
    result: RefResult = bbg.get_reference(securities, ISSUER_FIELDS)
    if result.errors.height:
        for e in result.errors.iter_rows(named=True):
            logger.warning("issuer lookup issue %s %s: %s",
                           e["security"], e["field"], e["message"])
    if not result.data.height:
        return pl.DataFrame()
    return result.data.pivot(on="field", index="security", values="value")


def check_approved(
    profile: pl.DataFrame,
    approved_parent_identifiers: set[str],
    *,
    identity_field: str = "ULT_PARENT_TICKER_EXCHANGE",
) -> pl.DataFrame:
    """Match exact parent identifiers; never approve on a ticker prefix alone."""
    if identity_field not in profile.columns:
        raise ValueError(f"issuer profile is missing identity field {identity_field!r}")
    approved = sorted(value.strip().upper() for value in approved_parent_identifiers)
    return profile.with_columns(
        approved=pl.col(identity_field)
                   .str.strip_chars()
                   .str.to_uppercase()
                   .is_in(approved)
    )


if __name__ == "__main__":
    from reference_data import BlpapiClient

    logging.basicConfig(level=logging.INFO)
    # Store the exact resolved parent identifier, including exchange. For a
    # production approval list prefer a legal-entity/guarantor master keyed by
    # LEI or another stable identifier and join it before this check.
    approved = {"MS UN", "C UN", "GS UN", "JPM UN", "BAC UN", "UBSG SE", "RY CN"}
    with BlpapiClient() as bbg:
        profile = issuer_profile(bbg, ["/cusip/17332YQM3"])   # the note itself (Corp)
    print(check_approved(profile, approved))
