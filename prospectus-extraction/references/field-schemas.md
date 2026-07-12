# Product types and field schemas

Ported from the payout-grapher extraction pipeline
(`~/dev/payout-grapher/server/src/prospectus/schemas.ts` + `classify.ts`).
The schema is developer-controlled and closed: extract exactly these fields for
the classified type, nothing else. **Material** fields are marked — a missing
or evidence-free material field is a headline warning.

This skill's schema extends the repo's where it lacks coverage: the
`strikeDate`, `underlierStructure`, `nonCallPeriodMonths`, and `stepUp`
fields (plus `stepDown` on phoenix — the repo has it on snowball only), and
the `contingent_yield_note` product type (contingent-coupon notes with no
trigger-automatic call — both the no-call and issuer-callable variants, which
the repo folds into phoenix). If importing results back into payout-grapher,
expect the extra fields to land in `unmappedFields` and map
`contingent_yield_note` to `phoenix_autocall` with `autocallTrigger` null and
`callType` carried through ("issuer" or null).

## Classification keywords

Distinguishing phrases (case-insensitive) to scan for in the first ~6 pages.
Score by how many distinct signals hit; classify by mechanics when brands
collide.

| Product type | Signals |
|---|---|
| `accelerated_return_note` | accelerated return, leveraged upside, upside leverage factor, participation rate, enhanced growth |
| `barrier_note` | downside threshold, knock-in, barrier level, european barrier, trigger level |
| `snowball_autocall` | snowball, step-down / stepdown, memory coupon (with call premium accruing to call date) |
| `phoenix_autocall` | phoenix, contingent coupon/yield/income + coupon barrier, autocallable / auto-callable, "automatically called/redeemed if" — **the call is trigger-automatic** |
| `contingent_yield_note` | same contingent coupon/yield/income + barrier language but **no trigger-automatic call**: either no call feature at all, or an issuer-elective one ("callable", "we may redeem", redemption-dates list with notice period) |
| `mlcd` | market-linked CD, market linked certificate, certificate of deposit, FDIC |
| `digital_income` | digital coupon, digital return, fixed coupon, digital note |
| `dual_directional` | dual directional, dual-directional, absolute return |

**Coupon-note family decision rule** — contingent-coupon language identifies
the family; the **call mechanism** picks the type. "Phoenix" is reserved for
notes whose call outcome is **formulaic** — a market level alone proves
whether the note was called. When the issuer elects, the call depends on
issuer economics (funding levels, hedging), not on a printed trigger, so
those notes are CYNs no matter how "callable" the branding sounds:

- trigger-automatic call ("will be automatically called/redeemed if…") →
  `phoenix_autocall`
- issuer-elective call ("we may, at our election, redeem", "callable at our
  option", a redemption-dates list with a notice period) →
  `contingent_yield_note` with `callType: "issuer"` (issuer-callable CYN)
- no call or early-redemption feature at all → `contingent_yield_note` with
  `callType` null

Don't force a CYN into phoenix and then report a "missing" autocall trigger —
the trigger isn't missing, it doesn't exist. The classification line matters
downstream: called/not-called logic can verify a phoenix call from a market
level, but never an issuer call.

Dealer-brand hints: Morgan Stanley "Contingent Income **Auto-Callable**
Securities" → phoenix (automatic). UBS "Trigger **Callable** Contingent Yield
Notes" and Citi "**Callable** Contingent Coupon Notes" are typically
issuer-election → issuer-callable CYN. Check the call language, not the
brand. A contingent-coupon note whose document has no call section at all is
a plain CYN.

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
| `nonCallPeriodMonths` | months | |
| `stepDown` (autocall trigger step-down per period) | percent | |
| `stepUp` (coupon / call-premium step-up per period) | percent | |
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
| `callType` (should be `automatic` here — issuer-elective reclassifies to `contingent_yield_note`) | text | |
| `firstCallDate` | date | |
| `nonCallPeriodMonths` | months | |
| `stepDown` (autocall trigger step-down per period) | percent | |
| `stepUp` (coupon step-up per period) | percent | |
| `knockInLevel` | percent | ✅ |
| `memoryCoupon` | bool | ✅ |
| `observationFrequency` | text | |

### contingent_yield_note
A contingent-coupon note whose early redemption is never trigger-automatic —
either no call feature at all, or an issuer-elective call (issuer-callable
CYN). If you find yourself wanting `autocallTrigger` or `stepDown` here, the
note has a formulaic trigger and belongs in `phoenix_autocall`.

| Field | Unit | Material |
|---|---|---|
| `couponRate` (contingent coupon) | percent | ✅ |
| `couponBarrier` | percent | ✅ |
| `knockInLevel` | percent | ✅ |
| `memoryCoupon` | bool | ✅ |
| `callType` (`issuer` when issuer-elective; null when no call feature exists) | text | |
| `firstCallDate` (issuer-callable only) | date | |
| `nonCallPeriodMonths` (issuer-callable only) | months | |
| `stepUp` (coupon step-up per period) | percent | |
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
| `stepUp` (coupon step-up per period) | percent | |
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
  Finding issuer-election language on a note classified as phoenix means the
  classification is wrong — move it to `contingent_yield_note` (see the
  coupon-note decision rule).
- **`firstCallDate` / `nonCallPeriodMonths`** — two statements of the same
  call protection. Documents give either a period ("Non-Call Period: 6
  months", shorthand "NC6"/"NC1") or a date ("callable on any Observation
  Date on or after…", or the first date in a redemption-dates list). Record
  whichever is **stated** with evidence and derive the other (report it under
  `derived`). Ground truth check: the first observation-schedule row with a
  non-null call level IS the first call date.
- **`stepDown` / `stepUp`** — the observation schedule rows are ground truth:
  a declining per-row autocall level is a step-down; a rising per-row coupon
  or call premium is a step-up. Extract the scalar per-period rate only when
  the document states the rule ("the Trigger Level will decrease by 5.00% on
  each anniversary", "the Contingent Coupon Rate increases by 0.25% each
  quarter") — if the pattern exists only as a printed table, the rows carry
  it and the scalar stays null with a note. When both exist they must agree.
- **`callPremium`** — snowball notes accrue a premium to the call date;
  phoenix notes redeem at par (premium 0/null).
