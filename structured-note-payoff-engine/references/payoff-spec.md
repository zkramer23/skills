# Canonical payoff specification

## Contents

- [Example](#example)
- [Required core fields](#required-core-fields)
- [Upside mechanics](#upside-mechanics)
- [Downside mechanics](#downside-mechanics)
- [Income, call, and schedule](#income-call-and-schedule)
- [Observation input](#observation-input)

Use schema version `1`. Percentages are decimals: 70% is `0.70`; performance
is final level divided by initial level; return is performance minus one.

## Example

```json
{
  "schema_version": 1,
  "note_id": "example-note",
  "product_type": "barrier_note",
  "notional": 1000,
  "underlier_structure": "worst_of",
  "underliers": [
    {"id": "SPX Index", "initial_level": 6000, "weight": null},
    {"id": "RTY Index", "initial_level": 2200, "weight": null}
  ],
  "terminal": {
    "upside": {
      "kind": "participation",
      "participation_rate": 1.0,
      "cap": null,
      "digital_trigger": null,
      "digital_return": null
    },
    "downside": {
      "kind": "barrier",
      "barrier": 0.70,
      "buffer": null,
      "gearing": 1.0
    }
  },
  "income": {
    "coupon_barrier": 0.70,
    "coupon_per_period": 0.02,
    "memory": false
  },
  "call": {"type": "automatic"},
  "schedule": [
    {
      "date": "2027-01-15",
      "coupon_barrier": 0.70,
      "coupon_amount": 0.02,
      "call_trigger": 1.00,
      "call_premium": 0.00
    }
  ]
}
```

## Required core fields

- `schema_version`: exactly `1`.
- `note_id`: stable non-empty identifier.
- `product_type`: extraction taxonomy value; descriptive, not a formula switch.
- `notional`: positive finite amount.
- `underlier_structure`: `single`, `worst_of`, `best_of`,
  `basket_equal_weight`, or `basket_defined_weight`.
- `underliers`: unique identifiers and positive initial levels. Basket weights
  must be finite, non-negative, and sum to one; non-baskets use null weights.
- `terminal`: explicit upside and downside mechanics.

## Upside mechanics

`kind` is one of:

- `participation`: positive return is `participation_rate × (performance - 1)`.
- `digital`: pay `digital_return` when performance is at or above
  `digital_trigger`; otherwise evaluate the downside branch.

`cap` is the maximum positive note return, not a maximum underlier level. Use
null only when the document explicitly has no cap.

## Downside mechanics

`kind` is one of:

- `full`: participate in negative performance at `gearing`.
- `barrier`: return zero while performance is at or above `barrier`; below it,
  participate in the full underlier decline at `gearing`.
- `buffer`: absorb the first `buffer` of decline, then lose
  `gearing × excess decline`.
- `principal_protected`: terminal downside return is zero.
- `absolute_return`: while performance is at or above `barrier`, convert the
  decline into a positive return using the upside participation/cap; below the
  barrier, apply full negative performance at `gearing`.

The engine floors redemption at zero. That is a calculation guard, not a
statement about issuer credit or deposit-insurance recovery.

## Income, call, and schedule

Omit `income`, `call`, and `schedule` only when the note has no periodic
feature. Otherwise:

- `income.coupon_barrier`, `coupon_per_period`, and `memory` define defaults.
  A schedule row may override barrier and amount.
- `call.type` is `automatic`, `issuer`, or `none`.
- Each schedule date is unique ISO `YYYY-MM-DD`.
- `call_trigger` is permitted only for automatic calls. Null means the row is
  inside the non-call period.
- `call_premium` is return over par, not a dollar amount.

## Observation input

The `path` command accepts:

```json
[
  {"date": "2027-01-15", "levels": {"SPX Index": 6100, "RTY Index": 2100}}
]
```

Missing dates or underlier levels remain unresolved. Do not substitute a prior
close in this file.

The path API and CLI optionally accept official determinations keyed by
schedule date. A `PAID` determination resets memory state; a `MISSED`
determination should include `missed_count` when an earlier memory state was
unknown. Official `NOT_CALLED` proves the note survived that date and lets the
later automatic-call path continue. Preserve a separately calculated raw
indicative path when reconciling disagreements.
