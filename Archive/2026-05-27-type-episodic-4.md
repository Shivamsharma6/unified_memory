---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:35:55.233895+00:00'
tags:
- '#cloud-functions'
- '#backup'
- '#firestore'
- '#scheduled'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
The scheduledFirestoreBackup function is configured to run daily at 03:00 AM IST to export the entire Firestore (default) database to a designated GCS bucket. It utilizes the @google-cloud/firestore v1 AdminClient for long-running, idempotent exports of all collections. Error handling is implemented to log failures and return null without throwing exceptions. A critical operational requirement is ensuring the service account possesses the datastore.importExportAdmin IAM permission.

## Raw Logs
# Function: `scheduledFirestoreBackup` (Lines 1030-1049)

## Summary
# Function: `scheduledFirestoreBackup` (Lines 1030-1049)

**Type:** ⏰ Scheduled (Cron)
**Schedule:** `0 3 * * *` (03:00 AM IST, daily)
**Signature:** `http` (CloudEvent)
**Path:** N/A (scheduler-triggered)

**What it does:** Exports the entire Firestore `(default)` database to GCS bucket `gs://sentri-ban2r1-backups-asia/db_backups/` using `FirestoreAdminClient.exportDocuments()`.

**Database operations:**
- **Firestore (gRPC):** `FirestoreAdminClient.exportDocuments({name: databaseName, outputUriPrefix: BACKUP_BUCKET, collectionIds: []})` — exports ALL collections (empty array = all).

**Side effects:** Long-running async export operation. Operation name logged. Idempotent — safe to run while previous export is in progress.

**Error handling:** Catches and logs errors, returns `null` on failure (no throw).

**Key detail:** Uses `@google-cloud/firestore` v1 `FirestoreAdminClient` (not regular Firestore SDK). Requires IAM `datastore.importExportAdmin` on the service account.