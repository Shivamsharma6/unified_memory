---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:36:03.153626+00:00'
tags:
- '#cloud-functions'
- '#backup'
- '#firestore'
- '#callable'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
Implemented a manual trigger for Firestore backups via the manualFirestoreBackup HTTP Callable function. The function exports all collections to the sentri-ban2r1-backups-asia bucket using the FirestoreAdminClient.exportDocuments method. Unlike the scheduled version, this implementation explicitly throws an HttpsError("internal") on failure to ensure proper error reporting to the client SDK.

## Raw Logs
# Function: `manualFirestoreBackup` (Lines 1051-1067)

## Summary
# Function: `manualFirestoreBackup` (Lines 1051-1067)

**Type:** 🔗 HTTP Callable (`onCall`)
**Signature:** `https` (callable)
**URL:** `https://us-central1-sentri-ban2r1.cloudfunctions.net/manualFirestoreBackup`

**What it does:** Identical to `scheduledFirestoreBackup` but triggered manually via Firebase callable function from client SDK.

**Parameters:** None (no data required).

**Database operations:**
- **Firestore (gRPC):** `FirestoreAdminClient.exportDocuments()` — all collections → `gs://sentri-ban2r1-backups-asia/db_backups/`

**Side effects:** Long-running async export. Returns `{success: true, operationName}`.

**Error handling:** Throws `HttpsError("internal", err.message)` on failure (unlike scheduled which returns null).

**Client usage:**
```js
const manualBackup = httpsCallable(functions, 'manualFirestoreBackup');
await manualBackup();
```