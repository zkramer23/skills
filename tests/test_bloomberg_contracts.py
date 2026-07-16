from __future__ import annotations

import json
import sys
from types import ModuleType

import polars as pl
import pytest

from issuer_lookup import check_approved
from market_data_types import (
    BULK_DATA_SCHEMA,
    ERROR_SCHEMA,
    REF_DATA_SCHEMA,
    RefResult,
    frame,
)


def test_result_frames_keep_schemas_when_empty() -> None:
    result = RefResult(
        data=frame([], REF_DATA_SCHEMA),
        bulk=frame([], BULK_DATA_SCHEMA),
        errors=frame([], ERROR_SCHEMA),
    )

    assert result.data.schema == pl.Schema(REF_DATA_SCHEMA)
    assert result.bulk.schema == pl.Schema(BULK_DATA_SCHEMA)
    assert result.errors.schema == pl.Schema(ERROR_SCHEMA)


def test_reference_parser_separates_scalar_and_bulk_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "blpapi", ModuleType("blpapi"))
    sys.modules.pop("reference_data", None)
    from reference_data import _partition_field_data

    scalar, bulk = _partition_field_data(
        "SPX Index",
        ["PX_LAST", "INDX_MEMBERS"],
        {
            "PX_LAST": 6500.25,
            "INDX_MEMBERS": [
                {"Member Ticker and Exchange Code": "AAPL UW"},
                {"Member Ticker and Exchange Code": "MSFT UW"},
            ],
        },
    )

    assert scalar == [{
        "security": "SPX Index",
        "field": "PX_LAST",
        "value": "6500.25",
        "value_type": "float",
    }]
    assert [json.loads(row["value_json"]) for row in bulk] == [
        {"Member Ticker and Exchange Code": "AAPL UW"},
        {"Member Ticker and Exchange Code": "MSFT UW"},
    ]


def test_issuer_approval_matches_complete_parent_identifier() -> None:
    profile = pl.DataFrame({
        "security": ["note-a", "note-b"],
        "ULT_PARENT_TICKER_EXCHANGE": ["MS UN", "MS LN"],
    })

    result = check_approved(profile, {"MS UN"})

    assert result["approved"].to_list() == [True, False]


def test_issuer_approval_requires_identity_column() -> None:
    with pytest.raises(ValueError, match="missing identity field"):
        check_approved(pl.DataFrame({"security": ["note-a"]}), {"MS UN"})
