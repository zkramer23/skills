# Monitoring operations

## Daily/as-of run

1. Freeze inventory and canonical spec versions.
2. Select events through the as-of date plus the reporting horizon.
3. Batch required identifiers/dates through the `bloomberg-api` provider.
4. Persist raw request metadata subject to licensing; prefer derived event
   records over broad quote-history storage.
5. Run the monitor with an explicit as-of date.
6. Resolve blockers, then distribute the summary with an indicative label.
7. Add official notices/determinations when received and rerun; retain both
   versions for audit.

## Exception priority

1. Invalid or ambiguous note/security identity.
2. Past automatic-call observation unresolved.
3. Past memory-coupon observation unresolved.
4. Official-versus-indicative conflict.
5. Maturity passed without final determination.
6. Missing market-data provenance.
7. Future schedule or payment-date inconsistency.

## Idempotence and corrections

Key event rows by portfolio, note ID, schedule date, event type, and run as-of.
The same frozen inputs must produce the same ledger. Corrections create a new
run/version linked to the superseded one; never mutate an already distributed
historical result without a correction record.

## Cashflow reporting

- Keep per-denomination and position-scaled amounts separate.
- Do not add an indicative call redemption to settled cash until confirmed.
- Coupon payment dates can differ from observation dates; show both when the
  canonical schedule supplies `payment_date`.
- Keep currency explicit and never aggregate across currencies without a named
  FX source/date.

## Licensing and authority

Bloomberg observations are licensed and indicative. Calculation-agent
statements and issuer notices establish contractual outcomes. Store the source
identifier/date for every official fact and apply access/retention policy in
the consuming project.
