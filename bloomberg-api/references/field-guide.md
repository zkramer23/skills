# Field guide

Fields are mnemonics validated per security type. The authoritative source is
the Terminal: `FLDS <GO>` on a loaded security searches every field with live
values. When unsure, ask the user to confirm in FLDS rather than guessing —
an invalid field costs a fieldException; a *wrong-but-valid* field costs a
silent bad number.

## Core price/identity fields

| Field | Meaning | Notes |
|---|---|---|
| `PX_LAST` | Last price | live-ish; in historical requests = daily close series |
| `PX_OFFICIAL_CLOSE` | Official closing level | **use for fixings/observations** |
| `PX_CLOSE_1D` | Prior close | snapshot convenience |
| `PX_BID` / `PX_ASK` | Quotes | realtime-entitled |
| `LAST_UPDATE_DT` | Date of last price | staleness checks |
| `CRNCY` | Trading currency | watch GBp (pence) vs GBP |
| `SECURITY_NAME` / `NAME` | Descriptive name | display |
| `TICKER`, `EXCH_CODE` | Parsed identifier parts | round-tripping |
| `ID_ISIN`, `ID_CUSIP`, `ID_SEDOL1`, `ID_BB_GLOBAL` | Cross identifiers | build mapping tables |
| `SECURITY_TYP`, `MARKET_SECTOR_DES` | Type / yellow key | routing logic |

## Issuer / credit fields (issuer-approval workflows)

| Field | Meaning |
|---|---|
| `ISSUER` | Issuer name |
| `ULT_PARENT_TICKER_EXCHANGE` | Ultimate parent |
| `RTG_MOODY`, `RTG_SP`, `RTG_FITCH` | Senior ratings |
| `CDS_SPREAD_TICKER_5Y` | Related CDS (coverage varies) |
| `COUNTRY_ISO` | Country of issuer |

## Bulk fields (arrays in fieldData)

| Field | Rows | Use |
|---|---|---|
| `DVD_HIST_ALL` | dividend history (ex-date, type, amount) | corporate-action review for share-linked notes |
| `INDX_MEMBERS` (+`INDX_MWEIGHT`) | index constituents | index composition; **not** note baskets — those come from the prospectus |
| `OPT_CHAIN` | option tickers | vol/hedging analysis |
| `CALL_SCHEDULE` | bond call schedule | callable paper |

Bulk fields often accept overrides (e.g. `DVD_START_DT`/`DVD_END_DT` to bound
dividend history).

## Overrides

Overrides change the *as-of* or assumptions of a field. Common ones:

| Override fieldId | Effect |
|---|---|
| `END_DATE_OVERRIDE` (yyyymmdd) | value as of a past date for many fields |
| `EQY_FUND_CRNCY` | currency-translate fundamental fields |
| `SETTLE_DT` | bond settlement-dependent analytics |
| `BEST_FPERIOD_OVERRIDE` | estimate period selection (BEst fields) |

Overrides are (fieldId, string value) pairs appended to
`request.getElement("overrides")` — see request-types.md. Log overrides with
the request; two identical-looking requests with different overrides are a
classic source of "the numbers changed" tickets.

## Field exceptions

Per-security, per-field failures inside a successful response:

```text
fieldExceptions[] → { fieldId, errorInfo { category, subcategory, message } }
```

Typical categories: `BAD_FLD` (invalid/inapplicable mnemonic — a typo or an
equity field on an index) and entitlement denials (field exists, you can't
have it). Treat `BAD_FLD` on *every* security as a coding bug; on *some*
securities as an applicability gap (model it — don't request equity-only
fields for indices).

## Static vs realtime

Request fields (`PX_LAST` via refdata) are point-in-time snapshots. The same
mnemonic may exist as a subscription field (`LAST_PRICE` on mktdata) with
different entitlement. Never assume a field that works in a
ReferenceDataRequest is subscribable, or vice versa.

## Structured-products field selection rules

1. Observation/fixing levels → `PX_OFFICIAL_CLOSE` via HistoricalDataRequest,
   unadjusted (see request-types.md), labeled **indicative** — the
   contractual fixing is the calculation agent's.
2. Live "where is it now vs barrier" → `PX_LAST`, clearly marked intraday
   indicative.
3. FX for quanto/composite baskets → the note defines the fixing source
   (WM/Reuters 4pm etc.); Bloomberg `<ccy1><ccy2> Curncy` closes are again
   indicative.
4. ETF underliers (e.g. `KRE US Equity`) distribute dividends — coupon/barrier
   math uses price levels, not total-return, unless the note says otherwise.
