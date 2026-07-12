"""Intraday bars: one security per request, UTC datetimes.

Use case for structured products: forensics around a fixing on a disrupted
day — NOT routine lifecycle work, which runs on official closes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import blpapi
import polars as pl

from reference_data import REFDATA, BlpapiClient

logger = logging.getLogger(__name__)


class IntradayClient(BlpapiClient):
    def get_bars(self, security: str, start: datetime, end: datetime,
                 *, interval_min: int = 5, event_type: str = "TRADE") -> pl.DataFrame:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware — blpapi treats them as UTC")
        start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)

        service = self._session.getService(REFDATA)
        req = service.createRequest("IntradayBarRequest")
        req.set("security", security)                 # exactly one per request
        req.set("eventType", event_type)              # TRADE | BID | ASK
        req.set("interval", interval_min)             # 1..1440 minutes
        req.set("startDateTime", blpapi.Datetime.fromdatetime(start))
        req.set("endDateTime", blpapi.Datetime.fromdatetime(end))

        rows: list[dict[str, object]] = []
        for msg in self._collect(req):
            bars = msg.getElement("barData").getElement("barTickData")
            for i in range(bars.numValues()):
                b = bars.getValueAsElement(i)
                rows.append({
                    "security": security,
                    "time_utc": b.getElementAsDatetime("time"),
                    "open": b.getElementAsFloat("open"),
                    "high": b.getElementAsFloat("high"),
                    "low": b.getElementAsFloat("low"),
                    "close": b.getElementAsFloat("close"),
                    "volume": b.getElementAsInteger("volume"),
                    "num_events": b.getElementAsInteger("numEvents"),
                })
        return pl.DataFrame(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # NYSE close window on a valuation date, expressed in UTC (16:00 ET = 20:00 UTC in June)
    with IntradayClient() as bbg:
        bars = bbg.get_bars(
            "KRE US Equity",
            start=datetime(2026, 6, 11, 19, 30, tzinfo=timezone.utc),
            end=datetime(2026, 6, 11, 20, 5, tzinfo=timezone.utc),
            interval_min=1,
        )
    print(bars)
