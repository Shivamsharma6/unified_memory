---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:36:46.539825+00:00'
tags:
- '#cloud-functions'
- '#active-cards'
- '#firestore-trigger'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Function: `onBusinessUserWrite` (Lines 840-848)

## Summary
# Function: `onBusinessUserWrite` (Lines 840-848)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/business_users/{userId}`
**Signature:** `cloudevent`

**What it does:** Watches for any write to a business user document. ... [Distilled] ... **Called by:** `onCardWrite`, `onShiftWrite`, `onBusinessUserWrite`, `dailyRebuild`, `rebuildActiveCards`, `rebuildActiveCardsCsv`

## Raw Logs
# Function: `onBusinessUserWrite` (Lines 840-848)

## Summary
# Function: `onBusinessUserWrite` (Lines 840-848)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/business_users/{userId}`
**Signature:** `cloudevent`

**What it does:** Watches for any write to a business user document. Triggers `rebuildActiveCardsCsvForBusiness(businessId)` — because changing a user's status, assigned card, or active/inactive state affects whose access slots are valid.

**Database operations:**
- **Firestore (read):** `businessess/{bizId}`, `businessess/{bizId}/cards/` (full rebuild via `rebuildActiveCardsCsvForBusiness`)
- **Firestore (write):** `businessess/{bizId}/active_cards/active_cards_csv` — `{ cards: <csv_string>, updated_at: serverTimestamp }`
- **RTDB (write):** `sentri/active_cards_version/{businessId}` — `{ <ISO timestamp> }` as version bump to notify connected POS clients

**Active-cards CSV format:** `card_data:HH:MM-HH:MM|HH:MM-HH:MM, card_data:00:00-23:59, …`
Left side = card_data value, right side = pipe-separated time-window ranges for every currently-active shift.

**Called by:** `onCardWrite`, `onShiftWrite`, `onBusinessUserWrite`, `dailyRebuild`, `rebuildActiveCards`, `rebuildActiveCardsCsv`