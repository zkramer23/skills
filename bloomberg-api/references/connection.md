# Connection, session lifecycle, and services

## Architecture

The **Desktop API (DAPI)** is a localhost bridge into a running, logged-in
Bloomberg Terminal:

```text
your process ──TCP localhost:8194──▶ bbcomm (Terminal runtime) ──▶ Bloomberg
```

- The Terminal must be running and logged in on the **same machine**.
- Authentication is implicit — you inherit the terminal user's identity and
  entitlements. There is no API key.
- If code must run on a server (scheduler, web app, CI), DAPI is the wrong
  product: that's **SAPI** (Server API) or **B-PIPE**, which add explicit
  authorization (`//blp/apiauth`, identities, app names) and a different
  license. Design the `MarketDataProvider` interface so this swap is a new
  implementation, not a rewrite.

## Session lifecycle

```python
import blpapi

opts = blpapi.SessionOptions()
opts.setServerHost("localhost")
opts.setServerPort(8194)
opts.setAutoRestartOnDisconnection(True)

session = blpapi.Session(opts)
if not session.start():
    raise BloombergConnectionError(
        "Cannot reach the Bloomberg Terminal on localhost:8194 — "
        "is the Terminal running and logged in?"
    )
if not session.openService("//blp/refdata"):
    session.stop()
    raise BloombergConnectionError("Failed to open //blp/refdata")
service = session.getService("//blp/refdata")
```

Wrap this in a context manager so `stop()` is guaranteed:

```python
class BlpapiClient:
    def __enter__(self) -> "BlpapiClient":
        self._start()          # start + openService, with retries
        return self

    def __exit__(self, *exc) -> None:
        self._session.stop()   # graceful: flushes pending events
```

## Services

| Service | Purpose |
|---|---|
| `//blp/refdata` | Reference, historical, intraday requests (the workhorse) |
| `//blp/mktdata` | Real-time subscriptions |
| `//blp/apiauth` | Authorization (SAPI/B-PIPE only — not used on DAPI) |
| `//blp/instruments` | Security lookup / search |

Open a service once per session and reuse it. `openService` is synchronous
and returns a bool; the async variant (`openServiceAsync`) reports via
`SERVICE_STATUS` events.

## Session status events

Even in synchronous use, the event loop can deliver admin events. Handle at
minimum:

| Event | Message | Meaning / action |
|---|---|---|
| `SESSION_STATUS` | `SessionStarted` | OK |
| `SESSION_STATUS` | `SessionStartupFailure` | Terminal down/not logged in — fail with the human-readable hint |
| `SESSION_STATUS` | `SessionTerminated` | Connection lost mid-flight — in-flight requests are dead; reconnect and re-send |
| `SESSION_STATUS` | `SessionConnectionUp/Down` | Transient transport state — log it |
| `SERVICE_STATUS` | `ServiceOpenFailure` | Wrong service name or entitlement problem |

## Retries

Retry **connection establishment**, not business requests, blindly:

```python
def _start(self, attempts: int = 3, base_delay: float = 2.0) -> None:
    for attempt in range(1, attempts + 1):
        session = self._new_session()  # a Session may only be started once
        if session.start():
            if session.openService(REFDATA):
                self._session = session
                return
            session.stop()
        if attempt < attempts:
            logger.warning("Bloomberg start failed (attempt %d/%d)", attempt, attempts)
            time.sleep(base_delay * 2 ** (attempt - 1))   # 2s, then 4s
    raise BloombergConnectionError(...)
```

- Transport failures (session died, timeout with no response): retry the
  request once after reconnecting.
- Request-level errors (bad security, bad field, entitlement, limits):
  **never** retry — the answer won't change and limit errors get worse.
- `setAutoRestartOnDisconnection(True)` lets blpapi heal brief drops, but
  requests in flight during the drop still fail — your code re-sends.

## Graceful shutdown

- `session.stop()` blocks until the session is down; call it in `finally`.
- For async sessions, `stop()` after draining the event queue; killing the
  process with events pending can lose responses but harms nothing server-side.
- Never share one session across threads without external locking; simplest
  rule — one session per thread, or a single dispatching owner thread.

## Startup health check

Expose a `ping()` on the client — a 1-security, 1-field
ReferenceDataRequest (`SPX Index` / `PX_LAST`) with a short timeout. Run it at
composition time so a dead Terminal fails the job in seconds with a clear
message, not 40 minutes in.
