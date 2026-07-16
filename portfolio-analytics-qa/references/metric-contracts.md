# Metric contracts

All formulas below use decimal returns. Convert to percentage points only at
the presentation boundary.

| Metric | Contract |
|---|---|
| Price return | `end_close / start_close - 1`; state the close adjustment convention. |
| Total return | Chain `(close_t + cash_distribution_t) / close_(t-1)` when distributions are reinvested. |
| Dividend contribution | Total return minus price return is an attribution residual, not cash received. |
| CAGR | `(ending_value / starting_value)^(1 / actual_years) - 1`; invalid at non-positive ending wealth. |
| Real return | `(1 + nominal_return) / (1 + inflation_return) - 1`. |
| Volatility | Sample standard deviation of periodic returns times `sqrt(periods_per_year)`. |
| Sharpe | Annualized arithmetic excess return divided by annualized volatility; define risk-free conversion. |
| Sortino | Annualized excess return divided by annualized downside deviation; define MAR and denominator. |
| Max drawdown | Minimum of `wealth / running_peak - 1` on the chosen price/total-return index. |
| Calmar | CAGR divided by absolute maximum drawdown over the same series and range. |
| Beta | Sample covariance of aligned security/benchmark returns divided by benchmark variance. |
| Alpha | Annualized security return minus `[rf + beta × (benchmark - rf)]`, using one return convention. |
| Tracking error | Sample standard deviation of aligned active returns, annualized. |
| Information ratio | Annualized mean active return divided by tracking error. |
| Historical VaR | Quantile of actual rolling horizon returns; report positive loss as `max(0, -quantile)`. |
| Parametric VaR | Normal approximation using horizon mean and `sqrt(horizon)` volatility; label distribution assumption. |
| ADTV | Mean daily traded volume over a named lookback; do not substitute a last weekly/monthly observation. |
| Days to liquidate | `ceil(position_shares / (ADTV × participation))`, before impact/capacity adjustments. |

## Convention choices that must be explicit

- Arithmetic versus geometric return in risk-adjusted ratios.
- Daily/weekly/monthly observation frequency and periods per year.
- Sample (`n-1`) versus population (`n`) dispersion.
- Simple versus log returns.
- Price versus total-return drawdown.
- Benchmark and risk-free currency.
- Historical VaR interpolation method and overlapping horizon windows.
- Return timestamps, session close, and timezone.

Two correct formulas with different conventions need reconciliation, not a
blind assertion that one is wrong.

## Dividends and corporate actions

- `Close` may already be split-adjusted even when it is not dividend-adjusted.
- `Adj Close` or an auto-adjusted price can already incorporate distributions;
  adding dividends again double-counts them.
- Summing dividends onto final price models cash held without reinvestment.
  Chaining gross returns models reinvestment. Label the choice.
- Special dividends and return-of-capital events need classification; median-
  based heuristics are findings, not authoritative event types.
- Forward dividend yield is an estimate; trailing yield is historical. Never
  display them under one unlabeled `dividend_yield` field.

## Earnings-event studies

- Map an announcement to the correct trading session using timestamp and
  before-open/after-close status.
- Calculate security and benchmark windows over identical sessions.
- Distinguish simple excess return from regression alpha.
- Avoid overlapping-event windows or disclose the overlap.
- Preserve delisted/missing observations as unavailable; do not shorten the
  requested window silently.
