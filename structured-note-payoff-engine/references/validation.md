# Payoff validation

Validate economics at three layers.

## Specification checks

- Percentages use decimals and levels use raw units.
- Initial levels are positive; identifiers and dates are unique.
- Basket weights sum to one.
- Caps, barriers, buffers, gearing, coupons, and premiums are finite and
  non-negative.
- Automatic calls have at least one trigger; issuer/no-call specs have none.
- Schedule-derived step-downs and step-ups reconcile to stated scalar terms.
- Every modeled mechanic has document evidence or is explicitly labeled
  derived.

## Boundary tests

For each threshold `b`, evaluate `b - ε`, `b`, and `b + ε`, with ε scaled to
the input precision. Always include:

- performance `1.0`;
- downside barrier/buffer edge;
- digital trigger;
- upside cap intersection;
- every schedule coupon barrier and automatic-call trigger;
- zero redemption and maximum redemption, when bounded.

Use the document's inequality. “At or above” means the boundary belongs to the
paying/protected/called region.

## Invariants

- Redemption is never negative.
- A principal-protected terminal payoff is never below par, ignoring issuer
  credit and early sale.
- Worst-of performance is no greater than any constituent performance.
- Basket performance lies within the constituent-performance range when
  weights are non-negative and sum to one.
- A cap never increases payoff.
- Increasing participation cannot reduce an uncapped positive payoff.
- A missing required level never becomes a numeric decision.
- Once an automatic call occurs, later scheduled observations do not exist.
- An unresolved eligible call prevents a definitive later not-called/called
  history until resolved.
- An unresolved memory-coupon observation makes the later accumulated coupon
  amount undetermined.

## Review output

Include the canonical spec, a scenario table, boundary results, unresolved
features, and a plain-language description. Reconcile at least one scenario by
hand against the document's formula before accepting generated code.
