---
name: structured-note-monitor
description: >-
  Operate a structured-note inventory as of a stated date: combine canonical
  payoff specifications with sourced market observations and official notices,
  evaluate coupon/autocall events, scale cashflows to positions, identify
  unresolved or overdue determinations, and produce upcoming-event calendars
  and auditable event ledgers. Use whenever the user asks what notes observe or
  pay soon, whether notes paid coupons or autocalled, which events need review,
  how an inventory changed, or requests a lifecycle, exception, cashflow, or
  maturity report across one or many structured notes.
argument-hint: "<inventory.json> <observations.json> [--as-of YYYY-MM-DD]"
model: sonnet
context: fork
---

# Structured Note Monitor

Join the existing domain skills into one operational workflow:

```text
prospectus-extraction → structured-note-payoff-engine → structured-note-monitor
                                     ↑                         ↑
                                bloomberg-api levels      notices/determinations
```

The monitor orchestrates these contracts; it does not reinterpret prospectus
language or implement a second payoff engine.

## Workflow

1. **Set an explicit as-of date.** Use the user's timezone and report it. Do
   not let “today” drift across a replay or audit.
2. **Validate inventory identity.** Require stable note IDs, position notional,
   currency, maturity date when known, and either an inline canonical payoff
   spec or a path to one. Read
   [references/inventory-schema.md](references/inventory-schema.md).
3. **Resolve and source observations.** Use the `bloomberg-api` skill for
   market data. Store source and retrieval timestamp with each note/date/level
   set. Never forward-fill an observation date.
4. **Evaluate deterministically.** Run:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/note_monitor.py" \
     inventory.json observations.json --as-of 2026-07-15 --horizon-days 45 \
     --output event-ledger.json
   ```

   The script delegates coupon/autocall math to the sibling
   `structured-note-payoff-engine` skill.
5. **Reconcile official facts.** Prefer calculation-agent determinations and
   issuer notices over indicative market calculations, but retain both and
   surface disagreements. Market performance never proves an issuer-election.
6. **Triage state.** Read [references/event-states.md](references/event-states.md).
   Resolve blockers before presenting a clean active/called/matured status.
7. **Report operations.** Follow
   [references/operations.md](references/operations.md). Present portfolio
   summary, overdue exceptions, upcoming calendar, position cashflows, and
   data-quality findings.

## Hard guards

- Label market-derived coupon/call results `indicative` until officially
  confirmed.
- Never infer an issuer call from an underlier level.
- Never mark a later automatic call definitive when an earlier eligible call
  observation is unresolved.
- Never calculate memory-coupon catch-up after an unresolved coupon observation.
- Never reuse stale observations without an explicit, terms-based disruption
  rule and provenance.
- Preserve corrections as new ledger runs; do not overwrite the historical
  as-of artifact silently.
- Isolate an invalid note as a blocker without losing valid notes in the batch.

## Chat output

Lead with counts: active, called, matured, invalid, unresolved past events, and
events inside the horizon. Then show:

1. blockers and overdue events;
2. the full upcoming observation/payment calendar;
3. official-versus-indicative conflicts;
4. position-scaled coupon/call cashflows;
5. provenance gaps and assumptions.

Include note ID, event date, event state, worst/aggregate performance when
available, coupon status/payment, call status/redemption, source, and basis.
End with “indicative, subject to official determination” whenever any event is
market-derived.
