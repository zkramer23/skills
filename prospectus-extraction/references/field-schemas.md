# Product types and field schemas

Ported from the payout-grapher extraction pipeline
(`~/dev/payout-grapher/server/src/prospectus/schemas.ts` + `classify.ts`).
The schema is developer-controlled and closed: extract exactly these fields for
the classified type, nothing else. **Material** fields are marked — a missing
or evidence-free material field is a headline warning.

This skill's schema extends the repo's in three places it lacks: the
`strikeDate` and `underlierStructure` fields, and the `contingent_yield_note`
product type (no-call contingent-coupon notes, which the repo folds into
phoenix). If importing results back into payout-grapher, expect the two
fields to land in `unmappedFields` and map `contingent_yield_note` to
`phoenix_autocall` with null call fields.

## Classification keywords

Distinguishing phrases (case-insensitive) to scan for in the first ~6 pages.
Score by how many distinct signals hit; classify by mechanics when brands
collide.

| Product type | Signals |
|---|---|
| `accelerated_return_note` | accelerated return, leveraged upside, upside leverage factor, participation rate, enhanced growth |
| `barrier_note` | downside threshold, knock-in, barrier level, european barrier, trigger level |
| `snowball_autocall` | snowball, step-down / stepdown, memory coupon (with call premium accruing to call date) |
| `phoenix_autocall` | phoenix, contingent coupon, contingent yield, contingent income, trigger callable, autocallable / auto-callable, coupon barrier — **and a call feature exists** |
| `contingent_yield_note` | same contingent coupon/yield/income + barrier language, but **no call or early-redemption feature anywhere in the document** |
| `mlcd` | market-linked CD, market linked certificate, certificate of deposit, FDIC |
| `digital_income` | digital coupon, digital return, fixed coupon, digital note |
| `dual_directional` | dual directional, dual-directional, absolute return |

**Coupon-note family decision rule** — contingent-coupon language identifies
the family; the **call mechanism** picks the type:

- automatic trigger call ("will be automatically called/redeemed if…") →
  `phoenix_autocall`
