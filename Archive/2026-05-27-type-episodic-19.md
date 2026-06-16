---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:39:17.966333+00:00'
tags:
- '#cloud-functions'
- '#active-cards'
- '#firestore-trigger'
- '#rtdb'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
Function syncActiveCardsCsvVersion bridges Firestore and RTDB to manage POS client cache invalidations. It triggers on writes to the active_cards_csv sub-document, parses the updated_at timestamp from Firestore (handling Timestamp, Date, or string types), and writes it as an ISO string to sentri/active_cards_version/{businessId} in RTDB. The function also handles deletions by removing the corresponding RTDB entry. This mechanism ensures POS terminals can detect data changes via version tokens.

## Raw Logs
# Function: `syncActiveCardsCsvVersion` (Lines 999-1028)

## Summary
# Function: `syncActiveCardsCsvVersion` (Lines 999-1028)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/active_cards/active_cards_csv`
**Signature:** `cloudevent`

**What it does:** Watches for writes to the `active_cards_csv` sub-document. When the CSV is written (by `rebuildActiveCardsCsvForBusiness`), this function **syncs the version token to RTDB** — writing the `updated_at` timestamp as an ISO string to `sentri/active_cards_version/{businessId}`.

**Algorithm:**
1. Read `after.data().updated_at` from the Firestore document
2. Parse the timestamp (handles Firestore `Timestamp`, native `Date`, or string)
3. Write ISO string to RTDB: `sentri/active_cards_version/{businessId}` → `{ <ISO timestamp> }`
4. If document deleted (`!after.exists`), **remove** the RTDB entry

**Database operations:**
- **Firestore (read):** `businessess/{bizId}/active_cards/active_cards_csv` — reads `updated_at` field
- **RTDB (write):** `sentri/active_cards_version/{businessId}` — `{ <ISO timestamp> }`
- **RTDB (delete):** `sentri/active_cards_version/{businessId}` — removes entry if Firestore doc deleted

**Key detail:** This is the **bridge** between Firestore (source of truth) and RTDB (POS client cache invalidation). The version token is what POS terminals use to detect changes and re-fetch.

**Called by:** `writeActiveCardsCsvForBusiness()` (internal utility).