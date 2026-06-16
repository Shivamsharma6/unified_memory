---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:38:41.420983+00:00'
tags:
- '#cloud-functions'
- '#scheduled'
- '#active-cards'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Function: `dailyRebuild` (Lines 868-884)

## Summary
# Function: `dailyRebuild` (Lines 868-884)

**Type:** ⏰ Scheduled (Cron)
**Schedule:** `0 0 * * *` (midnight IST, daily)
**Signature:** `http` (CloudEvent)

**What it does:** Full rebuild of active-cards CSV for **every business** in the project. ... [Distilled] ... **Note:** This is the "safety net" — ensures active-cards CSV is always fresh even if triggers missed updates.

## Raw Logs
# Function: `dailyRebuild` (Lines 868-884)

## Summary
# Function: `dailyRebuild` (Lines 868-884)

**Type:** ⏰ Scheduled (Cron)
**Schedule:** `0 0 * * *` (midnight IST, daily)
**Signature:** `http` (CloudEvent)

**What it does:** Full rebuild of active-cards CSV for **every business** in the project. Runs once per day at midnight IST. Processes businesses in chunks of 5 (concurrency limit) to prevent timeout and excessive concurrent load.

**Algorithm:**
1. Fetch all businesses from Firestore (`businesses/` collection)
2. Chunk into groups of 5
3. For each chunk, run `rebuildActiveCardsCsvForBusiness(doc.id)` in parallel (Promise.all)
4. Log completion

**Database operations:**
- **Firestore (read):** `businessess/` collection (all doc IDs)
- **Firestore (read):** `businessess/{bizId}`, `businessess/{bizId}/cards/` (per business, via `rebuildActiveCardsCsvForBusiness`)
- **Firestore (write):** `businessess/{bizId}/active_cards/active_cards_csv` (per business)
- **RTDB (write):** `sentri/active_cards_version/{businessId}` (per business)

**Key detail:** `CONCURRENCY_LIMIT = 5` — processes 5 businesses at a time. With 1000+ businesses, this could take 200+ invocations of `rebuildActiveCardsCsvForBusiness`.

**Called by:** Scheduled cron (EventArc).

**Note:** This is the "safety net" — ensures active-cards CSV is always fresh even if triggers missed updates.