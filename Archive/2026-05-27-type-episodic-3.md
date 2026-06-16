---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:35:43.936696+00:00'
tags:
- '#cloud-functions'
- '#core-pipeline'
- '#active-cards'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Cloud Functions — Core Pipeline: `rebuildActiveCardsCsvForBusiness` (Lines 402-617)

## Summary
# Cloud Functions — Core Pipeline: `rebuildActiveCardsCsvForBusiness` (Lines 402-617)

This is the **central function** called by 5+ triggers. ... [Distilled] ... ## `commitCustomerBackfillWrites(pendingWrites, summary)` (Lines 353-378)
Batch commit (up to 500 docs) with fallback to individual writes on failure.

## Raw Logs
# Cloud Functions — Core Pipeline: `rebuildActiveCardsCsvForBusiness` (Lines 402-617)

## Summary
# Cloud Functions — Core Pipeline: `rebuildActiveCardsCsvForBusiness` (Lines 402-617)

This is the **central function** called by 5+ triggers. It rebuilds the active-cards CSV for a single business.

## Algorithm (strict filtering pipeline)
1. **Fetch business metadata** — get `business_time_extension` (minutes, default 0).
2. **Query active cards** — `where("card_status", "==", true)` (optimization: skips inactive cards).
3. **For each card**, apply filters in order:
   - `card_status === true` (already filtered by query, but double-checked)
   - `card_assigned_to` must be non-empty
   - **If `card_assigned_type === "user"`:**
     - Look up business user (cached locally)
     - User must exist, `user_status === true`
     - `user_current_card` must match `card_id` (card mismatch = skip)
     - → Include as full-day card: `00:00-23:59`
   - **If `card_assigned_type === "customer"`:**
     - Look up customer (cached locally)
     - Customer must exist, `customer_status === true`
     - Get `customer_current_shift_id` (array or single)
     - For each shift:
       - Shift must exist, `shift_status === true`
       - Shift dates must be parseable
       - Shift dates must include today (`isDateWithinRangeInclusive`)
       - If whole-day window (`00:00-23:59`): include as `00:00-23:59`
       - Otherwise: apply `business_time_extension` via `getExtendedWindow`
       - → Include with extended time window
   - **Unsupported assignee type** → skip
4. **Write CSV** via `writeActiveCardsCsvForBusiness(businessId, cards)`
5. **Bump RTDB** version at `sentri/active_cards_version/{businessId}`

## Execution-level caches (per invocation)
- `localUserCache`: Map<userId, businessUser data>
- `localCustomerCache`: Map<customerId, customer data>
- `localShiftCache`: Map<shiftId, shift data>

## Skip counters (logged for debugging)
`skipped_card_status`, `skipped_not_assigned`, `skipped_unsupported_assignee`, `skipped_customer_missing`, `skipped_customer_inactive`, `skipped_no_shifts`, `skipped_shift_missing`, `skipped_shift_inactive`, `skipped_shift_date_mismatch`, `skipped_user_missing`, `skipped_user_inactive`, `skipped_user_card_mismatch`, `unparseable_shift_dates`

## `writeActiveCardsCsvForBusiness(businessId, cards)` (Lines 380-400)
Writes CSV to Firestore (`businessess/{bizId}/active_cards/active_cards_csv`) and bumps RTDB (`sentri/active_cards_version/{bizId}`) with ISO timestamp.

## `processAccessLogsForBusiness(businessId, rawLogs)` (Lines 212-318)
Parses raw pipe-delimited log entries, looks up card-to-entity mapping (with global cache), writes structured log documents via Firestore transaction (sequence-safe via `next_id_LOGS` counter).

## `processQueuedAccessLogsForBusiness(businessId)` (Lines 320-334)
Reads pending logs from `access_logs/access_logs` doc and delegates to `processAccessLogsForBusiness`.

## `getLatestSubscriptionTimestamp(subscriptionEndDates)` (Lines 336-351)
Returns the latest `Timestamp` from an array of subscription end dates.

## `commitCustomerBackfillWrites(pendingWrites, summary)` (Lines 353-378)
Batch commit (up to 500 docs) with fallback to individual writes on failure.