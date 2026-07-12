# blpapi patterns: events, correlation, partials, subscriptions

## The synchronous request/response loop (canonical form)

Every request-style interaction is this loop. Get it right once, reuse it:

```python
def _collect(self, request: blpapi.Request, timeout_ms: int = 30_000) -> list[blpapi.Message]:
    cid = blpapi.CorrelationId(uuid4().hex)      # explicit, always
    self._session.sendRequest(request, correlationId=cid)

    messages: list[blpapi.Message] = []
    while True:
        event = self._session.nextEvent(timeout_ms)
        if event.eventType() == blpapi.Event.TIMEOUT:
            raise BloombergTimeoutError(f"No response within {timeout_ms}ms")
        for msg in event:
            if not msg.correlationIds() or msg.correlationIds()[0] != cid:
                self._handle_admin(msg)          # session/service status
                continue
            if msg.hasElement("responseError"):  # request-level failure
                raise BloombergRequestError(str(msg.getElement("responseError")))
            messages.append(msg)
        if event.eventType() == blpapi.Event.RESPONSE:   # final event
            return messages
        # PARTIAL_RESPONSE → keep looping and accumulating
```

The three rules encoded there:

1. **Accumulate `PARTIAL_RESPONSE` events.** Large requests stream results
   across several partials before the final `RESPONSE`. Code that parses only
   the first event "randomly" misses securities.
2. **Match on correlation id.** Other traffic (admin events, other requests
   on a shared session) interleaves on the same queue.
3. **Timeout every `nextEvent()`.** Without it, a dead Terminal = a hung
   process.

## Correlation IDs

- Always pass your own (`blpapi.CorrelationId(value)`), never rely on
  auto-assigned ones — you need them for matching, logging, and cancellation.
- Any hashable value works; a UUID string or a monotonically increasing int
  is fine. Log it with every request and error.
- `session.cancel(cid)` abandons an in-flight request.

## Safe element access

blpapi elements throw on missing names. Never chain bare `getElement` calls;
use guarded helpers at the parse boundary:

```python
def opt_str(el: blpapi.Element, name: str) -> str | None:
    return el.getElementAsString(name) if el.hasElement(name) else None

def opt_float(el: blpapi.Element, name: str) -> float | None:
    return el.getElementAsFloat(name) if el.hasElement(name) else None
```

Array elements (`securityData` in reference responses, `fieldData` in
historical ones) iterate with `numValues()` / `getValueAsElement(i)`:

```python
sec_data = msg.getElement("securityData")
for i in range(sec_data.numValues()):
    row = sec_data.getValueAsElement(i)
```

Bulk fields are arrays *inside* `fieldData` — same iteration one level down.

## Response anatomy (ReferenceDataResponse)

```text
message
└── securityData[]                 # array over securities
    ├── security: "SPX Index"
    ├── securityError?             # ← this security failed; others are fine
    ├── fieldExceptions[]          # ← per-field failures for this security
    │   ├── fieldId
    │   └── errorInfo { category, subcategory, message }
    └── fieldData                  # the actual values (scalars + bulk arrays)
```

Parse all three branches. `securityError` and `fieldExceptions` are data,
not exceptions — return them in structured form (see error-handling.md).

## Asynchronous sessions

For long-lived processes and subscriptions, construct the session with an
event handler; blpapi runs it on its own dispatcher thread:

```python
def on_event(event: blpapi.Event, session: blpapi.Session) -> None:
    for msg in event:
        queue.put((event.eventType(), msg))     # hand off; don't do work here

session = blpapi.Session(opts, eventHandler=on_event)
```

Keep the handler tiny (enqueue and return) — heavy work in the handler blocks
the dispatcher. All the request/parse logic stays identical; only delivery
changes.

## Subscriptions (//blp/mktdata)

```python
subs = blpapi.SubscriptionList()
subs.add("SPX Index", "LAST_PRICE,BID,ASK", "interval=2.0", blpapi.CorrelationId("SPX"))
session.subscribe(subs)
```

- Events arrive as `SUBSCRIPTION_STATUS` (started/failed — check for
  entitlement failures here) then a stream of `SUBSCRIPTION_DATA`.
- Ticks are *conflated* by `interval`; omit it for every tick.
- Not every field is subscribable (realtime vs static — see field-guide.md).
- Unsubscribe and stop cleanly on shutdown; leaked subscriptions waste quota.
- For structured-note lifecycle work you almost never need subscriptions —
  observation processing is end-of-day. Reach for them only for live
  dashboards/alerts.

## Threading model summary

| Mode | Delivery | Use for |
|---|---|---|
| Sync (`nextEvent`) | your thread pulls | scripts, batch jobs, request/response |
| Async (handler) | blpapi dispatcher pushes | daemons, subscriptions |

One session per owner. If multiple components need data, share the *client*
(which serializes requests), not the session.
