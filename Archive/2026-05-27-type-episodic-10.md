---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:36:56.134460+00:00'
tags:
- '#cloud-functions'
- '#device'
- '#firestore-trigger'
- '#rtdb'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Function: `onDeviceUpdated` (Lines 619-637)

## Summary
# Function: `onDeviceUpdated` (Lines 619-637)

**Type:** 🔁 Firestore (`onDocumentUpdated`) — **NO delete support**
**Watched path:** `businessess/{businessId}/business_devices/{macAddress}`
**Signature:** `cloudevent`

**What it does:** Watches for **status changes** on an RTDB device entry synced to Firestore. ... [Distilled] ... Returns `null` if no status change occurred.

## Raw Logs
# Function: `onDeviceUpdated` (Lines 619-637)

## Summary
# Function: `onDeviceUpdated` (Lines 619-637)

**Type:** 🔁 Firestore (`onDocumentUpdated`) — **NO delete support**
**Watched path:** `businessess/{businessId}/business_devices/{macAddress}`
**Signature:** `cloudevent`

**What it does:** Watches for **status changes** on an RTDB device entry synced to Firestore. When `device_status` changes (e.g. device goes online/offline, gate open/close), it bumps the `active_cards_version` in RTDB so that connected POS terminals invalidate their cached active-cards data and re-fetch from Firestore.

**Guard:** Only fires on **status change** — `beforeData.device_status !== afterData.device_status` prevents spurious RTDB writes.

**Database operations:**
- **Firestore (read):** before/after snapshot of `businessess/{bizId}/business_devices/{macAddress}`
- **RTDB (write):** `sentri/active_cards_version/{businessId}` → `{ <timestamp_ms> }`

**Key detail:** Uses `Date.now().toString()` as version token (epoch ms as string). Returns `null` if no status change occurred.