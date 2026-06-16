---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:37:20.861269+00:00'
tags:
- '#cloud-functions'
- '#scheduled'
- '#shifts'
- '#expiration'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Function: `autoExpireShifts` (Lines 664-806)

## Summary
# Function: `autoExpireShifts` (Lines 664-806)

**Type:** ⏰ Scheduled (Cron)
**Schedule:** `every day 00:00` (midnight IST, daily)
**Signature:** `http` (CloudEvent)

**What it does:** **Automatic shift expiry job.** Runs every night at midnight IST. ... [Distilled] ... **Batch update** — expire shifts in Firestore batches of 500 (Firestore batch limit)

**Database operations:**
- **Firestore (collection-group read):** `customer_shifts/` where `shift_status == true`
- **Firestore (read):** `businessess/{bizId}` — `business_expiration_duration` (grace days)
- **Firestore (read):** `businessess/{bizId}/customer/{custId}` — `customer_subscription_end_date` array
- **Firestore (batch write):** `businessess/{bizId}/customer_shifts/{shiftId}` — `shift_status: false` + `shift_cancellation_reason: "expired"` (batches of 500)

**Grace period logic:**
```
effectiveExpiryMs = latestSubscriptionEndMs + (business_expiration_duration_days × 86400000)
if nowMs > effectiveExpiryMs → expire the shift
```

**Key detail:** Uses `collectionGroup` query — requires Firestore composite index on `customer_shifts.shift_status`.

## Raw Logs
# Function: `autoExpireShifts` (Lines 664-806)

## Summary
# Function: `autoExpireShifts` (Lines 664-806)

**Type:** ⏰ Scheduled (Cron)
**Schedule:** `every day 00:00` (midnight IST, daily)
**Signature:** `http` (CloudEvent)

**What it does:** **Automatic shift expiry job.** Runs every night at midnight IST. Scans all active shifts (`shift_status == true`) across all businesses. For each shift whose `shift_end_time` is in the past AND whose customer's latest subscription end date + per-business grace period (`business_expiration_duration` days) has also passed, it sets `shift_status = false` and `shift_cancellation_reason = "expired"`.

**Algorithm (4-phase):**
1. **Query all active shifts** — `db.collectionGroup("customer_shifts").where("shift_status", "==", true)`
2. **Pre-fetch all unique businesses** in parallel (for `business_expiration_duration` grace period)
3. **Filter candidates** — shifts past `shift_end_time` with `graceDays > 0` and valid `customerId`
4. **Pre-fetch all required customers** in parallel (chunks of 100) to get `customer_subscription_end_date`
5. **Calculate effective expiry** — `latestSubscriptionEndMs + (graceDays * MS_PER_DAY)`
6. **Batch update** — expire shifts in Firestore batches of 500 (Firestore batch limit)

**Database operations:**
- **Firestore (collection-group read):** `customer_shifts/` where `shift_status == true`
- **Firestore (read):** `businessess/{bizId}` — `business_expiration_duration` (grace days)
- **Firestore (read):** `businessess/{bizId}/customer/{custId}` — `customer_subscription_end_date` array
- **Firestore (batch write):** `businessess/{bizId}/customer_shifts/{shiftId}` — `shift_status: false` + `shift_cancellation_reason: "expired"` (batches of 500)

**Grace period logic:**
```
effectiveExpiryMs = latestSubscriptionEndMs + (business_expiration_duration_days × 86400000)
if nowMs > effectiveExpiryMs → expire the shift
```

**Key detail:** Uses `collectionGroup` query — requires Firestore composite index on `customer_shifts.shift_status`.