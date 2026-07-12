# /fetch-reference — generate a ReferenceDataRequest

## Purpose
Produce production-ready code (or run it, if a Terminal is present) for a
point-in-time snapshot of fields across securities.

## Expected inputs
- Securities: any mix of tickers, display names, CUSIPs, ISINs
- Fields: mnemonics, or a plain-English description of what's wanted
- Optional: overrides (as-of date, currency)

## Steps
1. **Resolve identifiers first** (references/identifiers.md). Display names →
   mapping table; CUSIP/ISIN → `/cusip/`, `/isin/` forms. Unknown names: ask,
   don't guess.
2. **Choose fields** via references/field-guide.md; if the user described the
   data in English, propose mnemonics and note any to verify in `FLDS`.
3. Confirm a snapshot is right — if the user needs values on past dates, this
   is `/fetch-history` instead (or `END_DATE_OVERRIDE` for a single as-of).
4. Generate code on the `BlpapiClient.get_reference` pattern
   (examples/reference_data.py): batched, partial-safe, error frame returned.

## Output format
One request for all securities/fields. Return `RefResult(data, errors)`:
long-format Polars frame (`security | field | value`) plus a structured error
frame. Show the user both.

## Example
"Get last price, currency, and name for the Citi note's underliers" →
resolve (NDX Index, RTY Index, KRE US Equity) → fields
`PX_LAST, CRNCY, SECURITY_NAME` → one request, 3×3 result frame.

## Pitfalls
- Per-security request loops (batch instead)
- Sending display names raw ("Russell 2000 Index" is not a ticker)
- Ignoring `fieldExceptions` — the frame looks fine, a field is just missing
- `PX_LAST` when the workflow needs `PX_OFFICIAL_CLOSE` semantics
