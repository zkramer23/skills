---
name: prospectus-extraction
description: >-
  Read structured-product offering documents — prospectuses, pricing supplements
  (preliminary or final), term sheets, and market-linked CD disclosures — and
  extract their terms as structured, evidence-grounded data. Use this whenever
  the user wants terms pulled out of a note/CD offering PDF: payout parameters,
  coupons, barriers, autocall triggers, observation schedules, underliers,
  dates, fees, or issuer details. Trigger even if they don't say "extract" —
  "what are the terms of this note", "summarize this pricing supplement",
  "compare these two term sheets", "which of these PDFs has the best coupon",
  or batch processing a folder of offering docs all qualify. Covers autocallable
  notes (phoenix/snowball), contingent yield notes (CYNs), barrier notes,
  accelerated return notes, digital income notes, dual-directional notes, and
  market-linked CDs.
---

# Prospectus Extraction

Extract structured, evidence-grounded terms from structured-product offering
documents. This skill is distilled from the payout-grapher production ingestion
pipeline (`~/dev/payout-grapher`), which pairs LLM extraction with deterministic
validation — it encodes the same field taxonomy, grounding rules, and
cross-checks so extractions are **auditable**, not just plausible-sounding.

## Core principle: no value without evidence

Every extracted value carries at least one **verbatim quote** from the document
with its **page number**. If a term is not stated, the value is `null` and the
evidence list is empty — never guess, never fill in a "typical" value, and never
echo a field label back as its value ("Coupon Barrier" is not a value for
`couponBarrier`). The point: a reviewer must be able to jump from any number to
the exact sentence that justifies it. An extraction without evidence is
indistinguishable from a hallucination, and in this domain a wrong barrier
level is a compliance incident, not a typo.

## Workflow

### 1. Get page-tagged text

```bash
uv run <this-skill-dir>/scripts/pdf_to_pages.py document.pdf pages.txt
```

The bundled script (pypdf via uv, no install needed) writes text with
`[[page N]]` markers so evidence can cite page numbers, uses layout mode so
observation schedules and terms tables keep their columns, and warns on
stderr when pages are near-empty — the signal of a scanned document. It also
whitespace-normalizes the text (strips EDGAR's giant left margins, collapses
space runs to 2) — measured ~53% fewer characters on a real 424B2 with tables
still readable. Quote evidence verbatim from this normalized text. Don't
reach for markitdown here: it was benchmarked and lost — no page boundaries
(so no evidence citations) and mangled terms tables, at a worse size than the
normalized output. If `pdftotext` is installed, `pdftotext -layout doc.pdf -`
also works (pages split on form-feeds, 1-indexed) but skips normalization.

Write the text to a file in the scratchpad and read it in slices rather than
dumping the whole document into context.

For scanned documents, use the OCR path (the `pdf` skill, or `tesseract` if
available). Note in the output that OCR was used: quotes may carry OCR noise,
so match them approximately when verifying, and lower confidence accordingly.

EDGAR HTM-converted filings (424B2s downloaded as PDF) sometimes come out as
one or two giant "pages" — page citations still work but are coarse; say so
in the output rather than inventing printed-page numbers.

### 2. Classify the product type

Scan roughly the first 6 pages (cover + summary are usually enough) against the
keyword table in [references/field-schemas.md](references/field-schemas.md),
then confirm by mechanics. Classify by **mechanics, not marketing name** —
every dealer brands the same structure differently: UBS "Trigger Callable
Contingent Yield Notes" and Morgan Stanley "Contingent Income Auto-Callable
Securities" are both phoenix autocalls (contingent coupon + coupon barrier +
call feature). Within the contingent-coupon family the **call mechanism picks
the type**: automatic trigger call → `phoenix_autocall`; issuer-elective call
→ `phoenix_autocall` with `callType: "issuer"`; no call feature anywhere →
`contingent_yield_note` (see the decision rule in the reference).

If the signals are weak or point at two types, say so and present the
candidates with their evidence instead of picking one silently — extracting
against the wrong schema produces confident nonsense for every field
downstream.

### 3. Extract the fields for that type

Read [references/field-schemas.md](references/field-schemas.md) and extract
**only** the fields defined for the classified product type: the common fields,
the product-specific fields, and the applicable list tables (underliers,
observation schedule). The schema is deliberately closed — a fixed field list
per type is what makes extractions comparable across documents and reviewable
by humans. If the document states a material feature outside the schema
(e.g. a "step return" floor on the upside), record it under `offSchemaTerms`
in the output — with evidence, like any field — rather than inventing a schema
field or silently dropping it.

