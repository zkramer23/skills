# mock — generate realistic mocked Bloomberg responses for tests

## Purpose
Produce test doubles and fixture data shaped exactly like the real client's
output, so business logic tests run with no Terminal
(references/testing.md).

## Expected inputs
- Which provider methods the code under test calls (`get_reference`,
  `get_history`, …) and which typed result each returns
- The scenario: happy path, missing security, field exception, disruption
  day, barrier-edge values

## Steps
1. Mock at the **`MarketDataProvider` boundary** (typed frames), not at the
   blpapi message level — unless the code under test IS the parser, in which
   case use recorded raw fixtures.
2. Make numbers **internally consistent**: closes near initial levels;
   worst-of scenarios where the intended underlier is actually worst; dates
   that are real weekdays aligned to the observation schedule.
3. Always include every result frame — including empty `bulk`/`errors` frames
   with their real schema — so tests exercise the actual contract.
4. For barrier tests, generate the tell-tale triple: clearly above, clearly
   below, and **exactly at** the barrier (the `>=` case).
5. Realistic imperfections on request: a missing date (holiday), one
   underlier absent (tests the "partial basket = undetermined" rule), a
   `BAD_FLD` row.

## Output format
Pytest-ready code: a `MockProvider` class or fixture returning Polars frames,
plus the scenario table as literals. Column names/types must match the real
client exactly (`security | date | PX_LAST`, `RefResult(data, bulk, errors)`,
`HistoryResult(data, errors)`).

## Example
"Mock a phoenix note that misses two coupons then pays with memory" →
history fixture with worst-of below barrier on obs 1–2, above on obs 3 →
assert obs-3 amount == 3 × coupon_per_period.

## Pitfalls
- Fixture frames that drift from the client's real schema (type-check mocks
  against the Protocol)
- Random data where the scenario needs engineered relationships
- Only happy-path mocks — the error frame paths are where production breaks
- Bulk-history dumps as fixtures (licensing; keep fixtures minimal)
