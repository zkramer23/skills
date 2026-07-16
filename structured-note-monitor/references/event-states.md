# Event and note states

## Event states

| State | Meaning |
|---|---|
| `SCHEDULED` | Future event outside or inside the reporting horizon. |
| `INDICATIVE` | Past/today event calculated from sourced market levels. |
| `OFFICIAL` | Calculation-agent determination supplied and applied. |
| `NOTICE_REQUIRED` | Issuer-elective date passed without an official decision record. |
| `UNRESOLVED` | Required level or prior path state is missing. |
| `CANCELLED_BY_CALL` | A prior automatic or issuer call terminated later events. |
| `OFFICIAL_NOTICE` | Separate issuer-call notice event. |

Timing is separate: `COMPLETED`, `OVERDUE`, `TODAY`, `UPCOMING`, `FUTURE`, or
`CANCELLED`. An unresolved past event is `UNRESOLVED` + `OVERDUE`.

## Note states

| State | Rule |
|---|---|
| `ACTIVE` | No termination/maturity and no unresolved past event. |
| `ACTIVE_WITH_UNRESOLVED_EVENTS` | One or more past events are unresolved or require a notice. |
| `INDICATIVELY_CALLED` | Automatic trigger calculated from market levels but not officially confirmed. |
| `OFFICIALLY_CALLED` | Calculation-agent call determination or issuer notice supplied. |
| `MATURED` | Maturity is on/before as-of with no unresolved past event. |
| `MATURED_WITH_UNRESOLVED_EVENTS` | Maturity passed but lifecycle state remains incomplete. |
| `INVALID` | Identity/spec/input prevents safe evaluation. |

Official state wins presentation priority, but the ledger retains the
indicative result and emits a conflict finding when they disagree.

## State propagation

- Missing memory-coupon observation → later accumulated coupon amount remains
  unresolved until corrected.
- Missing eligible automatic-call observation → later call state remains
  unresolved until corrected.
- Definitive call → all later schedule rows become `CANCELLED_BY_CALL`.
- Issuer-election without notice → never convert to automatic or not-called.