Fields marked **material** in the schema drive the economics (or compliance)
of the note. A missing material field is a headline warning in your output,
not a silent null.

### 4. Normalize values

| Unit | Convention | Example |
|---|---|---|
| percent | decimal | 30% → `0.30`; 300% participation → `3.0` |
| date | ISO | "June 15, 2027" → `2027-06-15` |
| usd | plain number | $1,000 → `1000` |
| level | raw index/share level | `4327.16` |
| barrier/trigger | fraction **of initial level** | "70% of the Initial Level" → `0.70` (not `-0.30`) |

Keep `rawText` as it appeared in the document alongside `normalizedValue`, so
normalization mistakes are catchable.

Some values are **derived**, not extracted — e.g. term in months from trade
date → maturity date when not stated, or settlement defaulting to cash (cash is
the structured-note default; physical is the explicit exception — only record
`physical` when the text says delivery/in-kind). Report derived values in a
separate `derived` section, never mixed in with evidence-backed fields.

### 5. Cross-check before reporting

Run these deterministic checks — they catch the extraction errors that actually
happen (each one is a bug class the payout-grapher validator was built for):

- **Material fields have evidence.** Any material field that is null or lacks a
  quote → prominent warning.
- **Memory coupon language.** Prospectuses almost never say "memory" — they say
  "plus any previously unpaid Contingent Coupons", "otherwise payable but not
  paid", or give a catch-up formula. If such language exists but you extracted
  `memoryCoupon: false`/null, re-read and fix or flag.
- **Issuer call vs. autocall.** "We may, at our election, redeem" is a
  **discretionary issuer call**; "will be automatically called if the closing
  level is at or above…" is an **automatic** trigger call. Mislabeling this
  breaks any downstream called/not-called logic, because a market level can
  prove an autocall but never an issuer call.
- **Underlier structure consistent with the table.** `underlierStructure` and
  the underliers table must agree: `single` ⇒ exactly one row; `worst_of` ⇒
  ≥2 rows with no weights but per-underlier barrier levels; basket structures
  ⇒ weights present (all equal for `basket_equal_weight`) and summing to
  ~100%, with barriers at the basket level. Extract every reference asset —
  a worst-of note with one underlier extracted is wrong, not incomplete. A
  five-index note can be worst-of or basket and the economics are completely
  different; classify from the payoff language ("worst performing" vs.
  "Basket Return"), never from the asset count.
- **Trade date vs. strike date.** These are separate roles that often share a
  calendar day: `tradeDate` is when the note priced; `strikeDate` is when the
  underliers' initial levels were observed. Capture each role with its own
  evidence. If they **differ** (e.g. a UBS-style Strike Date preceding the
  Trade Date), flag it prominently — every "% of Initial Level" threshold
  keys off the strike date, and schedule math run from the trade date will
  be wrong. If the strike role is unstated, `strikeDate` stays null with a
  derived note, not a copy of the trade date.
- **Fee sanity.** Selling commission + dealer concession + structuring fee
  above ~5%, or estimated initial value outside ~85–100% of par, deserves a
  warning and a re-read of the quotes.
- **Leverage/cap consistency.** Leveraged upside (>100% participation) with no
  cap is unusual — verify the cap really is absent rather than missed.
- **Barrier type.** American/daily-observed barriers are materially riskier
  than European point-to-point — flag them explicitly.
- **Arithmetic consistency.** Per-period coupon × frequency ≈ stated annual
  rate; observation dates fall between trade and maturity; initial level ×
  barrier percent ≈ stated barrier level.

### 6. Output

Always give the human-readable summary. Additionally write the JSON file when
the user asks for structured output, is processing multiple documents, or will
feed the data anywhere programmatic — name it `<pdf-basename>.extraction.json`
next to the source (or where the user says).

When the destination is a **database or Excel**, don't hand-build tables —
flatten the JSON with the bundled exporter:

```bash
python3 <this-skill-dir>/scripts/extraction_to_tables.py out_tables/ *.extraction.json
```

It emits tidy relational CSVs keyed by `document_id` (`documents`, `fields`,
`underliers`, `observation_schedule`, `off_schema_terms`, `findings`), so a
whole folder of prospectuses lands in one set of files that import directly
into Excel, SQLite, or pandas. Evidence page+quote ride along in every row,
and derived values appear in `fields.csv` with `source=derived` so nobody
mistakes a computed term-length for a stated one. If the user wants a single
`.xlsx` workbook, build it from these CSVs (one sheet per table) with the
`xlsx` skill.

