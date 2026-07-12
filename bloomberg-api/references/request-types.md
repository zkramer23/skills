# Request types and when to use each

| Need | Request | Notes |
|---|---|---|
| Snapshot of fields as-of now | `ReferenceDataRequest` | many securities × many fields, overrides, bulk fields |
| Daily/weekly/monthly series | `HistoricalDataRequest` | many securities, few fields, date range |
| Minute bars | `IntradayBarRequest` | **one security per request**, 1–1440 min bars |
| Raw ticks | `IntradayTickRequest` | one security, ~140-day lookback limit |
| Live streaming | Subscription (`//blp/mktdata`) | conflatable; entitlement-sensitive |

All request objects come from the service:
`service.createRequest("ReferenceDataRequest")`.

## ReferenceDataRequest

```python
req = service.createRequest("ReferenceDataRequest")
for s in securities:
    req.getElement("securities").appendValue(s)      # e.g. "RTY Index"
for f in fields:
    req.getElement("fields").appendValue(f)          # e.g. "PX_LAST"

# overrides: pairs of (fieldId, value) — values are strings
ovr = req.getElement("overrides").appendElement()
ovr.setElement("fieldId", "END_DATE_OVERRIDE")
ovr.setElement("value", "20260611")
```

- Response: `securityData[]` array (see blpapi-patterns.md anatomy).
- Bulk fields (e.g. `DVD_HIST_ALL`, `INDX_MEMBERS`) come back as arrays in
  `fieldData` — one sub-element per row.
- Batch limits are generous but unpublished; stay ≤100 securities / ≤25
  fields per request and split above that.

## HistoricalDataRequest

```python
req = service.createRequest("HistoricalDataRequest")
req.getElement("securities").appendValue("RTY Index")
req.getElement("fields").appendValue("PX_LAST")
req.set("startDate", "20260101")            # yyyymmdd strings
req.set("endDate",   "20260611")
req.set("periodicitySelection", "DAILY")    # DAILY | WEEKLY | MONTHLY | QUARTERLY | YEARLY
```

Options that matter (and their defaults):

| Element | Values | Use |
|---|---|---|
| `nonTradingDayFillOption` | `NON_TRADING_WEEKDAYS` \| `ALL_CALENDAR_DAYS` \| `ACTIVE_DAYS_ONLY` (default) | whether holidays produce rows |
| `nonTradingDayFillMethod` | `PREVIOUS_VALUE` \| `NIL_VALUE` | what a filled row contains |
| `adjustmentSplit` / `adjustmentNormal` / `adjustmentAbnormal` | bool | corporate-action adjustment of prices |
| `adjustmentFollowDPDF` | bool (default true) | inherit the terminal's DPDF setting |
| `currency` | ISO code | FX-translate prices |

**Structured-products default: adjustments OFF, explicitly.** Barrier and
fixing checks compare against levels struck in the past; adjusted series
rewrite those levels. Set `adjustmentFollowDPDF=False` and the three
adjustment flags `False` so results don't silently depend on the terminal
user's DPDF settings. (Use adjusted series only when the note's own terms
adjust — e.g. share-linked notes with dilution-adjustment clauses.)

- Response: **one message per security**; each has `securityData` (not an
  array) with `fieldData[]` = one element per date.
- Observation-date processing: request the full date range once and filter to
  the schedule locally — cheaper than one request per date.

## IntradayBarRequest

```python
req = service.createRequest("IntradayBarRequest")
req.set("security", "RTY Index")                     # exactly one
req.set("eventType", "TRADE")                        # TRADE | BID | ASK
req.set("interval", 5)                               # minutes, 1–1440
req.set("startDateTime", blpapi.Datetime(2026, 6, 11, 13, 30))
req.set("endDateTime",   blpapi.Datetime(2026, 6, 11, 20, 0))
```

- Times are **UTC**. Convert deliberately; a fixing window in New York is
  UTC-4/UTC-5 depending on DST.
- Response: `barData/barTickData[]` with `time, open, high, low, close,
  volume, numEvents`.

## IntradayTickRequest

Same shape as bars minus `interval`; `eventTypes` is a list (TRADE, BID, ASK,
…), optional `includeConditionCodes`. History limited to roughly 140 days.
Rarely needed for structured products — closing levels drive lifecycle events;
ticks are for execution/disruption forensics.

## Choosing for structured-product tasks

| Task | Request |
|---|---|
| Initial fixing / final valuation on a known date | `HistoricalDataRequest` (1-day range, unadjusted) |
| All observation levels for a schedule | `HistoricalDataRequest` (strike→today), filter to dates |
| Current indicative levels for a live note | `ReferenceDataRequest` (`PX_LAST`, `PX_OFFICIAL_CLOSE`) |
| Issuer metadata / ratings | `ReferenceDataRequest` |
| Dividend/corporate-action history | `ReferenceDataRequest` with bulk field `DVD_HIST_ALL` |
| Around-the-fixing forensics (disruption day) | `IntradayBarRequest` |
