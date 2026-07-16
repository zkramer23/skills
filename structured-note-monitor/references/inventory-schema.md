# Inventory and observation schemas

## Inventory

```json
{
  "portfolio_id": "personal-notes",
  "notes": [
    {
      "note_id": "note-001",
      "position_notional": 100000,
      "currency": "USD",
      "maturity_date": "2028-01-20",
      "payoff_spec": "specs/note-001.json",
      "official_determinations": [
        {
          "date": "2026-07-15",
          "coupon_status": "PAID",
          "coupon_payment": 20,
          "call_status": "NOT_CALLED",
          "source": "calculation-agent statement 2026-07-18"
        }
      ],
      "official_notices": [
        {
          "type": "issuer_call",
          "effective_date": "2027-01-20",
          "source": "issuer notice dated 2027-01-10"
        }
      ]
    }
  ]
}
```

Use either `payoff_spec` or inline `spec`, never both. Paths resolve relative
to the inventory file. The canonical spec follows the
`structured-note-payoff-engine` schema.

`position_notional / spec.notional` is the position multiplier. Official
coupon payments and redemptions are expressed per `spec.notional`; the monitor
adds position-scaled values.

An official determination needs a source. Omit fields the source does not
state; do not convert absence into `NOT_CALLED` or `MISSED`.

## Observations

```json
[
  {
    "note_id": "note-001",
    "date": "2026-07-15",
    "levels": {"SPX Index": 6500.25, "RTY Index": 2450.10},
    "source": "Bloomberg Desktop API PX_OFFICIAL_CLOSE",
    "retrieved_at": "2026-07-16T08:15:00-04:00"
  }
]
```

Each `(note_id, date)` is unique. Level keys must exactly match the canonical
spec's underlier IDs. Record an absent level by omitting it or using null; do
not substitute a prior close. Unknown note IDs are findings.

## Output identity

Every ledger run contains `portfolio_id`, `as_of`, `horizon_days`, note/event
states, findings, and the observation provenance copied into evaluated events.
Persist each run with the as-of date and a content/version identifier in the
consuming project.
