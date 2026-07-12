# Testing without a Bloomberg Terminal

The Desktop API needs a logged-in Terminal on the developer's machine — CI
has none, and half your dev loop shouldn't need one either. The architecture
already solves this: business logic depends on a `MarketDataProvider`
Protocol, so tests inject fakes.

## The interface

```python
class MarketDataProvider(Protocol):
    def get_reference(self, securities: Sequence[str], fields: Sequence[str],
                      overrides: Mapping[str, str] | None = None) -> RefResult: ...
    def get_history(self, securities: Sequence[str], fields: Sequence[str],
                    start: date, end: date, *, adjusted: bool = False) -> pl.DataFrame: ...
```

`RefResult` = `(data: pl.DataFrame, errors: pl.DataFrame)` — errors are data
(see error-handling.md), so mocks can exercise error paths without patching.

## Three tiers of test doubles

1. **Hand-built mock** — for unit tests of logic. Return small literal frames:

```python
class MockProvider:
    def __init__(self, history: pl.DataFrame): self._h = history
    def get_history(self, securities, fields, start, end, *, adjusted=False):
        return self._h.filter(pl.col("security").is_in(list(securities)))
```

2. **Recorded fixtures (replay)** — for parser and workflow tests. Once, on a
   Terminal machine, run the real client with `record=True`: every response
   is serialized (request signature → parquet in `tests/fixtures/bbg/`).
   `ReplayProvider` loads by signature and fails on a miss, so tests are
   deterministic and Terminal-free. Re-record deliberately; fixtures are
   checked in (mind licensing: keep fixtures minimal — a handful of
   securities/dates, not bulk history dumps).

3. **Live integration tests** — a thin marker-gated suite that runs only on a
   Terminal machine:

```python
bloomberg = pytest.mark.skipif(not terminal_available(), reason="needs Bloomberg Terminal")

@bloomberg
def test_spx_reference_roundtrip(live_client): ...
```

`terminal_available()` = can TCP-connect to `localhost:8194` quickly. CI runs
tiers 1–2 always; tier 3 never.

## What to test at each layer

| Layer | Tests | Double |
|---|---|---|
| blpapi parsing (`BlpapiClient._parse_*`) | response anatomy → frames; securityError/fieldExceptions extraction | recorded raw fixtures |
| lifecycle math (worst-of, coupons, autocall) | pure functions — table-driven cases incl. boundary (level == barrier exactly) | none needed if pure |
| workflows (observation processing) | end-to-end over replay data | ReplayProvider |
| error behavior | unknown security, entitlement denial, timeout | mock raising/returning errors |

Keep lifecycle math **pure** (levels in → decisions out, no provider calls
inside) — then the interesting logic needs no doubles at all, and
property-style tests are easy (e.g. worst-of return ≤ every constituent
return; memory-coupon payout count ≤ missed periods + 1).

## Boundary cases that must have tests

- Level exactly **at** the barrier (prospectuses say "at or above" — `>=`,
  not `>`; encode the document's own words in the test name).
- Observation date is a holiday → previous close must NOT be silently used
  (the note's terms say what happens; the data layer must not paper over it).
- One underlier of a worst-of missing data for the date → the whole
  observation is undetermined, not "worst of the ones we have".
- Security unknown / renamed ticker → error row present, other securities
  unaffected.
- GBp-quoted constituent in a mixed basket → normalization applied.

## pytest layout

```text
tests/
├── unit/                 # pure logic + parsers (fixtures)
├── workflows/            # replay-driven end-to-end
├── live/                 # @bloomberg-marked, Terminal only
└── fixtures/bbg/         # recorded parquet responses + index.json
```

`ruff` + full type hints on tests too — mocks conforming to the Protocol are
type-checked, which catches interface drift the moment `MarketDataProvider`
changes.
