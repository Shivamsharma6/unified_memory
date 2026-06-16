---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:38:49.319179+00:00'
tags:
- '#cloud-functions'
- '#active-cards'
- '#callable'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
Function rebuildActiveCards (Lines 886-895) is a duplicate of rebuildActiveCardsCsv, triggering a full active-cards CSV rebuild for a specific business. It requires a businessId parameter and throws an HttpsError("invalid-argument") if omitted. The core logic is delegated to rebuildActiveCardsCsvForBusiness(businessId).

## Raw Logs
# Function: `rebuildActiveCards` (Lines 886-895)

## Summary
# Function: `rebuildActiveCards` (Lines 886-895)

**Type:** 🔗 HTTP Callable (`onCall`)
**Signature:** `https` (callable)
**URL:** `https://us-central1-sentri-ban2r1.cloudfunctions.net/rebuildActiveCards`

**What it does:** Callable endpoint that triggers a full rebuild of active-cards CSV for a single business. Same as `rebuildActiveCardsCsv` (duplicate).

**Parameters:** `{ businessId: string }` — throws `HttpsError("invalid-argument", "Missing businessId")` if omitted.

**Client usage:**
```js
const rebuild = httpsCallable(functions, 'rebuildActiveCards');
await rebuild({ businessId: 'some-business-id' });
```

**Database operations:** Delegates to `rebuildActiveCardsCsvForBusiness(businessId)` — see core pipeline entry.

**Note:** Duplicate of `rebuildActiveCardsCsv` — both callable endpoints do the exact same thing.