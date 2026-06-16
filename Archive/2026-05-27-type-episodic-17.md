---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:38:55.881256+00:00'
tags:
- '#cloud-functions'
- '#active-cards'
- '#callable'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
Identified redundancy between the rebuildActiveCardsCsv and rebuildActiveCards callable endpoints, as both perform identical actions to trigger a full active-cards CSV rebuild for a single business. The rebuildActiveCardsCsv function validates that a businessId parameter is provided, throwing an HttpsError("invalid-argument") if missing before delegating to rebuildActiveCardsCsvForBusiness(businessId). Actionable: Consolidate these duplicate endpoints to reduce technical debt.

## Raw Logs
# Function: `rebuildActiveCardsCsv` (Lines 897-906)

## Summary
# Function: `rebuildActiveCardsCsv` (Lines 897-906)

**Type:** 🔗 HTTP Callable (`onCall`)
**Signature:** `https` (callable)
**URL:** `https://us-central1-sentri-ban2r1.cloudfunctions.net/rebuildActiveCardsCsv`

**What it does:** Callable endpoint that triggers a full rebuild of active-cards CSV for a single business. **Identical to `rebuildActiveCards`** (duplicate).

**Parameters:** `{ businessId: string }` — throws `HttpsError("invalid-argument", "Missing businessId")` if omitted.

**Client usage:**
```js
const rebuild = httpsCallable(functions, 'rebuildActiveCardsCsv');
await rebuild({ businessId: 'some-business-id' });
```

**Database operations:** Delegates to `rebuildActiveCardsCsvForBusiness(businessId)` — see core pipeline entry.

**Note:** Duplicate of `rebuildActiveCards` — both callable endpoints do the exact same thing.