"""Reference data: the canonical BlpapiClient + a multi-security snapshot.

This module is the ONLY place blpapi is imported. Other examples import
BlpapiClient from here. Requires a logged-in Bloomberg Terminal; everything
above this layer is testable without one (see references/testing.md).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Mapping, Sequence
from uuid import uuid4

import blpapi
import polars as pl

logger = logging.getLogger(__name__)

REFDATA = "//blp/refdata"


class BloombergError(Exception): ...
class BloombergConnectionError(BloombergError): ...
class BloombergTimeoutError(BloombergError): ...
class BloombergRequestError(BloombergError): ...


@dataclass(frozen=True)
class RefResult:
    data: pl.DataFrame     # security | field | value
    errors: pl.DataFrame   # security | field (nullable) | category | message


class BlpapiClient:
    """Thin, session-owning Bloomberg client. Use as a context manager."""

    def __init__(self, host: str = "localhost", port: int = 8194,
                 timeout_ms: int = 30_000) -> None:
        opts = blpapi.SessionOptions()
        opts.setServerHost(host)
        opts.setServerPort(port)
        opts.setAutoRestartOnDisconnection(True)
        self._session = blpapi.Session(opts)
        self._timeout_ms = timeout_ms

    def __enter__(self) -> "BlpapiClient":
        for attempt in range(1, 4):
            if self._session.start() and self._session.openService(REFDATA):
                return self
            logger.warning("Bloomberg start failed (attempt %d/3)", attempt)
            time.sleep(2.0 * 2 ** (attempt - 1))
        raise BloombergConnectionError(
            "Cannot reach Bloomberg on localhost:8194 — is the Terminal running and logged in?")

    def __exit__(self, *exc: object) -> None:
        self._session.stop()

    # -- core event loop (accumulates partials, honors timeout) --------------
    def _collect(self, request: blpapi.Request) -> list[blpapi.Message]:
        cid = blpapi.CorrelationId(uuid4().hex)
        t0 = time.monotonic()
        self._session.sendRequest(request, correlationId=cid)
        messages: list[blpapi.Message] = []
        while True:
            event = self._session.nextEvent(self._timeout_ms)
            if event.eventType() == blpapi.Event.TIMEOUT:
                raise BloombergTimeoutError(f"cid={cid.value()}: no response in {self._timeout_ms}ms")
            for msg in event:
                if not msg.correlationIds() or msg.correlationIds()[0] != cid:
                    continue  # admin traffic
                if msg.hasElement("responseError"):
                    raise BloombergRequestError(f"cid={cid.value()}: {msg.getElement('responseError')}")
                messages.append(msg)
            if event.eventType() == blpapi.Event.RESPONSE:
                logger.info("bbg.request cid=%s ms=%d msgs=%d",
                            cid.value(), (time.monotonic() - t0) * 1000, len(messages))
                return messages

    # -- reference data -------------------------------------------------------
    def get_reference(self, securities: Sequence[str], fields: Sequence[str],
                      overrides: Mapping[str, str] | None = None) -> RefResult:
        service = self._session.getService(REFDATA)
        req = service.createRequest("ReferenceDataRequest")
        for s in securities:
            req.getElement("securities").appendValue(s)
        for f in fields:
            req.getElement("fields").appendValue(f)
        for k, v in (overrides or {}).items():
            o = req.getElement("overrides").appendElement()
            o.setElement("fieldId", k)
            o.setElement("value", v)

        rows: list[dict[str, object]] = []
        errs: list[dict[str, object]] = []
        for msg in self._collect(req):
            sec_data = msg.getElement("securityData")
            for i in range(sec_data.numValues()):
                sd = sec_data.getValueAsElement(i)
                sec = sd.getElementAsString("security")
                if sd.hasElement("securityError"):
                    e = sd.getElement("securityError")
                    errs.append({"security": sec, "field": None,
                                 "category": e.getElementAsString("category"),
                                 "message": e.getElementAsString("message")})
                    continue
                fx = sd.getElement("fieldExceptions")
                for j in range(fx.numValues()):
                    ex = fx.getValueAsElement(j)
                    info = ex.getElement("errorInfo")
                    errs.append({"security": sec,
                                 "field": ex.getElementAsString("fieldId"),
                                 "category": info.getElementAsString("category"),
                                 "message": info.getElementAsString("message")})
                fd = sd.getElement("fieldData")
                for f in fields:
                    if fd.hasElement(f) and not fd.getElement(f).isArray():
                        rows.append({"security": sec, "field": f,
                                     "value": fd.getElement(f).getValueAsString()})
        return RefResult(data=pl.DataFrame(rows), errors=pl.DataFrame(errs))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with BlpapiClient() as bbg:
        result = bbg.get_reference(
            securities=["SPX Index", "RTY Index", "KRE US Equity"],
            fields=["PX_LAST", "PX_OFFICIAL_CLOSE", "CRNCY", "SECURITY_NAME"],
        )
    print(result.data)
    if result.errors.height:
        print("errors:\n", result.errors)
