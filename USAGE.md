# Using These Skills with Claude Code and Codex

This repository is the source of truth for five personal finance workflows. It
can serve both Claude Code (CC) and Codex without maintaining two hand-edited
copies:

```text
~/.claude/skills/                         source checkout used by Claude Code
        │
        └── scripts/install_codex_skills.py
                         │
                         ▼
~/.agents/skills/                         generated copies used by Codex
```

Use the files in this repository for edits. Treat `~/.agents/skills/` as a
generated installation and refresh it with the installer after repository
changes.

## Claude Code and Codex at a glance

| | Claude Code | Codex CLI, IDE, and app |
|---|---|---|
| Personal skill location | `~/.claude/skills/<name>/SKILL.md` | `~/.agents/skills/<name>/SKILL.md` |
| Explicit invocation | `/skill-name arguments` | Mention `$skill-name` in the prompt, or select it with `/skills` |
| Automatic invocation | Matches the skill description | Matches the skill description |
| Project instructions | `CLAUDE.md` | `AGENTS.md` |
| Product-specific metadata | Honors `argument-hint`, `model`, and `context: fork` in these source files | Uses portable frontmatter plus optional `agents/openai.yaml` metadata |
| Bundled file paths | Resolves `${CLAUDE_SKILL_DIR}` at invocation time | The installer resolves that variable to the installed skill's absolute path |
| Change discovery | Watches existing skill directories live | Detects changes automatically; restart if an update does not appear |

Both products initially discover a skill from its name and description, then
load the full instructions and supporting resources only when the skill is
selected. Explicit invocation is useful when you want predictable routing;
natural-language prompts are often enough for ordinary work.

## One-time setup

### 1. Install for Claude Code

On a new machine, clone the repository as the personal Claude Code skills
directory:

```bash
git clone https://github.com/zkramer23/skills.git ~/.claude/skills
```

If the repository is already at `~/.claude/skills`, no additional Claude Code
installation is needed. Start `claude` in the project that contains the files
you want to analyze, not in the skills repository.

Claude Code watches an existing personal skills directory for changes. Restart
it only if the top-level directory was created after the session began or a
skill does not appear.

### 2. Install for Codex

Generate portable copies in Codex's personal skills directory:

```bash
python3 ~/.claude/skills/scripts/install_codex_skills.py
```

The installer:

- discovers every top-level directory containing `SKILL.md`;
- copies its scripts, references, examples, commands, and UI metadata;
- removes Claude-only YAML fields from the generated `SKILL.md`;
- resolves `${CLAUDE_SKILL_DIR}` so bundled commands work in Codex; and
- updates only destinations previously created by this installer.

It refuses to overwrite an unmanaged directory with the same name. Move or
rename that directory after reviewing it, then rerun the installer.

Useful options:

```bash
# Preview all changes
python3 ~/.claude/skills/scripts/install_codex_skills.py --dry-run

# Install only selected skills
python3 ~/.claude/skills/scripts/install_codex_skills.py \
  --skill bloomberg-api \
  --skill portfolio-analytics-qa

# Inspect the available source skills
python3 ~/.claude/skills/scripts/install_codex_skills.py --list

# Test a separate target without touching the normal installation
python3 ~/.claude/skills/scripts/install_codex_skills.py --target /tmp/codex-skills
```

Start a new Codex session if the new skills do not appear immediately. In the
CLI or IDE, `/skills` shows the discovered skills and typing `$` opens the skill
mention picker.

### Why not symlink the same folders into both products?

Codex supports symlinked skill folders, but these particular source files use
Claude Code extensions: model selection, argument hints, forked context, and
`${CLAUDE_SKILL_DIR}`. A direct symlink would preserve syntax that is not part
of Codex's portable frontmatter contract. Generated copies preserve Claude
Code's richer behavior while giving Codex a validated skill and executable
script paths.

## How to invoke each skill

The examples below are explicit. You can also describe the same job naturally
and let either agent select the matching skill.

### Prospectus extraction

Use for pricing supplements, term sheets, prospectuses, and market-linked CD
disclosures. The output is evidence-grounded: extracted values carry page-cited
quotes, and absent values stay null.

