---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:37:06.643546+00:00'
tags:
- '#cloud-functions'
- '#ota'
- '#firestore-trigger'
- '#rtdb'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Function: `onOtaUpdate` (Lines 639-662)

## Summary
# Function: `onOtaUpdate` (Lines 639-662)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `devices/firmware_updates` (root-level doc, **no business scoping**)
**Signature:** `cloudevent`

**What it does:** Global firmware update ping. ... [Distilled] ... Could be expensive with thousands of businesses.

## Raw Logs
# Function: `onOtaUpdate` (Lines 639-662)

## Summary
# Function: `onOtaUpdate` (Lines 639-662)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `devices/firmware_updates` (root-level doc, **no business scoping**)
**Signature:** `cloudevent`

**What it does:** Global firmware update ping. When a new OTA firmware entry is written to `devices/firmware_updates`, this function **queries all businesses** from Firestore and writes a version bump to **every business's `active_cards_version`** in RTDB simultaneously. This ensures all active POS terminals refresh on an app update.

**Database operations:**
- **Firestore (read):** `businessess/` collection (select all doc IDs)
- **RTDB (write):** Multi-path update: `sentri/active_cards_version/{bizId}` → `{ <timestamp_ms> }` for **every business** in the project

**Key detail:** Uses `admin.database().ref().update(batchPings)` — single RTDB call with all business IDs. If no businesses exist, returns `null` (no-op).

**Blast radius:** Fires once per OTA push, touches every business. Could be expensive with thousands of businesses.