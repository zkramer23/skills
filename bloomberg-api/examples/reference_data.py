"""Canonical Bloomberg boundary client for reference, history, and bars.

This is the only example module that imports ``blpapi``. It owns the session,
request construction, message parsing, and error normalization. Everything
above this boundary consumes the contracts from ``market_data_types`` and is
therefore importable and testable without Bloomberg installed.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, time as time_value, timezone
from typing import Any, Mapping, Sequence
from uuid import uuid4

import blpapi
import polars as pl

from market_data_types import (
    BAR_DATA_SCHEMA,
    BULK_DATA_SCHEMA,
    ERROR_SCHEMA,
    REF_DATA_SCHEMA,
    BarResult,
    HistoryResult,
    RefResult,
    frame,
    history_schema,
)

logger = logging.getLogger(__name__)

REFDATA = "//blp/refdata"


class BloombergError(Exception): ...
class BloombergConnectionError(BloombergError): ...
class BloombergTimeoutError(BloombergError): ...
class BloombergRequestError(BloombergError): ...
class BloombergEntitlementError(BloombergRequestError): ...


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime, time_value)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _scalar_value(value: object) -> tuple[str | None, str]:
    if value is None:
        return None, "null"
    if isinstance(value, (date, datetime, time_value)):
        return value.isoformat(), type(value).__name__
    if isinstance(value, bytes):
        return value.decode(errors="replace"), "bytes"
    return str(value), type(value).__name__


def _partition_field_data(
    security: str,
    fields: Sequence[str],
    values: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Split native ``Element.toPy()`` output into scalar and bulk rows."""
    scalar_rows: list[dict[str, object]] = []
    bulk_rows: list[dict[str, object]] = []
    for field in fields:
        if field not in values:
            continue
        value = values[field]
        if isinstance(value, list):
            for index, item in enumerate(value):
                bulk_rows.append({
                    "security": security,
                    "field": field,
                    "row": index,
                    "value_json": json.dumps(item, sort_keys=True, default=_json_default),
                })
        elif isinstance(value, dict):
            bulk_rows.append({
                "security": security,
                "field": field,
                "row": 0,
                "value_json": json.dumps(value, sort_keys=True, default=_json_default),
            })
        else:
            text, value_type = _scalar_value(value)
            scalar_rows.append({
                "security": security,
                "field": field,
                "value": text,
                "value_type": value_type,
            })
    return scalar_rows, bulk_rows


def _error_row(
    security: str,
    error: Mapping[str, object],
    *,
    field: str | None = None,
) -> dict[str, object]:
    return {
        "security": security,
        "field": field,
        "category": str(error.get("category") or error.get("subcategory") or "UNKNOWN"),
        "message": str(error.get("message") or error),
    }


