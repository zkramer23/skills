"""Historical closes using the canonical client from ``reference_data``.

``BlpapiClient.get_history`` returns ``HistoryResult(data, errors)``. History
is unadjusted by default for structured-note lifecycle work.
"""

from __future__ import annotations

import logging
from datetime import date

from reference_data import BlpapiClient

# Backward-compatible name for older snippets; all boundary behavior now lives
# in reference_data.py so this module never imports blpapi.
HistoryClient = BlpapiClient


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with HistoryClient() as bloomberg:
        result = bloomberg.get_history(
            securities=["NDX Index", "RTY Index", "KRE US Equity"],
            fields=["PX_LAST"],
            start=date(2026, 6, 1),
            end=date(2026, 7, 11),
        )
    print(result.data.tail(9))
    if result.errors.height:
        print("errors:\n", result.errors)