Claude Code:

```text
/prospectus-extraction ./pricing-supplement.pdf json
```

Codex:

```text
$prospectus-extraction Extract ./pricing-supplement.pdf to evidence-grounded JSON. Preserve page citations and flag uncertain terms.
```

Good follow-ups include:

```text
Compare these three term sheets and rank their coupons, barriers, and call mechanics.
Export the extraction to relational CSVs and SQLite.
Verify every barrier and observation date against its cited text.
```

### Bloomberg API

Use for Desktop API request design, identifier and field selection, historical
or reference data, lifecycle fixings, and `blpapi` troubleshooting. Use its
mock/replay route when a Bloomberg Terminal is unavailable.

Claude Code:

```text
/bloomberg-api history NDX Index PX_LAST from 2026-01-01
/bloomberg-api troubleshoot "responseError: BAD_SEC"
/bloomberg-api mock a three-underlier worst-of coupon observation
```

Codex:

```text
$bloomberg-api Build a historical-data request for NDX Index PX_LAST from 2026-01-01. Preserve partial-response handling and field errors.
$bloomberg-api Diagnose this BAD_SEC response and separate retryable from terminal failures.
```

Specify the identifier, request type, field, date range, adjustment policy, and
whether the value must be an official close whenever those choices matter.

### Structured-note payoff engine

Use after extraction to compile a canonical payoff specification and evaluate
terminal, scenario, coupon, memory, or automatic-call economics.

Claude Code:

```text
/structured-note-payoff-engine ./note.extraction.json validate
/structured-note-payoff-engine ./payoff-spec.json scenarios
```

Codex:

```text
$structured-note-payoff-engine Compile ./note.extraction.json into a canonical payoff spec, validate it, and run boundary scenarios.
```

The deterministic helper supports direct use when you already have a payoff
specification:

```bash
python3 ~/.claude/skills/structured-note-payoff-engine/scripts/payoff_engine.py \
  terminal payoff-spec.json --performance 0.69
```

For a Codex installation in a non-default location, let the skill run its own
installed script path instead of hard-coding the Claude path above.

### Structured-note monitor

Use for an as-of inventory view: event ledgers, upcoming observations and
payments, coupon/call status, unresolved determinations, position cashflows,
and exception queues.

Claude Code:

```text
/structured-note-monitor ./inventory.json ./observations.json --as-of 2026-07-15
```

Codex:

```text
$structured-note-monitor Run the inventory in ./inventory.json against ./observations.json as of 2026-07-15. Produce the event ledger, 45-day calendar, cashflows, and exception queue.
```

Always provide an explicit as-of date for replayable work. Market-derived
results remain indicative until reconciled to an official determination.

### Portfolio analytics QA

Use to audit financial metric contracts, source-data semantics, alignment,
edge cases, and tests across returns, risk, dividends, earnings, volatility,
options, and liquidity analytics.

Claude Code:

```text
/portfolio-analytics-qa ./backend/services/risk_service.py audit
/portfolio-analytics-qa ./exports/prices.json oracle
```

Codex:

```text
$portfolio-analytics-qa Audit ./backend/services/risk_service.py. Recompute representative cases with the independent oracle and report contract, alignment, and edge-case failures.
```

Ask for both the implementation review and an independent recomputation when a
metric is decision-critical.

## Recommended structured-note workflow

The three note skills have deliberately separate contracts. Bloomberg supplies
sourced observations rather than replacing document interpretation or payoff
logic.

```text
offering PDF
    │
    ▼
prospectus-extraction ──► canonical terms with evidence
    │
    ▼
structured-note-payoff-engine ──► validated payoff spec and scenarios
    │                                      ▲
    │                                      │
    └──────── bloomberg-api ──► sourced observations
                                           │
                                           ▼
                              structured-note-monitor
                                           │
                                           ▼
                       ledger + calendar + exceptions + cashflows
```

Run the stages in separate turns when you want to inspect each artifact, or ask
the agent to use several skills in one task.

Claude Code example:

```text
/prospectus-extraction ./note.pdf json
```

Then:

```text
/structured-note-payoff-engine ./note.extraction.json validate and scenarios
```

Codex example:

```text
$prospectus-extraction $structured-note-payoff-engine Extract ./note.pdf, compile a canonical payoff spec, validate all evidence mappings, and run barrier/call boundary scenarios. Save each intermediate artifact separately.
```

For lifecycle work, source observations with `bloomberg-api`, retain their
retrieval timestamps and field semantics, then pass them with the validated
inventory to `structured-note-monitor`.

## Environment and data requirements

- All deterministic helpers use Python 3. The payoff, monitor, and analytics
  helpers use only the standard library.
- Prospectus PDF text extraction runs through `uv run` and declares its Python
  dependency inline. Install [`uv`](https://docs.astral.sh/uv/) if it is not
  already available.
- Live Bloomberg examples require Bloomberg Desktop API access, a running
  Terminal session, and the matching `blpapi` Python package. Mock and replay
  workflows do not.
- Run agents from the project containing your input and output files. Personal
  skills remain available across projects.
- Keep source documents, extracted terms, observations, and derived ledgers as
  separate artifacts. Do not silently overwrite evidence or historical as-of
  results.
- Review financial outputs before using them for trading, valuation,
  suitability, tax, compliance, or client reporting decisions.

## Claude Code versus Codex behavior

The workflow instructions and deterministic scripts are the same. A few host
behaviors differ:

- Claude Code honors the per-skill `model` choice. Prospectus extraction uses
  Opus; the other skills specify Sonnet.
- Claude Code runs prospectus extraction and note monitoring with
  `context: fork`, keeping document or inventory volume out of the main thread.
- Codex uses the active session/configured model because the portable copy does
  not carry Claude's model field. If isolation matters, start a focused Codex
  thread or explicitly ask Codex to delegate the bounded stage.
- Codex UI metadata in `agents/openai.yaml` is optional. A skill remains usable
  without that file; it only improves presentation and invocation policy where
  supported.
- Permission and sandbox behavior belongs to the host. A skill's instructions
  do not override the approval rules of either agent.

## Updating both installations

Pull once, then refresh Codex's generated copies:

```bash
cd ~/.claude/skills
git pull --ff-only
python3 scripts/install_codex_skills.py
```

Claude Code reads the checkout directly. Do not edit the generated files under
`~/.agents/skills`; those changes are replaced on the next sync.

Before committing changes to the source skills, run the repository tests:

```bash
cd ~/.claude/skills
pytest -q
```

You can also test a portable installation without changing your real Codex
environment:

```bash
python3 scripts/install_codex_skills.py --target /tmp/codex-skills-test
```

## Troubleshooting

### A skill does not appear

1. Confirm its `SKILL.md` exists at the expected personal path.
2. In Claude Code, open `/skills` and confirm the skill is enabled. Restart if
   the personal skills directory was created during the current session.
3. In Codex, rerun the installer, open `/skills`, and restart Codex if the copy
   still does not appear.
4. Check for two installed skills with the same `name`; Codex lists both rather
   than merging them.

### The wrong skill triggers

Invoke it explicitly with `/name` in Claude Code or `$name` in Codex. Include
the artifact path and desired operation in the same prompt. If automatic
routing repeatedly misfires, improve the source skill's `description` rather
than patching a generated Codex copy.

### A bundled script cannot be found

Rerun `install_codex_skills.py`. It regenerates the Codex path substitutions.
For Claude Code, confirm that the repository remains at the path containing the
invoked skill and that the bundled `scripts/` directory was not omitted.

### The Codex installer refuses a destination

The existing folder was not created by this installer, so it may contain your
work. Review and move it aside manually. The installer intentionally has no
force flag for unmanaged destinations.

### Bloomberg calls fail outside the Terminal environment

Use the `bloomberg-api` troubleshooting route to distinguish connection,
entitlement, security, field, and response errors. Use the mock/replay route for
development and CI where Desktop API access is unavailable.

## Official references

- [Claude Code: Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Agent Skills open specification](https://agentskills.io/specification)