def _field_exception_rows(
    security: str,
    exceptions: object,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not isinstance(exceptions, list):
        return rows
    for exception in exceptions:
        if not isinstance(exception, Mapping):
            continue
        info = exception.get("errorInfo")
        error = info if isinstance(info, Mapping) else exception
        rows.append(_error_row(security, error, field=str(exception.get("fieldId") or "") or None))
    return rows


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


class BlpapiClient:
    """Thin, session-owning Bloomberg client. Use as a context manager."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8194,
        timeout_ms: int = 30_000,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout_ms = timeout_ms
        self._session: blpapi.Session | None = None

    def _new_session(self) -> blpapi.Session:
        options = blpapi.SessionOptions()
        options.setServerHost(self._host)
        options.setServerPort(self._port)
        options.setAutoRestartOnDisconnection(True)
        return blpapi.Session(options)

    def __enter__(self) -> "BlpapiClient":
        for attempt in range(1, 4):
            session = self._new_session()
            if session.start():
                if session.openService(REFDATA):
                    self._session = session
                    return self
                session.stop()
            if attempt < 3:
                logger.warning("Bloomberg start failed (attempt %d/3)", attempt)
                time.sleep(2.0 * 2 ** (attempt - 1))
        raise BloombergConnectionError(
            f"Cannot reach Bloomberg on {self._host}:{self._port} — "
            "is the Terminal running and logged in?"
        )

    def __exit__(self, *exc: object) -> None:
        if self._session is not None:
            self._session.stop()
            self._session = None

    def _active_session(self) -> blpapi.Session:
        if self._session is None:
            raise BloombergConnectionError("BlpapiClient must be used inside a with block")
        return self._session

    def _raise_request_error(self, cid: blpapi.CorrelationId, detail: object) -> None:
        message = f"cid={cid.value()}: {detail}"
        if any(word in message.lower() for word in ("entitlement", "permission", "not authorized")):
            raise BloombergEntitlementError(message)
        raise BloombergRequestError(message)

    def _collect(self, request: blpapi.Request) -> list[blpapi.Message]:
        session = self._active_session()
        cid = blpapi.CorrelationId(uuid4().hex)
        started = time.monotonic()
        deadline = started + self._timeout_ms / 1000
        session.sendRequest(request, correlationId=cid)
        messages: list[blpapi.Message] = []
        while True:
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                session.cancel(cid)
                raise BloombergTimeoutError(
                    f"cid={cid.value()}: request exceeded {self._timeout_ms}ms"
                )
            event = session.nextEvent(remaining_ms)
            if event.eventType() == blpapi.Event.TIMEOUT:
                session.cancel(cid)
                raise BloombergTimeoutError(
                    f"cid={cid.value()}: request exceeded {self._timeout_ms}ms"
                )

            matched = False
            for message in event:
                if cid not in message.correlationIds():
                    continue
                matched = True
                if message.hasElement("responseError"):
                    self._raise_request_error(cid, message.getElement("responseError").toPy())
                messages.append(message)

            if event.eventType() == blpapi.Event.REQUEST_STATUS and matched:
                self._raise_request_error(cid, messages[-1])
            if event.eventType() == blpapi.Event.RESPONSE and matched:
                logger.info(
                    "bbg.request cid=%s ms=%d msgs=%d",
                    cid.value(),
                    (time.monotonic() - started) * 1000,
                    len(messages),
                )
                return messages

    def get_reference(
        self,
        securities: Sequence[str],
        fields: Sequence[str],
        overrides: Mapping[str, str] | None = None,
    ) -> RefResult:
        if not securities or not fields:
            raise ValueError("securities and fields must both be non-empty")
        service = self._active_session().getService(REFDATA)
        request = service.createRequest("ReferenceDataRequest")
        for security in securities:
            request.getElement("securities").appendValue(security)
        for field in fields:
            request.getElement("fields").appendValue(field)
        for key, value in (overrides or {}).items():
            override = request.getElement("overrides").appendElement()
            override.setElement("fieldId", key)
            override.setElement("value", value)

        rows: list[dict[str, object]] = []
        bulk: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []
        for message in self._collect(request):
            payload = message.getElement("securityData").toPy()
            security_rows = payload if isinstance(payload, list) else [payload]
            for item in security_rows:
                if not isinstance(item, Mapping):
                    continue
                security = str(item.get("security") or "")
                security_error = item.get("securityError")
                if isinstance(security_error, Mapping):
                    errors.append(_error_row(security, security_error))
                    continue
                errors.extend(_field_exception_rows(security, item.get("fieldExceptions")))
                field_data = item.get("fieldData")
                if isinstance(field_data, Mapping):
                    scalar_rows, bulk_rows = _partition_field_data(security, fields, field_data)
                    rows.extend(scalar_rows)
                    bulk.extend(bulk_rows)

        return RefResult(
            data=frame(rows, REF_DATA_SCHEMA),
            bulk=frame(bulk, BULK_DATA_SCHEMA),
            errors=frame(errors, ERROR_SCHEMA),
        )

    def get_history(
        self,
        securities: Sequence[str],
        fields: Sequence[str],
        start: date,
        end: date,
        *,
        adjusted: bool = False,
        periodicity: str = "DAILY",
    ) -> HistoryResult:
        if not securities or not fields:
            raise ValueError("securities and fields must both be non-empty")
        if start > end:
            raise ValueError("start must be on or before end")
        service = self._active_session().getService(REFDATA)
        request = service.createRequest("HistoricalDataRequest")
        for security in securities:
            request.getElement("securities").appendValue(security)
        for field in fields:
            request.getElement("fields").appendValue(field)
        request.set("startDate", start.strftime("%Y%m%d"))
        request.set("endDate", end.strftime("%Y%m%d"))
        request.set("periodicitySelection", periodicity)
        request.set("nonTradingDayFillOption", "ACTIVE_DAYS_ONLY")
        request.set("adjustmentFollowDPDF", False)
        for flag in ("adjustmentSplit", "adjustmentNormal", "adjustmentAbnormal"):
            request.set(flag, adjusted)

        rows: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []
        for message in self._collect(request):
            item = message.getElement("securityData").toPy()
            if not isinstance(item, Mapping):
                continue
            security = str(item.get("security") or "")
            security_error = item.get("securityError")
            if isinstance(security_error, Mapping):
                errors.append(_error_row(security, security_error))
                continue
            errors.extend(_field_exception_rows(security, item.get("fieldExceptions")))
            points = item.get("fieldData")
            if not isinstance(points, list):
                continue
            for point in points:
                if not isinstance(point, Mapping) or point.get("date") is None:
                    continue
                row: dict[str, object] = {
                    "security": security,
                    "date": _as_date(point["date"]),
                }
                for field in fields:
                    try:
                        row[field] = _as_float(point.get(field))
                    except (TypeError, ValueError):
                        row[field] = None
                        errors.append({
                            "security": security,
                            "field": field,
                            "category": "PARSE_ERROR",
                            "message": f"Expected numeric historical value, got {point.get(field)!r}",
                        })
                rows.append(row)

        data = frame(rows, history_schema(fields))
        if data.height:
            data = data.sort(["security", "date"])
        return HistoryResult(data=data, errors=frame(errors, ERROR_SCHEMA))

    def get_bars(
        self,
        security: str,
        start: datetime,
        end: datetime,
        *,
        interval_min: int = 5,
        event_type: str = "TRADE",
    ) -> BarResult:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware")
        if start >= end:
            raise ValueError("start must be before end")
        if not 1 <= interval_min <= 1440:
            raise ValueError("interval_min must be between 1 and 1440")
        start_utc = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)

        service = self._active_session().getService(REFDATA)
        request = service.createRequest("IntradayBarRequest")
        request.set("security", security)
        request.set("eventType", event_type)
        request.set("interval", interval_min)
        request.set("startDateTime", blpapi.Datetime.fromdatetime(start_utc))
        request.set("endDateTime", blpapi.Datetime.fromdatetime(end_utc))

        rows: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []
        for message in self._collect(request):
            bar_data = message.getElement("barData").toPy()
            if not isinstance(bar_data, Mapping):
                continue
            response_error = bar_data.get("responseError")
            if isinstance(response_error, Mapping):
                errors.append(_error_row(security, response_error))
                continue
            points = bar_data.get("barTickData")
            if not isinstance(points, list):
                continue
            for point in points:
                if not isinstance(point, Mapping):
                    continue
                rows.append({
                    "security": security,
                    "time_utc": point.get("time"),
                    "open": point.get("open"),
                    "high": point.get("high"),
                    "low": point.get("low"),
                    "close": point.get("close"),
                    "volume": point.get("volume"),
                    "num_events": point.get("numEvents"),
                })
        data = frame(rows, BAR_DATA_SCHEMA)
        if data.height:
            data = data.sort("time_utc")
        return BarResult(data=data, errors=frame(errors, ERROR_SCHEMA))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with BlpapiClient() as bloomberg:
        result = bloomberg.get_reference(
            securities=["SPX Index", "RTY Index", "KRE US Equity"],
            fields=["PX_LAST", "PX_OFFICIAL_CLOSE", "CRNCY", "SECURITY_NAME"],
        )
    print(result.data)
    if result.bulk.height:
        print("bulk:\n", result.bulk)
    if result.errors.height:
        print("errors:\n", result.errors)
