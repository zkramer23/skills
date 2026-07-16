# request — business requirement → optimal Bloomberg request

## Purpose
Translate a business ask ("check if these notes paid their coupons this
month") into the minimal set of correctly-shaped requests plus the local
computation around them.

## Expected inputs
A business requirement in plain English, plus whatever terms data exists
(extraction JSON, note list, schedule).

## Steps
1. **Split data from logic.** What must come from Bloomberg (levels, ratings)
   vs what is already known (barriers, schedules, weights — from the note's
   terms) vs what is computed locally (worst-of, decisions)? Only the first
   group becomes requests.
2. **Pick request types** with the table in references/request-types.md.
   Known-date levels → historical; now-snapshot → reference; bars only for
   intraday forensics.
3. **Minimize request count**: all securities in one request; full date range
   once, filter locally; dedupe securities shared across notes.
4. **Decide adjustment/fill/override settings explicitly** and state why.
5. Emit: the request plan (a short table), then code on the examples/
   patterns, then the local computation (Polars) with lifecycle rules from
   references/structured-products.md.

## Output format
```text
Plan
 1. HistoricalDataRequest — 7 securities, PX_LAST, 2026-01-02→today, unadjusted
 2. (local) join to observation schedules; worst-of; coupon decisions
Requests: 1 · Securities: 7 · Est. data points: ~1,300
```
Then the code.

## Example
"Did any of our 12 phoenix notes autocall this quarter?" → dedupe underliers
(maybe 15 securities) → ONE historical request over the quarter → per-note
autocall scan (guard: automatic mechanics only; an explicit trigger may resolve
a null callType) → summary table CALLED /
NOT CALLED / UNDETERMINED.

## Pitfalls
- Fetching what the terms already state (weights, barriers — never from Bloomberg)
- One request per note when notes share underliers
- Answering an issuer-callable note's "did it call?" from levels
- Quietly choosing adjusted/unadjusted instead of stating the choice
