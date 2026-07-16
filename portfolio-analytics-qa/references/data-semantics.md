# Data semantics and alignment

## Price series

Record these attributes with every analytical series:

- vendor and endpoint;
- security identifier and venue;
- field (`Close`, `Adj Close`, official close, NAV, total-return index);
- adjustment flags;
- currency and quote units;
- session date/timezone;
- retrieval timestamp;
- requested range and actual observation range.

Do not mix vendor series merely because ticker labels match. Corporate-action
history, session boundaries, and adjustment restatements can differ.

## Calendar alignment

- Compute single-security returns on that security's valid observations.
- For beta, alpha, correlation, or active return, align the return intervals,
  not just endpoint dates.
- Cross-market holidays can create multi-day versus one-day interval mismatch.
  Either aggregate both sides to common intervals or mark the comparison
  unavailable.
- A forward-fill can be appropriate for a display line, but it introduces a
  zero return and must not silently enter volatility/correlation calculations.
- Pre-inception baselines are visualization scaffolding, never observations.

## Annualization

Use actual elapsed years for CAGR. Use declared observation counts for
dispersion annualization: typically 252 daily, 52 weekly, or 12 monthly. Do not
infer “daily” merely from row count; inspect timestamps and resampling.

Convert an annual effective risk-free rate `rf` to periodic:

```text
rf_period = (1 + rf)^(1 / periods_per_year) - 1
```

Fallback macro rates must carry `source=fallback`, the chosen value, and a
warning through the API and UI.

## Units and signs

- Use decimals internally (`0.12`) and percentage points only for display
  (`12.0%`). Name percentage-point fields with `_pct` if the API uses them.
- Keep currencies and subunits explicit (`GBP` versus `GBp`).
- Choose one VaR convention. This skill's oracle reports positive loss.
- Drawdown is normally non-positive; “drawdown magnitude” is positive. Do not
  use those names interchangeably.
- Participation input may be decimal (`0.10`) or percentage points (`10`);
  reject ambiguity at the boundary.

## Data-quality findings

Classify each issue as missing, stale, conflicting, substituted, insufficient,
or unsupported. Include the affected metric and whether the UI should hide it,
show null, or display it with a warning.
