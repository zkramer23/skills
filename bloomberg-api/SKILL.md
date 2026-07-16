---
name: bloomberg-api
description: >-
  Design, write, review, and troubleshoot Bloomberg API (blpapi) integrations
  for a structured-products platform. Use this whenever the task touches
  Bloomberg in any form: blpapi code, Desktop API / Terminal data, BDP/BDH/BDS
  equivalents, reference or historical or intraday market data, subscriptions,
  field selection (PX_LAST vs PX_OFFICIAL_CLOSE), security identifiers
  (ticker/CUSIP/ISIN/SEDOL/FIGI), entitlement or "permission denied" errors,
  mocking Bloomberg for tests, or market-data workflows for structured notes —
  fixings, observation levels, worst-of calculations, coupon/autocall checks,
  basket pricing, issuer lookups. Trigger even when the user just says "pull
  prices from Bloomberg", "check if this note autocalled", or pastes a blpapi
  stack trace.
argument-hint: "<reference|history|fields|request|troubleshoot|mock> [details]"
model: sonnet
---

# Bloomberg API for Structured Products

Internal engineering guide for building Bloomberg Desktop API (blpapi)
integrations that are testable, entitlement-aware, and correct for
structured-note lifecycle work. The goal: every session produces the same
architecture — a thin, replaceable Bloomberg client behind an interface, with
business logic that never imports `blpapi`.

## When this skill is active

Any Bloomberg-touching work: writing or reviewing blpapi code, choosing
request types or fields, mapping identifiers, diagnosing errors, building
tests without a Terminal, or computing structured-product lifecycle events
from market data. For prospectus/term extraction itself, defer to the
`prospectus-extraction` skill — this skill consumes its output (underliers,
barriers, schedules) and prices/monitors against Bloomberg.

When invoked explicitly, interpret the first word of `$ARGUMENTS` as the task
route (`reference`, `history`, `fields`, `request`, `troubleshoot`, or `mock`)
and the remaining text as the task inputs. If no route is supplied, infer it
from the request. The supported explicit form is `/bloomberg-api <route> ...`;
the files under `commands/` are supporting playbooks, not independently
registered slash commands.

## Architecture (non-negotiable shape)

```text
┌────────────────────────┐     ┌──────────────────────────┐
│ business logic          │     │ tests                     │
│ (lifecycle, worst-of,   │────▶│ MockBloombergClient       │
│  coupons, reports)      │     │ (fixtures / replay)       │
└──────────┬─────────────┘     └──────────────────────────┘
           │ depends on
           ▼
┌────────────────────────┐
│ MarketDataProvider      │  ← Protocol: get_reference(), get_history(), …
│ (typed interface)       │
└──────────┬─────────────┘
           │ implemented by
           ▼
┌────────────────────────┐
│ BlpapiClient            │  ← ONLY module that imports blpapi
│ (session, events,       │
│  parsing, retries)      │
└────────────────────────┘
```

Rules that follow from the shape:

- **One module imports `blpapi`.** Everything else takes a
  `MarketDataProvider` by constructor injection. This is what makes offline
  tests, replay fixtures, and a future B-PIPE/vendor swap possible.
- **The client returns typed data (Polars DataFrames or dataclasses), never
  raw blpapi messages.** Parsing happens once, at the boundary.
- **No globals, no module-level sessions.** Sessions are context managers
  owned by the composition root.

## Session lifecycle (the 7 steps every request follows)

1. `SessionOptions` → host `localhost`, port `8194` (Desktop API; Terminal
   must be logged in on the same machine).
2. `session.start()` — fail fast with a clear message if the Terminal is down.
3. `session.openService("//blp/refdata")` (or `//blp/mktdata` for subs).
4. Build request; send with an explicit `CorrelationId`.
5. Event loop: consume `PARTIAL_RESPONSE` events (accumulate!) until the
   final `RESPONSE` event; honor a timeout.
6. Parse per-security: handle `securityError` and `fieldExceptions`
   explicitly — they arrive inside otherwise-successful responses.
7. `session.stop()` in a `finally`/context manager — always.

Details, retries, and async patterns: [references/connection.md](references/connection.md)
and [references/blpapi-patterns.md](references/blpapi-patterns.md).

## Best-practices checklist

Before shipping any Bloomberg code, verify:

- [ ] `blpapi` imported in exactly one module; business logic tested against a mock
- [ ] Batched requests (many securities/fields per request), never per-security loops
- [ ] `PARTIAL_RESPONSE` accumulated — a large request that "returns half the
      securities" is almost always a dropped partial
- [ ] `securityError` and `fieldExceptions` surfaced per security/field, not swallowed
- [ ] Fixings use `PX_OFFICIAL_CLOSE` semantics, unadjusted — see
      [references/structured-products.md](references/structured-products.md)
- [ ] Identifiers follow the hierarchy in [references/identifiers.md](references/identifiers.md);
      display names from prospectuses are mapped, never sent raw
- [ ] Results cached (content-addressed by request) so reruns don't burn entitlement quota
- [ ] Every request logged: securities count, fields, correlation id, duration, errors
- [ ] Timeout on every `nextEvent()`; retries only for transport-class failures

## Coding standards

