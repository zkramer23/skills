# BQL — what it is, and what not to promise

**BQL (Bloomberg Query Language)** is Bloomberg's analytical query language:
declarative, server-side, with screening, grouping, and point-in-time
semantics. It looks like this:

```text
get(px_last) for(['SPX Index','RTY Index'])
get(avg(group(px_last, gics_sector_name))) for(members('SPX Index'))
```

## Where BQL actually runs

| Surface | Available? |
|---|---|
| Excel `=BQL(...)` | ✅ (Terminal license) |
| BQNT (Bloomberg's hosted Jupyter) | ✅ (`bql` Python package, BQNT-only) |
| Terminal (`BQLX <GO>` etc.) | ✅ |
| **Public desktop `blpapi` SDK** | ❌ not an official request type |

The `bql` Python package that BQNT notebooks use is **not distributable** and
does not run against the Desktop API. Do not generate code that
`import bql` outside BQNT, and do not wire "BQL over blpapi" via undocumented
service names — it's unsupported, entitlement-fragile, and an audit problem.

## What to do instead (translation table)

| BQL idea | Desktop API equivalent |
|---|---|
| `get(px_last) for([...])` | `ReferenceDataRequest` |
| `get(px_last(dates=range(...)))` | `HistoricalDataRequest` |
| `for(members('SPX Index'))` | `ReferenceDataRequest` bulk field `INDX_MEMBERS`, then a second request over the members |
| screening (`filter(...)`) | run the screen on the Terminal (`EQS`), export, feed the result list to the API |
| grouped aggregates | pull rows via blpapi, aggregate in Polars |

The pattern for "BQL-ish" needs on DAPI is always: **fetch flat data with
refdata requests, compute in Polars**. That keeps the Bloomberg boundary thin
and the analytics testable offline.

## When BQL is genuinely the right tool

- The user works in Excel and wants a live sheet → `=BQL()` there, not Python.
- The analysis needs Bloomberg-side point-in-time universes (index membership
  *as of* past dates) that DAPI can't reconstruct cheaply → BQNT is the
  honest answer; say so rather than approximating silently.
