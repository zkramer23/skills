"""Provider contracts shared by live Bloomberg clients and offline tests.

This module deliberately does not import ``blpapi``. Business logic, mocks,
and replay providers can import these types on machines without a Terminal or
Bloomberg's Python package.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Mapping, Protocol, Sequence, runtime_checkable

import polars as pl


REF_DATA_SCHEMA = {
    "security": pl.String,
    "field": pl.String,
    "value": pl.String,
    "value_type": pl.String,
}
BULK_DATA_SCHEMA = {
    "security": pl.String,
    "field": pl.String,
    "row": pl.UInt32,
    "value_json": pl.String,
}
ERROR_SCHEMA = {
    "security": pl.String,
    "field": pl.String,
    "category": pl.String,
    "message": pl.String,
}
BAR_DATA_SCHEMA = {
    "security": pl.String,
    "time_utc": pl.Datetime,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Int64,
    "num_events": pl.Int64,
}


def frame(rows: list[dict[str, object]], schema: Mapping[str, pl.DataType]) -> pl.DataFrame:
    """Build a schema-stable frame, including when ``rows`` is empty."""
    return pl.DataFrame(rows, schema=schema, strict=False)


def history_schema(fields: Sequence[str]) -> dict[str, pl.DataType]:
    return {"security": pl.String, "date": pl.Date, **{field: pl.Float64 for field in fields}}


@dataclass(frozen=True)
class RefResult:
    data: pl.DataFrame
    bulk: pl.DataFrame
    errors: pl.DataFrame


@dataclass(frozen=True)
class HistoryResult:
    data: pl.DataFrame
    errors: pl.DataFrame


@dataclass(frozen=True)
class BarResult:
    data: pl.DataFrame
    errors: pl.DataFrame


@runtime_checkable
class ReferenceDataProvider(Protocol):
    def get_reference(
        self,
        securities: Sequence[str],
        fields: Sequence[str],
        overrides: Mapping[str, str] | None = None,
    ) -> RefResult: ...


@runtime_checkable
class HistoryDataProvider(Protocol):
    def get_history(
        self,
        securities: Sequence[str],
        fields: Sequence[str],
        start: date,
        end: date,
        *,
        adjusted: bool = False,
        periodicity: str = "DAILY",
    ) -> HistoryResult: ...


@runtime_checkable
class BarDataProvider(Protocol):
    def get_bars(
        self,
        security: str,
        start: datetime,
        end: datetime,
        *,
        interval_min: int = 5,
        event_type: str = "TRADE",
    ) -> BarResult: ...


@runtime_checkable
class MarketDataProvider(
    ReferenceDataProvider,
    HistoryDataProvider,
    BarDataProvider,
    Protocol,
):
    """Composite contract for clients that provide every supported data shape."""
