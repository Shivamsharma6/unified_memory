---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:36:10.049919+00:00'
tags:
- '#cloud-functions'
- '#noop'
- '#paused'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Function: `onCustomerWrite` (Lines 818-828)

## Summary
# Function: `onCustomerWrite` (Lines 818-828)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/customer/{customerId}`
**Signature:** `cloudevent`

**What it does:** **NO-OP / PAUSED.** Logs a message and returns `null`. ... [Distilled] ... It fires on every customer document write but performs no state transition.

## Raw Logs
# Function: `onCustomerWrite` (Lines 818-828)

## Summary
# Function: `onCustomerWrite` (Lines 818-828)

**Type:** 🔁 Firestore (`onDocumentWritten`)
**Watched path:** `businessess/{businessId}/customer/{customerId}`
**Signature:** `cloudevent`

**What it does:** **NO-OP / PAUSED.** Logs a message and returns `null`. Logic was folded into `onShiftWrite` and `onCardWrite` by design.

**Database operations:** None (read-only, reads `event.params.businessId`, `event.params.customerId` for logging).

**Note:** This is a candidate for removal during the optimisation split. It fires on every customer document write but performs no state transition.