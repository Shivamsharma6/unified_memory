---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:38:31.401170+00:00'
tags:
- '#cloud-functions'
- '#active-cards'
- '#firestore-trigger'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Function: `onShiftWrite` (Lines 830-838)

## Summary
# Function: `onShiftWrite` (Lines 830-838)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/customer_shifts/{shiftId}`
**Signature:** `cloudevent`

**What it does:** Watches for any write to a customer shift document. ... [Distilled] ... This is the most impactful trigger — a single shift change rebuilds the entire business's active-cards CSV.

## Raw Logs
# Function: `onShiftWrite` (Lines 830-838)

## Summary
# Function: `onShiftWrite` (Lines 830-838)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/customer_shifts/{shiftId}`
**Signature:** `cloudevent`

**What it does:** Watches for any write to a customer shift document. Triggers `rebuildActiveCardsCsvForBusiness(businessId)` — because shift start/end times determine the time-window ranges in the active-cards CSV.

**Database operations:**
- **Firestore (read):** `businessess/{bizId}`, `businessess/{bizId}/cards/` (full rebuild via `rebuildActiveCardsCsvForBusiness`)
- **Firestore (write):** `businessess/{bizId}/active_cards/active_cards_csv` — `{ cards: <csv_string>, updated_at: serverTimestamp }`
- **RTDB (write):** `sentri/active_cards_version/{businessId}` — `{ <ISO timestamp> }`

**Called by:** Direct Firestore write to any customer_shifts document.

**Note:** Shift creation, modification, or deletion all trigger a full rebuild. This is the most impactful trigger — a single shift change rebuilds the entire business's active-cards CSV.