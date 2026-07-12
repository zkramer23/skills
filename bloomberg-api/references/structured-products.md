# Structured-product workflows on Bloomberg data

The workflows below consume terms extracted from offering documents (see the
`prospectus-extraction` skill: underliers, initial levels, barriers as
fractions of initial, observation schedules) and price/monitor them with
Bloomberg data. Two ground rules repeat throughout:

1. **Bloomberg levels are indicative.** The contractual fixing is the
   calculation agent's determination. Label every computed lifecycle event
   "indicative, subject to official determination" — especially near
   barriers.
2. **A market level can prove a trigger-automatic call, never an
   issuer-elective one.** Phoenix autocalls are checkable from data;
   issuer-callable CYNs are not — their redemption is a fact you learn from
   a notice, not a level. Guard every autocall routine with this check.

## Identifier step (always first)

Map prospectus display names → Bloomberg tickers via the table in
identifiers.md; resolve stocks via `/isin/` or `/cusip/` from the document.
Unknown name → stop and ask. Store the resolved ticker alongside the note.

## Initial fixing (strike)

`HistoricalDataRequest`, `PX_OFFICIAL_CLOSE` (fallback `PX_LAST` if the
security has no official close), **unadjusted**, single-day range on the
strike date (the `strikeDate` field — which may differ from the trade date).
Cross-check against the prospectus's printed initial levels: a mismatch
usually means wrong ticker (price vs TR index, venue), wrong date
(trade vs strike), or an averaging-in strike.

## Observation levels

One `HistoricalDataRequest` per note covering strike → today (unadjusted,
`ACTIVE_DAYS_ONLY`), then join to the observation schedule locally:

```python
obs = schedule.join(history, left_on=["security", "observation_date"],
                    right_on=["security", "date"], how="left")
```

A null after the join = no close on that date (holiday/disruption). Do NOT
auto-fill with the previous close — the note's terms define postponement
(typically next scheduled trading day per underlier, with cutoffs). Surface
nulls as "needs postponement handling" findings.

## Worst performer

Per observation date: `perf_i = close_i / initial_i`; worst = min over
underliers. Undefined if ANY underlier lacks a level that day. Store the
worst performer's identity, not just the value — reports need "KRE was worst
at 0.62".

## Coupon determination (phoenix / CYN)

Coupon pays iff worst performance ≥ `couponBarrier` (fraction-of-initial from
the extraction; use the document's own inequality — "at or above" = `>=`).
**Memory coupon**: if `memoryCoupon` is true, a paying observation also pays
all previously missed coupons; track `missed_count` through the schedule in
order. Emit one row per observation: date, worst perf, barrier, paid?,
amount, cumulative missed.

## Autocall determination

Only when `callType == "automatic"` (extraction taxonomy: issuer-elective
notes are `contingent_yield_note` — for those, record "callable by issuer;
not determinable from market data"). For automatic calls: on each observation
date on/after the first call date, called iff worst performance ≥ that date's
autocall level (per-row levels from the schedule handle step-downs). Once
called, the note is dead: no further coupons/observations — stop the scan.

## Maturity redemption

At final valuation: if worst ≥ knock-in/protection threshold → par (plus any
final coupon per terms); else loss per the note's downside formula (1:1 from
initial for knock-in structures; buffered structures lose only beyond the
buffer). Compute from the extraction's `knockInLevel`/`protectionLevel` and
the document's stated formula — don't hardcode one payoff shape.

## Basket notes

Note baskets are defined **in the document** (constituents + weights from the
`underliers` table of the extraction), not by Bloomberg membership — never
fetch `INDX_MEMBERS` for a note basket. Basket level per date:
`Σ weight_i × (close_i / initial_i)` (defined or equal weights). Barriers for
basket notes apply at the **basket** level. `INDX_MEMBERS`/`INDX_MWEIGHT` are
for actual indices (analytics on an underlier), not note baskets.

## Issuer lookup

`ReferenceDataRequest` on the issuer's equity or the note's `Corp` ticker:
`ISSUER`, `ULT_PARENT_TICKER_EXCHANGE`, `RTG_MOODY`, `RTG_SP`, `RTG_FITCH`,
`COUNTRY_ISO`. Feed approved-issuer checks with the ultimate parent, not the
issuing shell (MSFL is guaranteed by Morgan Stanley; the rating that matters
is the guarantor's).

## Corporate actions

For share-linked notes, dividends/splits interact with the note's own
adjustment clauses. Pull `DVD_HIST_ALL` (bounded by `DVD_START_DT`/`DVD_END_DT`
overrides) to review what happened; whether the note's initial level/barriers
adjust is a **terms** question (the calculation agent adjusts per the
prospectus), not a data toggle. Index-linked notes: the index provider
handles constituent actions — no adjustment on your side.

## Historical observations / backfill

Rebuilding a note's life to date = the coupon + autocall scans above over the
full schedule, in date order, with the called-stops-everything rule. Persist
the derived event table (per observation: levels, worst, decisions) keyed by
note id + schedule row — that's the auditable artifact, and it means
re-pricing doesn't re-burn Bloomberg quota.