**Markdown summary** — lead with identity (issuer, type, underlier(s), CUSIP,
term), then the economics grouped as the schema groups them (economics /
downside / dates / fees), then the observation/coupon calendar (next
paragraph), then **warnings and missing material fields last and loud**. Cite
pages inline like `(p.3)`.

**Observation/coupon calendar** — whenever the note observes or pays over time
(any coupon-bearing or callable type), render the calendar **in chat** as a
markdown table, one row per date the document enumerates:

| # | Observation date | Payment date | Coupon | Call level | Call premium |
|---|---|---|---|---|---|

Drop columns that are entirely null — a non-callable income note has no call
columns, and an issuer-elective call note has notice-based redemption dates
rather than trigger levels (table those dates and label them as
issuer-elective). This calendar is usually the single most-used artifact of
the whole extraction — it's what cashflow dates get checked against — so
render every enumerated row; 36 monthly rows is a normal, useful table, not
clutter to summarize away as "monthly for 3 years". Only when the schedule
runs past ~50 rows compress to cadence + the first few and final rows in
chat, and point at `observation_schedule.csv` for the full set. If the
document states only a frequency with start/end dates and never enumerates
the dates, don't fabricate them — state the cadence and note that the real
dates embed business-day adjustments the document didn't print.

**JSON shape** (mirrors the payout-grapher contract, so it can be diffed or
imported):

```json
{
  "documentType": "final pricing supplement | preliminary pricing supplement | term sheet | ...",
  "productType": "phoenix_autocall",
  "classification": { "confidence": "high|medium|low", "signals": ["quoted phrases that drove the call"] },
  "fields": {
    "couponRate": {
      "rawText": "10.00% per annum",
      "normalizedValue": 0.10,
      "unit": "percent",
      "confidence": 0.97,
      "evidence": [{ "page": 2, "quote": "Contingent Coupon Rate: 10.00% per annum" }],
      "warnings": []
    }
  },
  "tables": {
    "underliers": [{ "values": { "symbol": "RTY", "name": "Russell 2000 Index", "initialLevel": 2038.32, "knockInLevel": 1426.82, "couponBarrierLevel": 1426.82, "protectionLevel": null, "weight": null }, "evidence": [{ "page": 2, "quote": "..." }] }],
    "observationSchedule": [{ "values": { "observationDate": "2026-09-15", "autocallLevel": 1.0, "couponBarrierLevel": 0.70, "couponAmount": 0.025, "callPremium": null, "paymentDate": "2026-09-18" }, "evidence": [{ "page": 4, "quote": "..." }] }]
  },
  "derived": { "termMonths": { "value": 36, "from": "tradeDate → maturityDate" } },
  "findings": [{ "severity": "blocking|warning|info", "field": "knockInLevel", "message": "..." }]
}
```

## Traps that produce wrong extractions

- **Preliminary documents have placeholders.** "$____ per Note", "expected to
  be between 9.00% and 11.00%", "will be set on the Trade Date". Record what is
  actually stated (a range is a range, a blank is null), set `documentType` to
  preliminary, and warn that terms are indicative.
- **"Coupon Barrier: 70.00% of the Initial Level" appears twice** — once as a
  percent, once as an absolute level per underlier. Capture the percent in the
  scalar field and the absolute level in the underliers table; they must be
  consistent with each other.
- **Estimated initial value ≠ price to public.** The estimated initial value
  (issuer's model value, typically 90–99% of par) is a fee-transparency
  disclosure. Don't confuse it with the 100% issue price.
- **The same date has many names — map by role, not label.** Settlement ≈
  original issue date; final observation ≈ final valuation ≈ final
  determination date; strike ≈ initial valuation ≈ pricing/determination date
  when listed separately from the trade date. "Determination Date" is
  especially treacherous: it names the *initial* strike in some programs and
  the *final* observation in others — decide from what the date is used for,
  and quote the document's own label in `rawText`.
- **Risk-factor sections restate terms hypothetically** ("if the barrier were
  60%…"). Prefer quotes from the terms/summary tables on the cover pages; a
  quote from a risk factor or hypothetical-returns table is weak evidence.
- **Long observation schedules.** Quarterly observations on a 5-year note = 20
  rows. Extract all of them (the payment-date column too); don't summarize as
  "quarterly" when an explicit table exists — downstream date logic needs the
  actual dates, which embed holiday adjustments you can't reproduce.

## When done

If the extraction fed a decision (approve/compare/book), remind the user which
findings were warnings vs. blocking-grade, and that null-with-no-evidence means
"not stated in the document", not "zero".
