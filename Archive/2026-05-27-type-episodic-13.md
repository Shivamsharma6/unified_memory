---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:38:23.569511+00:00'
tags:
- '#cloud-functions'
- '#active-cards'
- '#firestore-trigger'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
The onCardWrite function triggers a full CSV rebuild (rebuildActiveCardsCsvForBusiness) whenever a card document in the businesses/{businessId}/cards/ path is modified. This design decision was made because card data serves as the primary key for POS devices, necessitating a complete refresh of the active-cards CSV. The operation involves reading business and card data from Firestore, then writing the updated CSV string to Firestore and an ISO timestamp to RTDB. Note that this function executes with high frequency, as every creation, update, or deletion initiates a full rebuild.

## Raw Logs
# Function: `onCardWrite` (Lines 808-816)

## Summary
# Function: `onCardWrite` (Lines 808-816)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/cards/{cardId}`
**Signature:** `cloudevent`

**What it does:** Watches for any write to a card document. Triggers `rebuildActiveCardsCsvForBusiness(businessId)` — because card data (the string that POS devices use to identify cards) is the primary key in the active-cards CSV.

**Database operations:**
- **Firestore (read):** `businessess/{bizId}`, `businessess/{bizId}/cards/` (full rebuild via `rebuildActiveCardsCsvForBusiness`)
- **Firestore (write):** `businessess/{bizId}/active_cards/active_cards_csv` — `{ cards: <csv_string>, updated_at: serverTimestamp }`
- **RTDB (write):** `sentri/active_cards_version/{businessId}` — `{ <ISO timestamp> }`

**Called by:** Direct Firestore write to any card document.

**Note:** This is the most frequently triggered function — every card creation, update, or deletion triggers a full rebuild.