# troubleshoot — analyze Bloomberg API errors and recommend fixes

## Purpose
Take a stack trace, error message, or misbehavior description and produce a
diagnosis + concrete fix, using the taxonomy in references/error-handling.md.

## Expected inputs
The error text / trace / symptom, ideally with the request that caused it
(securities, fields, options) and where the code runs (desktop? server?).

## Decision tree
```text
Can't connect / start() fails?
├─ Terminal running & logged in on THIS machine? → start it
├─ Running on a server/container/CI? → DAPI can't do that; SAPI/B-PIPE or
│  re-architect (mocks in CI — references/testing.md)
└─ Port 8194 reachable? firewall/bbcomm → restart Terminal

Request sent, no data?
├─ TIMEOUT event → timeout too low? Terminal hung? health-check ping
├─ Only SOME securities returned → partial responses dropped (client bug)
└─ responseError → read category: BAD_ARGS (fix request) | limits (STOP, don't retry)

Data present but wrong/missing pieces?
├─ securityError per security → identifier resolution (references/identifiers.md)
├─ fieldExceptions BAD_FLD → invalid/inapplicable field (references/field-guide.md)
├─ entitlement wording → BloombergEntitlementError: report exactly what's
│  not permissioned; the fix is a Bloomberg rep, not code
└─ numbers "off" → adjusted vs unadjusted; price vs TR index; GBp; venue ticker

Subscription issues?
└─ SUBSCRIPTION_STATUS failure → field not realtime, or realtime not entitled
```

## Output format
1. **Diagnosis** — one sentence naming the failure class
2. **Evidence** — which part of the message/trace says so
3. **Fix** — code or action, referencing the pattern to adopt
4. **Prevention** — the checklist item that would have caught it

## Example
"My batch returns 60 of 100 securities, no errors" → partials dropped:
the loop exits on the first event instead of accumulating until `RESPONSE`
→ adopt the `_collect` loop from examples/reference_data.py.

## Pitfalls
- Retrying limit errors (makes it worse)
- Blaming entitlements for identifier typos (BAD_SEC ≠ permission denied)
- "Fixing" wrong numbers by switching fields instead of checking
  adjustment/index-variant semantics
