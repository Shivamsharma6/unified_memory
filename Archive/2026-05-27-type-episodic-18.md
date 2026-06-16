---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:39:07.331111+00:00'
tags:
- '#cloud-functions'
- '#backfill'
- '#subscription'
- '#http'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
Decision: Implement a one-time migration utility to populate the missing customer_latest_subscription_end field for all customers. 

Implementation Details: The function iterates through all businesses and customers, skipping records that already contain the field. It calculates values based on customer status (null if false) and uses batch writes of up to 500 documents per business to optimize Firestore performance.

Error Handling: A fallback mechanism is included in the commit function to switch to individual writes if a batch write fails, ensuring all records are processed.

Resolution: This utility is intended for one-time use; it should be decommissioned once the migration confirms all customer documents have been updated.

## Raw Logs
# Function: `backfillCustomerLatestSubscriptionEnd` (Lines 919-997)

## Summary
# Function: `backfillCustomerLatestSubscriptionEnd` (Lines 919-997)

**Type:** 🌐 HTTP Request (`onRequest`)
**Signature:** `https` (raw HTTP)
**URL:** `https://us-central1-sentri-ban2r1.cloudfunctions.net/backfillCustomerLatestSubscriptionEnd`
**Timeout:** 540 seconds (9 minutes)
**Memory:** 512MiB

**What it does:** **One-time backfill utility.** Iterates over all businesses, then all customers, and writes `customer_latest_subscription_end` field to every customer document that doesn't already have it. This is a **migration helper** — once all customers have this field, the function can be removed.

**Algorithm:**
1. Fetch all businesses from Firestore
2. For each business:
   - Fetch all customers
   - For each customer:
     - Skip if `customer_latest_subscription_end` already exists
     - If `customer_status === false` → `latestSubscriptionEnd = null`
     - Otherwise → `latestSubscriptionEnd = getLatestSubscriptionTimestamp(customer_subscription_end_date)`
     - Batch writes (up to 500 docs per batch) via `commitCustomerBackfillWrites()`
3. Return summary: `{ businesses, updated, skipped, errors }`

**Database operations:**
- **Firestore (read):** `businessess/` (all doc IDs)
- **Firestore (read):** `businessess/{bizId}/customer/` (all customer docs)
- **Firestore (batch write):** `businessess/{bizId}/customer/{custId}` — `{ customer_latest_subscription_end: <Timestamp|null> }` (batches of 500)

**Parameters:** GET or POST (no body required).

**Response:** `{ businesses: N, updated: N, skipped: N, errors: N }`

**Key detail:** `CUSTOMER_BACKFILL_BATCH_SIZE = 500` (Firestore batch limit). Uses `commitCustomerBackfillWrites()` which falls back to individual writes on failure.

**Note:** This is a **one-time migration** — once complete, it can be removed.