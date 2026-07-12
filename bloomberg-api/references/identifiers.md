# Security identifiers

## Ticker anatomy

```text
  RTY        Index          ← "<ticker> <yellow key>" (indices, curncy, cmdty)
  IBM   US   Equity         ← "<ticker> <exchange> <yellow key>"
  └──┬──┘└┬┘ └───┬───┘
   ticker exch  yellow key
```

**Yellow keys**: `Equity`, `Index`, `Curncy`, `Comdty`, `Govt`, `Corp`,
`Mtge`, `M-Mkt`, `Muni`, `Pfd`. Every terminal-style identifier ends in one.

**Composite vs venue exchange codes**: `IBM US Equity` is the US *composite*
(consolidated tape); `IBM UN Equity` is NYSE specifically, `IBM UW` Nasdaq.
Prefer the composite unless a venue-specific price is contractually required.
Same instrument cross-listed (e.g. `US` vs `LN`) = different prices and
currencies — pick deliberately.

## Prefixed identifier forms

blpapi accepts identifier-scheme prefixes in the securities list:

| Form | Example |
|---|---|
| `/ticker/` | `/ticker/IBM US Equity` (same as bare) |
| `/cusip/` | `/cusip/459200101` |
| `/isin/` | `/isin/US4592001014` |
| `/sedol/` | `/sedol/2005973` |
| `/bbgid/` | `/bbgid/BBG000BLNNH6` (FIGI) |

CUSIP/ISIN/SEDOL for a cross-listed equity resolve to a default venue — pin
the exchange when it matters (`/isin/US4592001014@US`, or resolve to a ticker
first and keep the ticker).

## Preferred hierarchy

Resolve once, store the strongest identifier you have, echo the resolved
ticker back into your records:

1. **FIGI / `bbgid`** — unambiguous, venue-level, free-standard; best for storage
2. **ISIN + explicit exchange** — strong, but venue-default trap without the exchange
3. **CUSIP** (North America) — same caveat
4. **Composite ticker** (`IBM US Equity`) — human-friendly, stable enough
5. **Venue ticker** (`IBM UN Equity`) — only when a specific venue is required
6. **Display name** — never send to the API; map first (below)

For notes themselves (the structured products): the CUSIP/ISIN from the
prospectus identifies the *note*; the underliers need their own resolution.

## Display names are not tickers

Prospectuses (and the `prospectus-extraction` skill's output) carry display
names and informal symbols. Maintain an explicit mapping table — never
string-munge:

| Prospectus name | Bloomberg |
|---|---|
| S&P 500 Index | `SPX Index` |
| Nasdaq-100 Index | `NDX Index` |
| Russell 2000 Index | `RTY Index` (⚠ not RUT — that's the Yahoo/CBOE symbol) |
| Dow Jones Industrial Average | `INDU Index` |
| EURO STOXX 50 Index | `SX5E Index` |
| FTSE 100 Index | `UKX Index` |
| Nikkei Stock Average / Nikkei 225 | `NKY Index` |
| Swiss Market Index | `SMI Index` |
| S&P/ASX 200 Index | `AS51 Index` |
| SPDR S&P Regional Banking ETF | `KRE US Equity` |
| Common stock "XYZ" | resolve via `/isin/` or `/cusip/` from the doc |

Keep the mapping provider-aware (`RTY Index` for Bloomberg vs `^RUT` for
Yahoo) so a `MarketDataProvider` swap doesn't corrupt symbols. Unknown name →
fail loudly and ask; a wrong-but-resolvable guess (RUT/RTY, price vs
total-return variants like `SPXT Index`) produces plausible wrong numbers,
which is worse than an error.

## Pitfalls

- **Total-return vs price-return indices**: `SPX Index` (price) vs
  `SPXT Index` (TR). Notes almost always reference the price index; a TR
  ticker inflates every observation.
- **GBp**: LSE equities quote in pence; `CRNCY` says `GBp`. Mixed-currency
  basket math must normalize.
- **Ticker reuse/changes**: corporate actions rename tickers; FIGI survives.
  For historical fixings of a renamed security, FIGI or ISIN resolution is
  the reliable path.
- **`Corp` vs `Mtge` yellow keys** for the note itself when looking up the
  issuer's paper — structured notes typically sit under `Corp`.