Python 3.12+, full type hints, `pathlib`, stdlib `logging` (module-level
`logger = logging.getLogger(__name__)`), `pytest`, `ruff`. **Polars** for
tabular data; Pandas only at an edge where a consumer demands it. Dataclasses
(frozen where possible) for domain types. Custom exception hierarchy rooted at
`BloombergError` — see [references/error-handling.md](references/error-handling.md).
Dependency injection over globals or singletons; the composition root wires
`BlpapiClient` in, tests wire mocks in.

## Common mistakes (each has caused a real incident somewhere)

1. **Dropping partial responses** — processing only the first event and
   missing later securities.
2. **Treating `RESPONSE` as success** — per-security `securityError` and
   per-field `fieldExceptions` live inside successful responses.
3. **`PX_LAST` for fixings** — last trade ≠ official close; notes fix on the
   official close, and the calculation agent's fixing is contractual anyway
   (Bloomberg levels are indicative).
4. **Adjusted history for barrier checks** — split/dividend-adjusted closes
   rewrite the past; a barrier struck against the original initial level must
   use unadjusted data unless the note's terms adjust too.
5. **Sending display names as tickers** — "Russell 2000 Index" is not
   `RTY Index`; prospectus underlier names need explicit mapping.
6. **Per-security request loops** — 50 requests for 50 securities burns quota
   and time; one request takes them all.
7. **Claiming an issuer-callable note "autocalled" from a level** — only
   trigger-automatic calls are provable from market data (see
   structured-products reference; this mirrors the phoenix vs CYN taxonomy).
8. **No timeout on the event loop** — a dead Terminal hangs the process forever.
9. **Zombie sessions** — no `stop()` on the error path; use context managers.

## Bloomberg limitations to design around

- **Desktop API is desktop-only**: requires a logged-in Terminal on the same
  machine, licensed to that user. It will not run headless on a server, in CI,
  or in a container. Server-side needs SAPI/B-PIPE (different contract).
- **Usage limits are real but unpublished**: daily hit limits and monthly
  unique-security caps exist per terminal. Batch, cache, and log usage;
  a `responseError` mentioning limits means stop and back off, not retry.
- **One security per intraday request**; intraday tick history is limited to
  ~140 days.
- **Field coverage varies by asset class** — validate fields with FLDS on the
  Terminal before coding them in; see [references/field-guide.md](references/field-guide.md).
- **BQL is not part of the public desktop blpapi SDK** — see
  [references/bql.md](references/bql.md) before promising BQL features.

## Data licensing

Desktop API data is licensed for the terminal user's own use. Do not
redistribute it, serve it to other users, or feed shared systems/databases
without checking the firm's Bloomberg agreement — "it's just a cache" has
failed audits. Persist derived results (a coupon decision, a worst-of flag)
rather than raw quote history where possible, and label stored levels as
indicative, not official fixings.

## Performance

Batch securities and fields per request (start conservative: ≤100 securities,
≤25 fields; split beyond that). Prefer one `HistoricalDataRequest` over many
reference snapshots when you need a date range. Cache immutable history
(closed trading days never change — adjusted history does; cache unadjusted).
Reuse one session for a batch of requests; don't start/stop per request.
Subscriptions only for genuinely-live needs — lifecycle monitoring is
end-of-day work.

## Error-handling philosophy

Fail **loud and specific** at the boundary, degrade **gracefully and
per-item** above it. A batch of 40 securities with 2 unknowns returns 38 rows
plus 2 structured errors — never an exception that loses the 38, never a
silent 38 that hides the 2. Full taxonomy, retry matrix, and exception
hierarchy: [references/error-handling.md](references/error-handling.md).

## Task playbooks (commands/)

Route explicit `/bloomberg-api <route> ...` requests and equivalent natural
language to the matching playbook:

| Route | Playbook |
|---|---|
| `reference` — snapshot fields for securities | [commands/fetch-reference.md](commands/fetch-reference.md) |
| `history` — time series | [commands/fetch-history.md](commands/fetch-history.md) |
| `fields` — sanity-check field mnemonics | [commands/validate-fields.md](commands/validate-fields.md) |
| `request` — business requirement → optimal request | [commands/build-request.md](commands/build-request.md) |
| `troubleshoot` — diagnose a blpapi error/trace | [commands/troubleshoot.md](commands/troubleshoot.md) |
| `mock` — realistic mocked responses for tests | [commands/mock-data.md](commands/mock-data.md) |

## Reference map

| Topic | File |
|---|---|
| Session, services, auth, retries, shutdown | [references/connection.md](references/connection.md) |
| Event loops, correlation ids, partials, subscriptions | [references/blpapi-patterns.md](references/blpapi-patterns.md) |
| Request types & when to use each | [references/request-types.md](references/request-types.md) |
| Fields, bulk fields, overrides, exceptions | [references/field-guide.md](references/field-guide.md) |
| Identifiers & preferred hierarchy | [references/identifiers.md](references/identifiers.md) |
| BQL — what it is and isn't | [references/bql.md](references/bql.md) |
| Error taxonomy, retries, exceptions | [references/error-handling.md](references/error-handling.md) |
| Testing without a Terminal | [references/testing.md](references/testing.md) |
| Structured-product workflows | [references/structured-products.md](references/structured-products.md) |

Runnable patterns live in `examples/` — start from
[examples/reference_data.py](examples/reference_data.py), which defines the
`BlpapiClient` the other examples build on.
