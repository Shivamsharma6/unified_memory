---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:36:36.268929+00:00'
tags:
- '#cloud-functions'
- '#access-logs'
- '#firestore-trigger'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Function: `onAccessLogsWrite` (Lines 850-866)

## Summary
# Function: `onAccessLogsWrite` (Lines 850-866)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/access_logs/access_logs`
**Signature:** `cloudevent`

**What it does:** Watches for writes to the pending access-logs document. ... [Distilled] ... **Database operations:**
- **Firestore (read):** `businessess/{bizId}/access_logs/access_logs` — reads `logs` array field
- **Firestore (read):** `businessess/{bizId}/cards/` — `where("card_data", "in", [...])` chunks of 30 (card-to-entity lookup, results cached in `globalCardAssignmentCache`)
- **Firestore (write):** `businessess/{bizId}/access_logs/ACCESS_LOGS_NNNN` — one doc per row via **Firestore transaction** (uses `next_id_LOGS` on business doc for sequence safety)
- **Firestore (write):** `businessess/{bizId}/access_logs/access_logs` — resets `{ logs: [] }` after processing

**Key detail:** Uses `globalCardAssignmentCache` (cross-execution cache) for card-to-entity lookups, avoiding redundant Firestore reads across invocations.

## Raw Logs
# Function: `onAccessLogsWrite` (Lines 850-866)

## Summary
# Function: `onAccessLogsWrite` (Lines 850-866)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/access_logs/access_logs`
**Signature:** `cloudevent`

**What it does:** Watches for writes to the pending access-logs document. When new raw logs are pushed (batch append), reads them, maps each row to a card-to-entity lookup (using `globalCardAssignmentCache`), and dispatches to `processAccessLogsForBusiness()` to write into individual `ACCESS_LOGS_NNNN` documents.

**Trigger:** Fires when a POS device pushes a new batch of access log rows into the central doc.

**Database operations:**
- **Firestore (read):** `businessess/{bizId}/access_logs/access_logs` — reads `logs` array field
- **Firestore (read):** `businessess/{bizId}/cards/` — `where("card_data", "in", [...])` chunks of 30 (card-to-entity lookup, results cached in `globalCardAssignmentCache`)
- **Firestore (write):** `businessess/{bizId}/access_logs/ACCESS_LOGS_NNNN` — one doc per row via **Firestore transaction** (uses `next_id_LOGS` on business doc for sequence safety)
- **Firestore (write):** `businessess/{bizId}/access_logs/access_logs` — resets `{ logs: [] }` after processing

**Key detail:** Uses `globalCardAssignmentCache` (cross-execution cache) for card-to-entity lookups, avoiding redundant Firestore reads across invocations.