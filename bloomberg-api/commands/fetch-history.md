# history — generate a HistoricalDataRequest

## Purpose
Produce code for daily/weekly/monthly time series — the workhorse for
fixings, observation levels, and barrier monitoring.

## Expected inputs
- Securities (resolve identifiers first — references/identifiers.md)
- Fields (usually `PX_LAST`; add `PX_OFFICIAL_CLOSE` awareness for fixings)
- Date range; periodicity
- **Adjustment intent** — ask if unstated: "compare against historical
  fixed levels?" → unadjusted; "total-return analytics?" → adjusted

## Steps
1. Resolve securities; map display names.
2. Default to **unadjusted + `adjustmentFollowDPDF=False`** for
   structured-product work and say so — silent DPDF dependence is how two
   machines get different numbers.
3. `ACTIVE_DAYS_ONLY` unless the user explicitly wants filled calendars;
   never let fill options fabricate observation-date levels.
4. Generate on the `BlpapiClient.get_history` pattern in
   examples/reference_data.py (examples/historical_data.py shows usage). One
   request for the full range; filter to specific dates locally.

## Output format
`HistoryResult(data, errors)`: a sorted Polars frame
`security | date | <fields…>` plus structured per-security/per-field errors.
Missing security → an error row + absent data rows, never a crash.

## Example
"Closes for the worst-of note's underliers since strike" → one request,
strike date → today, unadjusted `PX_LAST`, then join to the observation
schedule (references/structured-products.md).

## Pitfalls
- One request per date (request the range once)
- Adjusted series against fixed historical barriers
- `PREVIOUS_VALUE` fill silently answering "what was the level on the
  observation date" with a stale close — postponement is a terms question
- Forgetting that each security arrives in its own message (partial handling)
