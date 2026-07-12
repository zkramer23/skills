# Error handling

## Philosophy

Fail **loud and specific at the boundary**, degrade **per-item above it**.
A 40-security batch with 2 unknowns returns 38 rows + 2 structured errors:
never throw away the 38, never hide the 2. Every error carries the
correlation id, the securities/fields involved, and Bloomberg's own message.

## Exception hierarchy

```python
class BloombergError(Exception): ...
class BloombergConnectionError(BloombergError): ...   # can't reach/keep session
class BloombergTimeoutError(BloombergError): ...      # no response in time
class BloombergRequestError(BloombergError): ...      # responseError: bad request/limits
class BloombergEntitlementError(BloombergError): ...  # permissioning
class SecurityNotFoundError(BloombergError): ...      # per-security (only if caller asked for strict mode)
```

Per-security/per-field problems are usually **returned as data**
(an `errors` frame alongside the results), not raised — raising is for
whole-request failures. Offer `strict=True` for callers who want any error
to raise.

## Taxonomy → detection → action

| Class | How it appears | Action |
|---|---|---|
| Terminal down / not logged in | `session.start()` False; `SessionStartupFailure` | fail fast, human hint ("start the Terminal"), no retry loop beyond startup backoff |
| Connection lost mid-flight | `SessionTerminated` / `SessionConnectionDown` | reconnect; re-send in-flight requests once |
| Timeout | `Event.TIMEOUT` from `nextEvent()` | raise `BloombergTimeoutError`; retry once for transport-suspect cases only |
| Malformed request | `responseError` (category `BAD_ARGS`) | raise `BloombergRequestError`; **never retry** — fix the code |
| Daily/monthly limit hit | `responseError` mentioning limits | raise `BloombergRequestError`; **stop the job** — retrying digs the hole deeper |
| Unknown security | `securityData[i].securityError` (e.g. `BAD_SEC`) | per-item error row; check identifier mapping before blaming Bloomberg |
| Invalid/inapplicable field | `fieldExceptions` category `BAD_FLD` | on all securities → coding bug (raise in dev); on some → applicability gap (error rows) |
| Not entitled (field/security/realtime) | `fieldExceptions`/`securityError`/`SUBSCRIPTION_STATUS` failure with permission wording | `BloombergEntitlementError` context; tell the user which entitlement, don't retry |
| Partial response mishandled | symptoms: "only some securities returned" | not an error event — a client bug; accumulate partials |

## Entitlement failures — read them precisely

Permission messages state *what* you lack (a field, an exchange's realtime,
a dataset). Surface Bloomberg's message verbatim plus the security/field, so
the user can raise it with their Bloomberg rep. Common desktop cases:
realtime for non-entitled exchanges (delayed only), restricted datasets
(e.g. some CDS/index data), and third-party data addons.

## Retry matrix

| Failure | Retry? | How |
|---|---|---|
| Session start | yes | 3 attempts, exponential backoff (2s/4s/8s) |
| Timeout | once | after a session health check |
| SessionTerminated mid-request | once | reconnect, re-send |
| responseError BAD_ARGS | no | bug |
| Limit errors | no | stop, report usage |
| securityError / fieldExceptions | no | data, not transport |

Idempotency makes retries safe: requests are read-only, so the only retry
cost is quota — which is why limit errors are the one hard stop.

## Logging standard

One structured line per request and per failure:

```python
logger.info("bbg.request", extra={"cid": cid, "n_sec": len(secs),
            "fields": fields, "ms": elapsed, "n_err": len(errors)})
logger.warning("bbg.security_error", extra={"cid": cid, "security": sec,
               "category": cat, "message": bbg_msg})
```

The `cid` ties your logs to the request that produced them — include it in
every error surfaced to users.