- issuer-elective call ("we may, at our election, redeem", "callable at our
  option") → `phoenix_autocall` with `callType: "issuer"`
- **no call or early-redemption feature at all** → `contingent_yield_note`.
  Don't force a no-call note into phoenix and then report a "missing"
  autocall trigger — the trigger isn't missing, it doesn't exist, and the
  note's risk profile (guaranteed to run to maturity) is different.

Dealer-brand hints: UBS "Trigger **Callable** Contingent Yield Notes" and
Morgan Stanley "Contingent Income Auto-Callable Securities" are phoenix
autocalls (UBS CYNs typically **issuer-election** calls, not automatic —
check the call language, not the brand). A UBS "Trigger Yield Note" or any
contingent-coupon note whose document has no call section is a
`contingent_yield_note`.

## Common fields (every product type)

| Field | Unit | Group | Material |
|---|---|---|---|
| `issuer` | text | identity | ✅ |
| `underlier` | text | identity | ✅ |
| `underlierStructure` (`single` / `worst_of` / `best_of` / `basket_equal_weight` / `basket_defined_weight`) | text | identity | ✅ |
| `cusip` (CUSIP / ISIN) | text | identity | |
| `payoutType` (growth/yield) | text | identity | |
| `initialLevel` | level | economics | |
| `tradeDate` (trade date — when terms are priced and the note is sold) | date | dates | |
| `strikeDate` (strike / initial determination date — when the underliers' initial levels are observed) | date | dates | |
| `settlementDate` | date | dates | |
| `finalObservationDate` | date | dates | |
| `maturityDate` | date | dates | |
| `termMonths` | months | dates | |
| `denomination` | usd | economics | ✅ |
| `salesCommission` | percent | fees | |
| `dealerConcession` | percent | fees | |
| `structuringFee` | percent | fees | |
| `estimatedInitialValue` | percent | fees | |

## Product-specific fields

### accelerated_return_note
| Field | Unit | Material |
|---|---|---|
| `participationRate` | percent | ✅ |
| `upsideCap` | percent | |
| `bufferLevel` | percent | |
| `downsideGearing` | percent | |

### barrier_note
| Field | Unit | Material |
|---|---|---|
| `barrierLevel` | percent | ✅ |
| `barrierType` (European/American) | text | ✅ |
| `settlementType` (cash/physical) | text | |
| `downsideGearing` | percent | |
| `participationRate` | percent | |
| `upsideCap` | percent | |

### snowball_autocall
| Field | Unit | Material |
|---|---|---|
| `couponRate` | percent | ✅ |
| `couponBarrier` | percent | |
| `autocallTrigger` | percent | ✅ |
| `callType` (automatic/issuer) | text | |
| `firstCallDate` (end of no-call period) | date | |
| `stepDown` (per period) | percent | |
| `settlementType` | text | |
| `knockInLevel` | percent | ✅ |
| `memoryCoupon` | bool | ✅ |
| `observationFrequency` | text | |

### phoenix_autocall
| Field | Unit | Material |
|---|---|---|
| `couponRate` (contingent coupon) | percent | ✅ |
| `settlementType` | text | |
| `couponBarrier` | percent | ✅ |
| `autocallTrigger` | percent | ✅ |
| `callType` (automatic/issuer) | text | |
| `firstCallDate` | date | |
| `knockInLevel` | percent | ✅ |
| `memoryCoupon` | bool | ✅ |
| `observationFrequency` | text | |

### contingent_yield_note
Phoenix minus the call fields — a contingent-coupon note that runs to
maturity. If you find yourself wanting `autocallTrigger`, `callType`, or
`firstCallDate` here, the note has a call feature and belongs in
`phoenix_autocall`.

| Field | Unit | Material |
|---|---|---|
| `couponRate` (contingent coupon) | percent | ✅ |
| `couponBarrier` | percent | ✅ |
| `knockInLevel` | percent | ✅ |
| `memoryCoupon` | bool | ✅ |
| `settlementType` (cash/physical) | text | |
| `observationFrequency` | text | |

### mlcd
| Field | Unit | Material |
|---|---|---|
| `participationRate` | percent | ✅ |
| `upsideCap` | percent | |
| `fdicCoverageLimit` | usd | |
| `observationFrequency` (averaging) | text | |

### digital_income
| Field | Unit | Material |
|---|---|---|
| `couponRate` | percent | ✅ |
| `couponBarrier` | percent | |
| `settlementType` | text | |
| `memoryCoupon` | bool | |
| `downsideProtectionType` | text | |
| `downsideProtectionLevel` | percent | |

### dual_directional
| Field | Unit | Material |
|---|---|---|
| `participationRate` (upside) | percent | ✅ |
| `upsideCap` | percent | |
| `absoluteReturnBarrier` | percent | |
| `downsideBarrier` | percent | ✅ |
| `settlementType` | text | |

## List tables

### `underliers` — one row per reference asset
Applies to: all multi-underlier-capable types (everything except mlcd).
Always fill this table — even single-underlier notes get their one row — and
keep it consistent with `underlierStructure`:

- **`single`** — exactly one row; `weight` null.
- **`worst_of`** (or rare `best_of`) — ≥2 rows, `weight` null (no weights —
  the payoff keys off the worst performer), and per-underlier barrier/knock-in
  **levels** present (each underlier has its own absolute thresholds).
- **`basket_equal_weight`** — ≥2 rows, all weights equal (1/n; the text may
  say "equally weighted" without printing numbers — record 1/n and quote that
  phrase as evidence). Barriers are defined at the **basket** level, so the
  per-underlier barrier columns are usually null.
- **`basket_defined_weight`** — ≥2 rows with stated, differing weights that
  must sum to ~100%. Basket-level barriers, as above.

| Column | Unit |
|---|---|
| `symbol` | text |
| `name` | text |
| `initialLevel` | level |
| `couponBarrierLevel` | level (absolute, per underlier; null for basket structures) |
| `knockInLevel` | level (absolute, per underlier; null for basket structures) |
| `protectionLevel` | level (absolute, per underlier; null for basket structures) |
| `weight` (basket weight; null for single/worst-of) | percent |

`knockInLevel` vs `protectionLevel`: the knock-in (aka final barrier /
downside threshold / trigger) is **contingent** protection — breach it and
downside exposure applies from the initial level. A protection/buffer level is
**hard** protection — losses apply only below it, and only for the excess.
Citi-style docs print a per-underlying "Final barrier value" (knock-in);
buffered notes state a "Buffer Level" (protection). A note usually has one or
the other — put the value in the column matching its mechanics, not its label,
and leave the other null.

### `observationSchedule` — one row per scheduled observation/call date
Applies to: coupon-bearing types (`snowball_autocall`, `phoenix_autocall`,
`contingent_yield_note`, `digital_income`). Income notes without a call still
observe per period — the call columns come back null.

| Column | Unit |
|---|---|
| `observationDate` | date |
| `autocallLevel` (trigger, fraction of initial) | percent |
| `couponBarrierLevel` (fraction of initial) | percent |
| `couponAmount` (per period) | percent |
| `callPremium` (snowball step-up over par; 0/null when redeemed at par) | percent |
| `paymentDate` | date |

## Field-hunting notes (from production label text)

- **`underlierStructure`** — classify from the payoff language, not the count
  of assets. Worst-of: "worst performing", "least performing", "lowest
  performing underlier", "laggard" — the payoff references one asset's
  performance. Basket: "weighted basket", "Basket Return", "Basket Level" —
  the payoff references a composite. Equal-weight baskets often say "equally
  weighted" instead of printing weights. A note listing five indices can be
  either worst-of or basket, and the economics are completely different —
  this field is material precisely because the distinction is easy to skip.
- **`strikeDate`** — the date the underliers' initial levels are observed.
  Labels vary by program: "Pricing Date" (Citi and others — "its closing
  value on the pricing date"), "Strike Date" (UBS, and it can precede the
  Trade Date), "Initial Valuation Date", "Determination Date". Assign dates
  by **role**, not label: record `strikeDate` whenever the document states
  when initial levels are set — even when that is the same calendar day as
  the trade date, quote the statement that gives it the strike role. Leave it
  null (with a derived "assumed struck on trade date" note) only when the
  strike role is genuinely unstated. Some notes strike as an **average** over
  several dates — record the dates in `offSchemaTerms` and warn.
- **`memoryCoupon`** — true if previously unpaid coupons can be paid later.
  Look for catch-up language: "plus any previously unpaid Contingent Coupons",
  "including any Contingent Coupons otherwise payable but unpaid", "coupons
  that were not previously paid", "catch-up payment/provision", or a formula
  multiplying the coupon by the number of unpaid periods.
- **`callType`** — "automatic" when a trigger level mechanically calls the
  note ("will be automatically called if…"); "issuer" when redemption is at
  the issuer's election ("we may, at our election, redeem", "callable at the
  issuer's option/discretion"). When unstated but an autocall trigger level is
  defined, downstream treats it as automatic — leave null and note it.
- **`firstCallDate`** — the end of the no-call period; the earliest date the
  note can be called. May be phrased as "callable on any Observation Date on
  or after…".
- **`callPremium`** — snowball notes accrue a premium to the call date;
  phoenix notes redeem at par (premium 0/null).
