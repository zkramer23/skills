---
name: structured-note-payoff-engine
description: >-
  Compile evidence-backed structured-note terms into a canonical payoff
  specification, validate the economics, calculate terminal redemption and
  path-dependent coupon/autocall scenarios, and generate boundary-focused test
  cases. Use whenever the user asks to model, graph, simulate, explain, review,
  or test a structured-note payoff; translate prospectus extraction JSON into
  executable economics; compare note structures; check payoff code; or answer
  what-if questions about autocallables, contingent-yield notes, barrier notes,
  accelerated return notes, dual-directional notes, digital income notes, or
  market-linked CDs. Do not use market levels as contractual determinations.
argument-hint: "<terms-or-extraction.json> [validate|terminal|path|scenarios|tests]"
model: sonnet
---

# Structured Note Payoff Engine

Translate document terms into deterministic, reviewable calculations. Keep
term interpretation evidence-grounded; let the bundled engine perform the
math. Treat every result as indicative unless it comes from the calculation
agent.

## Workflow

1. **Establish the source of truth.** If starting from a prospectus, invoke the
   `prospectus-extraction` skill first. Preserve its evidence and warnings. If
   terms are incomplete, stop before modeling the missing mechanic.
2. **Build a canonical specification.** Read
   [references/payoff-spec.md](references/payoff-spec.md). Map the note's stated
   mechanics into the closed schema; never choose a formula merely from the
   marketing name.
3. **Reconcile product mechanics.** Read
   [references/product-mapping.md](references/product-mapping.md) for the
   relevant product family. Record any off-schema feature instead of silently
   approximating it.
4. **Validate before calculating.** Run:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/payoff_engine.py" validate payoff-spec.json
   ```

5. **Calculate with the deterministic engine.** Use `terminal`, `scenario`, or
   `path` according to the task. Never reimplement the formulas in ad hoc code
   when the engine supports the mechanic.
6. **Test discontinuities and state.** Read
   [references/validation.md](references/validation.md). Always test exactly at,
   immediately below, and immediately above every barrier, cap, trigger, and
   buffer boundary.
7. **Report assumptions and limitations.** Separate stated terms, derived
   mappings, scenario inputs, and results. Flag issuer-elective calls as not
   determinable from market performance.

## Commands

```bash
# One terminal outcome from an aggregate performance ratio
python3 "${CLAUDE_SKILL_DIR}/scripts/payoff_engine.py" terminal payoff-spec.json --performance 0.69

# A grid of terminal outcomes
python3 "${CLAUDE_SKILL_DIR}/scripts/payoff_engine.py" scenario payoff-spec.json --start 0.4 --end 1.6 --step 0.05

# Coupon/autocall path from observation levels
python3 "${CLAUDE_SKILL_DIR}/scripts/payoff_engine.py" path payoff-spec.json observations.json
```

Use `--output result.json` on calculation commands when the result feeds
another workflow. Use `--levels-json '{"SPX Index": 6500}'` instead of
`--performance` when the underlier aggregation itself must be tested.

## Hard guards

- Do not infer missing barriers, participation, gearing, caps, observation
  rows, or call mechanics from a product label.
- Do not collapse worst-of and weighted-basket structures; their aggregation
  is economically different.
- Do not treat an issuer-election date as an automatic trigger.
- Do not use adjusted historical data for contractual barrier scenarios unless
  the note terms explicitly incorporate the same adjustment.
- Do not auto-fill missing observation levels. A disruption or postponement is
  an unresolved state, not the prior close.
- Do not present payoff charts without the notional convention, units, formula
  assumptions, and the loss region.

## Output contract

Return:

1. the canonical spec or a concise terms table;
2. validation findings and unresolved mechanics;
3. the scenario/path result with units;
4. boundary cases tested;
5. an “indicative, subject to official determination” label when market data
   or lifecycle conclusions are involved.

For charts, plot aggregate-underlier performance on the x-axis and redemption
or note return on the y-axis. Include markers at every economic boundary and
provide the underlying scenario table alongside the visual.
