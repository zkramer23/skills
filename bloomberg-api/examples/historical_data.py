"""Historical closes for lifecycle work: unadjusted, ready to join to schedules.

Adds get_history() to the client pattern from reference_data.py. Unadjusted
by default — structured-note fixings compare against levels struck in the
past, and adjusted series rewrite them (references/request-types.md).
"""

from __future__ import annotations

import logging
from datetime import date

import polars as pl

from reference_data import REFDATA, BlpapiClient

logger = logging.getLogger(__name__)


class HistoryClient(BlpapiClient):
    def get_history(self, securities: list[str], fields: list[str],
                    start: date, end: date, *, adjusted: bool = False,
                    periodicity: str = "DAILY") -> pl.DataFrame:
        service = self._session.getService(REFDATA)
        req = service.createRequest("HistoricalDataRequest")
        for s in securities:
            req.getElement("securities").appendValue(s)
        for f in fields:
            req.getElement("fields").appendValue(f)
        req.set("startDate", start.strftime("%Y%m%d"))
        req.set("endDate", end.strftime("%Y%m%d"))
        req.set("periodicitySelection", periodicity)
        req.set("nonTradingDayFillOption", "ACTIVE_DAYS_ONLY")
        # explicit, not terminal-DPDF-dependent:
        req.set("adjustmentFollowDPDF", False)
        for flag in ("adjustmentSplit", "adjustmentNormal", "adjustmentAbnormal"):
            req.set(flag, adjusted)

        rows: list[dict[str, object]] = []
        for msg in self._collect(req):           # one message per security
            sd = msg.getElement("securityData")
            sec = sd.getElementAsString("security")
            if sd.hasElement("securityError"):
                logger.warning("bbg.security_error %s: %s", sec,
                               sd.getElement("securityError"))
                continue
            fdata = sd.getElement("fieldData")
            for i in range(fdata.numValues()):
                point = fdata.getValueAsElement(i)
                row: dict[str, object] = {
                    "security": sec,
                    "date": point.getElementAsDatetime("date").date(),
                }
                for f in fields:
                    row[f] = point.getElementAsFloat(f) if point.hasElement(f) else None
                rows.append(row)
        return pl.DataFrame(rows).sort(["security", "date"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with HistoryClient() as bbg:
        closes = bbg.get_history(
            securities=["NDX Index", "RTY Index", "KRE US Equity"],
            fields=["PX_LAST"],
            start=date(2026, 6, 1), end=date(2026, 7, 11),
        )
    print(closes.tail(9))
