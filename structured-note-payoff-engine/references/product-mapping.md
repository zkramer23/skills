# Product mechanics mapping

Use this reference to select candidate canonical mechanics, then confirm every
choice against the document's formula and evidence. Product names never
override stated economics.

| Product family | Typical upside | Typical downside | Path features |
|---|---|---|---|
| Accelerated return note | participation, often capped | full, barrier, or buffer | usually none |
| Barrier note | participation, sometimes capped | barrier | sometimes physical settlement |
| Phoenix autocall | participation or par-oriented terminal branch | barrier | contingent coupon; automatic call |
| Contingent-yield note | usually par-oriented above barrier | barrier | contingent coupon; issuer call or no call |
| Snowball autocall | often par plus call premium | barrier | automatic call; premium and/or coupon step-up |
| Market-linked CD | participation, sometimes capped | principal protected | averaging may be off-schema |
| Digital note | digital return or periodic digital coupon | stated protection branch | periodic income possible |
| Dual-directional note | participation above initial | absolute return above downside barrier | usually none |

## Mapping rules

- Map a knock-in/final barrier with contingent principal protection to
  `downside.kind = "barrier"`. The loss below the barrier is normally measured
  from the initial level, not from the barrier.
- Map a hard buffer to `downside.kind = "buffer"`. Confirm whether gearing is
  exactly `1 / (1 - buffer)` or another stated factor; do not derive it unless
  the formula establishes that relationship.
- Map FDIC language separately from payoff protection. Deposit insurance is
  credit protection subject to eligibility and limits, not an upside/downside
  formula input.
- Map worst-of using the minimum constituent performance. Map a defined or
  equal-weight basket using the weighted sum of constituent performances.
- For physical settlement, the engine may calculate economic value, but the
  deliverable quantity and fractional-share cash treatment remain off-schema
  unless explicitly modeled.
- For averaging, lookbacks, daily/American barriers, currency conversion,
  quanto features, or calculation-agent discretion, record an unsupported
  mechanic and do not force the note into a point-to-point formula.

## Autocall distinction

- A printed level that mechanically redeems the note is an automatic call.
- “We may redeem” or “at our election” is issuer-elective. The engine returns
  `ISSUER_ELECTIVE`; it never infers exercise from performance.
- A null call type plus explicit trigger rows requires a documented inference
  before compiling the spec as automatic.
