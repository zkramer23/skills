# /validate-fields — review Bloomberg fields for correctness

## Purpose
Audit a list of field mnemonics (in code, a config, or a request) for
validity, applicability, and *semantic* fit — the dangerous errors are valid
fields that mean the wrong thing.

## Expected inputs
- The fields, with the security types they'll be requested for
- What the numbers will be used for (fixings? display? analytics?)

## Steps
1. Check each mnemonic against references/field-guide.md; flag unknowns and
   likely typos (`PX_LAST_PRICE` → `PX_LAST`).
2. Check **applicability**: equity-only fields on indices, bond fields on
   equities → predictable `BAD_FLD` fieldExceptions.
3. Check **semantics against the stated use**:
   - fixings/observations ↔ `PX_OFFICIAL_CLOSE` (not `PX_LAST`)
   - price vs total-return intent ↔ index choice, adjustment flags
   - realtime-only fields in request contexts (and vice versa)
4. Check bulk fields are parsed as arrays, and overrides they may need.
5. For anything not in the guide, say "verify in `FLDS <GO>` on a loaded
   security" — don't invent mnemonics.

## Output format
A table: `field | status (ok / unknown / inapplicable / wrong-for-purpose) |
recommendation`, followed by the corrected field list.

## Example
Input: `PX_LAST, PX_OFFCL_CLOSE, DVD_HIST_ALL` for index fixings →
`PX_OFFCL_CLOSE` typo → `PX_OFFICIAL_CLOSE`; `DVD_HIST_ALL` inapplicable to
indices; recommend official close for the fixing use.

## Pitfalls
- Approving fields that "exist" without checking the use case
- Missing that a field needs an override to mean what the user thinks
- Letting `BAD_FLD`-on-some-securities pass silently as applicability drift
