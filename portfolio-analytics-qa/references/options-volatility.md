# Options and volatility QA

## Historical volatility

- State simple versus log returns, window length, minimum observations, and
  annualization.
- A volatility cone is a distribution of historical realized volatilities for
  comparable windows, not percentiles of individual daily returns.
- Vol-of-vol needs its own window and unit. Do not compare an annualized IV
  percentage directly with an unannualized vol-of-vol number.
- Timestamp the ATM IV used in any HV-IV spread.

## Option inputs

Capture spot timestamp, option quote timestamp, strike, expiry/timezone,
option style, dividend/carry assumption, yield curve, and contract multiplier.
A hard-coded risk-free rate or zero dividend yield is an approximation that
must appear in warnings.

For Black-Scholes with continuous dividend yield `q`, use:

```text
d1 = [ln(S/K) + (r - q + σ²/2)T] / (σ√T)
d2 = d1 - σ√T
```

State Greek units: theta per day versus per year; vega per 1 volatility point
versus per unit volatility.

## Quote filtering

- Prefer executable midquotes with positive bid, non-crossed markets, and
  acceptable spread; last trade may be stale.
- Volume zero does not necessarily mean invalid if open interest and a current
  market exist. Make filtering policy configurable.
- Calls and puts can provide complementary OTM information. If using calls
  only, label the resulting surface and inspect dividend/carry effects.

## Surface construction

- Interpolate total variance over expiry and log-moneyness/delta rather than
  raw IV over strike when production quality matters.
- Check non-negative variance, calendar monotonicity, convexity/butterfly
  behavior, and call-price bounds after interpolation.
- Nearest-neighbor filling can create visually smooth but economically invalid
  regions; expose extrapolated cells.
- Do not describe a surface as arbitrage-free unless those constraints are
  actually enforced.

## Minimal tests

- Put-call parity within quote/timing tolerances.
- Delta bounds and put/call signs.
- Positive gamma and vega for standard long European options.
- Expired, zero-volatility, zero-spot, and deep ITM/OTM behavior.
- Known textbook price/Greek fixture.
- Sparse and collinear surface points without silent NaNs/infinities.
