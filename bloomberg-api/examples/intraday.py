"""Intraday bars using the canonical client from ``reference_data``.

Use bars for fixing-day forensics, not routine lifecycle processing. Start and
end must be timezone-aware; the boundary converts them to UTC.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from reference_data import BlpapiClient

IntradayClient = BlpapiClient


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with IntradayClient() as bloomberg:
        result = bloomberg.get_bars(
            "KRE US Equity",
            start=datetime(2026, 6, 11, 19, 30, tzinfo=timezone.utc),
            end=datetime(2026, 6, 11, 20, 5, tzinfo=timezone.utc),
            interval_min=1,
        )
    print(result.data)
    if result.errors.height:
        print("errors:\n", result.errors)
