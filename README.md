# Zach Kramer — Claude Skills

[Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) for Claude Code and claude.ai, built by [Zach Kramer](https://github.com/zkramer23) — domain workflows distilled into reusable instructions, reference material, and scripts that Claude loads on demand.

The current focus is **structured products**: these skills grew out of tooling I've built for ingesting and analyzing structured-note offering documents (autocallables, contingent yield notes, barrier notes, market-linked CDs), and they encode the field taxonomies, classification rules, and validation checks from that work so any Claude session can apply them.

## Skills

| Skill | What it does |
|---|---|
| [`prospectus-extraction`](prospectus-extraction/) | Evidence-grounded term extraction from structured-product offering documents (pricing supplements, term sheets, MLCD disclosures). Classifies the product (phoenix autocall, contingent yield note, snowball, barrier note, dual-directional, ARN, digital income, MLCD), extracts a closed per-type field schema with verbatim page-cited evidence for every value, runs deterministic cross-checks (memory-coupon language, issuer-call vs. autocall, underlier-structure consistency, fee sanity), and outputs a chat summary with the full observation/coupon calendar plus JSON → relational CSVs or SQLite for downstream analysis. |
| [`bloomberg-api`](bloomberg-api/) | Bloomberg Desktop API (blpapi) reference patterns for structured products. Encodes the session/event-loop patterns (partial responses, correlation IDs, retries), request-type selection, field semantics (official close vs. last, adjusted vs. unadjusted), identifier resolution (display name → ticker, FIGI hierarchy), an error taxonomy with retry rules, and Terminal-free testing via dependency injection and replay fixtures. Includes runnable examples for fixings, worst-of coupon/memory checks, autocall scans (trigger-automatic only), basket pricing, and issuer lookups. Invoke its playbooks through `/bloomberg-api history ...`, `/bloomberg-api troubleshoot ...`, `/bloomberg-api mock ...`, and the other routes documented in the skill. Pairs with `prospectus-extraction`: terms come from the document, levels from Bloomberg. |
| [`structured-note-payoff-engine`](structured-note-payoff-engine/) | Compiles evidence-backed note terms into a closed payoff specification and deterministically evaluates terminal scenarios, coupons, memory, and automatic-call paths. Includes a pure-standard-library engine plus boundary and invariant guidance. |
| [`structured-note-monitor`](structured-note-monitor/) | Operates a note inventory as of a fixed date. Joins canonical payoff specs, sourced observations, and official determinations into an auditable event ledger, upcoming calendar, exception queue, note state, and position-scaled cashflows. |
| [`portfolio-analytics-qa`](portfolio-analytics-qa/) | Audits the financial and data contracts behind returns, risk, dividend, earnings, volatility/options, and liquidity analytics. Includes an independent standard-library oracle for total returns, risk metrics, benchmark alignment, VaR, and liquidation timelines. |

## How a skill is structured

```
skill-name/
├── SKILL.md          # routing/model metadata + the workflow
├── agents/           # optional UI metadata for compatible skill hosts
├── commands/         # optional route-specific playbooks
├── references/       # deeper docs Claude reads only when needed
└── scripts/          # deterministic helpers Claude runs instead of rewriting
```

Skills use progressive disclosure: the frontmatter description is always in Claude's context (it's how the skill triggers), the SKILL.md body loads when the skill activates, and reference files load only when the task needs them. Deterministic, repetitive work (PDF text extraction, JSON flattening) lives in bundled scripts so every invocation behaves identically.

## Using these skills

**Claude Code** — clone into your skills directory:

```bash
git clone https://github.com/zkramer23/skills.git ~/.claude/skills
```

Skills auto-trigger on matching prompts in any project, or invoke one explicitly with `/skill-name`.

```text
/bloomberg-api history NDX Index PX_LAST from 2026-01-01
/prospectus-extraction ./pricing-supplement.pdf json
/structured-note-payoff-engine ./note.extraction.json scenarios
/structured-note-monitor ./inventory.json ./observations.json --as-of 2026-07-15
/portfolio-analytics-qa ./backend/services/risk_service.py audit
```

The skills carry their own execution policy: engineering and financial QA use
Sonnet; long prospectus reviews use Opus in a forked context; portfolio note
monitoring also forks so a large inventory ledger does not fill the main
conversation. That keeps the everyday global model lightweight without
under-powering domain work.

The structured-note workflow is deliberately composable:

```text
prospectus-extraction → structured-note-payoff-engine → structured-note-monitor
          terms                    economics                    operations
              bloomberg-api supplies sourced market observations ────────┘
```

**claude.ai (web/desktop)** — package a skill into a `.skill` file and upload it under Settings → Capabilities:

```bash
cd skill-name && zip -r ../skill-name.skill .
```

**Scripts** — no environment setup. Python scripts are either pure stdlib or declare their own dependencies inline ([PEP 723](https://peps.python.org/pep-0723/)) and run via [`uv run`](https://docs.astral.sh/uv/).

## Conventions

- One folder per skill; `SKILL.md` stays lean and explains *why* behind each rule, not just what.
- Domain knowledge comes from real pipelines and real documents, not generic instructions — extraction schemas, classification rules, and validation checks are ported from production code and verified against actual filings.
- Anything Claude would rebuild every session (parsers, exporters) gets bundled as a script once.

---

Maintained by [Zach Kramer](https://github.com/zkramer23). Questions or ideas — open an issue.
