"""Basket pricing: weighted basket level/return from constituent closes.

Basket constituents and weights come from the NOTE'S TERMS (the
prospectus-extraction underliers table) — never from INDX_MEMBERS. Barriers
on basket notes apply at the basket level. The lifecycle math is pure: data
comes in as a frame, so it tests offline with a mock provider.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import polars as pl

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BasketConstituent:
    security: str       # resolved Bloomberg ticker, e.g. "SX5E Index"
    initial_level: float
    weight: float       # equal-weight baskets: 1/n for each


def basket_returns(closes: pl.DataFrame, basket: list[BasketConstituent]) -> pl.DataFrame:
    """Per-date basket return: sum_i w_i * (close_i / initial_i) - 1.

    `closes`: security | date | PX_LAST (unadjusted).
    A date where ANY constituent lacks a close yields a null basket return —
    a partial basket is not a basket.
    """
    weights = abs(sum(c.weight for c in basket) - 1.0)
    if weights > 1e-6:
        raise ValueError(f"basket weights sum to {1.0 + weights:.4f}, expected 1.0")

    terms = pl.DataFrame([{"security": c.security, "initial": c.initial_level,
                           "weight": c.weight} for c in basket])
    perf = (closes.join(terms, on="security", how="inner")
                  .with_columns(contrib=pl.col("weight") * pl.col("PX_LAST") / pl.col("initial")))
    return (perf.group_by("date")
                .agg(n=pl.len(),
                     basket_level=pl.col("contrib").sum())
                .with_columns(
                    basket_level=pl.when(pl.col("n") == len(basket))
                                   .then(pl.col("basket_level"))
                                   .otherwise(None),        # incomplete date → null
                    basket_return=pl.when(pl.col("n") == len(basket))
                                    .then(pl.col("basket_level") - 1.0)
                                    .otherwise(None))
                .drop("n")
                .sort("date"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from datetime import date as d
    from historical_data import HistoryClient

    # Terms from the MS Trigger Absolute Return Step extraction (defined-weight basket)
    basket = [
        BasketConstituent("SX5E Index", 6187.63, 0.40),
        BasketConstituent("NKY Index", 66020.04, 0.25),
        BasketConstituent("UKX Index", 10471.72, 0.175),
        BasketConstituent("SMI Index", 13708.02, 0.10),
        BasketConstituent("AS51 Index", 8804.037, 0.075),
    ]
    with HistoryClient() as bbg:
        closes = bbg.get_history([c.security for c in basket], ["PX_LAST"],
                                 start=d(2026, 6, 12), end=d(2026, 7, 11))
    print(basket_returns(closes, basket).tail(5))
