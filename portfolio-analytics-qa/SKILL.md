---
name: portfolio-analytics-qa
description: >-
  Design, audit, test, and reconcile portfolio and security analytics across
  returns, benchmarks, inflation, volatility, Sharpe/Sortino/Calmar ratios,
  beta/alpha, drawdowns, VaR, dividends, earnings events, historical/implied
  volatility, options Greeks, and liquidity estimates. Use whenever the user
  builds or reviews an investment dashboard, tearsheet, risk endpoint, return
  attribution, volatility surface, liquidation model, or financial-metric
  calculation; reports inconsistent values across screens or vendors; asks
  whether a formula is correct; or needs deterministic finance test fixtures.
argument-hint: "<code|dataset|metric|endpoint> [audit|oracle|tests|reconcile]"
model: sonnet
---

# Portfolio Analytics QA

Treat every metric as a contract: source series, adjustment convention,
calendar, unit, formula, annualization, missing-data policy, and output sign.
Audit the contract before debugging arithmetic.

## Workflow

1. **Inventory claims.** List each displayed/output metric and its business
   meaning. Separate price return, total return, and realized cash flows.
2. **Trace the data lineage.** Identify source, timestamp, timezone, currency,
   price adjustment, dividend/corporate-action treatment, frequency, and any
   fallback. Read [references/data-semantics.md](references/data-semantics.md).
3. **Write the metric contract.** Use
   [references/metric-contracts.md](references/metric-contracts.md). State units
   and sign convention before comparing values.
4. **Calculate an independent oracle.** For supported metrics, run the bundled
   standard-library tool on a small frozen JSON fixture:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/metric_oracle.py" returns prices.json --inflation 0.03
   python3 "${CLAUDE_SKILL_DIR}/scripts/metric_oracle.py" risk prices.json --benchmark benchmark.json --risk-free 0.04
   python3 "${CLAUDE_SKILL_DIR}/scripts/metric_oracle.py" liquidity --shares 250000 --adtv 1000000 --participation 0.10
   ```

5. **Localize disagreement.** Compare intermediate return series before final
   ratios. Most apparent formula bugs are actually adjusted-close, dividend,
   calendar, unit, or alignment bugs.
6. **Test degeneracies.** Include flat prices, total loss, zero variance,
   sparse history, missing benchmark dates, special dividends, splits, zero
   volume, and insufficient option quotes.
7. **Report by severity.** Lead with incorrect economic meaning, then silent
   data substitutions, numerical errors, inconsistent UI contracts, and
   presentation issues. Provide the smallest reproducible fixture.

For options or volatility work, additionally read
[references/options-volatility.md](references/options-volatility.md).

## Non-negotiable checks

- Use the same total-return construction across comparison, attribution, and
  risk screens. Do not call cash-dividend addition and dividend reinvestment
  the same metric.
- Use actual first/last valid observations for annualization; keep the requested
  range separately as metadata.
- Use exact real-return math, `(1 + nominal) / (1 + inflation) - 1`.
- Convert annual risk-free rates to the observation period before subtracting
  them from periodic returns.
- Never subtract an annual percentage rate directly from a daily decimal mean.
- State whether VaR is a positive loss or negative return and keep that sign
  everywhere.
- Calculate comparative statistics only on aligned return intervals. Do not
  fabricate pre-inception `100` values for metric computation.
- Sum volume over multi-day buckets when measuring traded volume; use daily
  observations for ADTV.
- Surface fallback CPI/risk-free rates as data-quality findings, not invisible
  defaults.
- Keep display forward-fills out of analytical return series unless the
  stale-price policy explicitly permits them.

## Output

Return a metric-contract table, findings with severity and evidence, oracle
results, a minimal failing fixture, and proposed regression tests. Distinguish:

- **wrong** — violates the declared economic contract;
- **inconsistent** — individually defensible conventions differ across screens;
- **approximate** — acceptable only when labeled;
- **unverifiable** — source data or convention is missing.

Do not change a convention merely to match another vendor. First establish
which convention the product intends to display.
