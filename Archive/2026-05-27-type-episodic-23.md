---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:40:08.166816+00:00'
tags:
- '#cloud-functions'
- '#firestore'
- '#data-model'
- '#collections'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
The Firestore data model establishes a nested hierarchy under businessesses/{businessId}/ to manage cards, users, customers, and shifts. Key architectural decisions include dual-logging for access logs—storing both raw pipe-delimited strings and granular individual documents with metadata like status and device IDs. The model supports subscription tracking via backfilled fields, shift cancellation reasons, and a CSV-based active card repository. Root-level collections manage business extensions/expiration durations, device statuses mapped by MAC addresses, and firmware updates. Note the naming discrepancy between businesses and businessesses for potential consistency checks.

## Raw Logs
# Cloud Functions — Firestore Data Model

## Summary
# Cloud Functions — Firestore Data Model

## Collections (all under `businessess/{businessId}/`)

### `cards/`
- `card_id` (document ID)
- `card_data` (string — the card's human-readable identifier, used in CSV)
- `card_status` (boolean — `true` = active, `false` = inactive)
- `card_assigned_to` (string — customer/user ID)
- `card_assigned_type` (string — `"user"` or `"customer"`)

### `business_users/`
- `user_id` (document ID)
- `user_status` (boolean/string)
- `user_current_card` (string — expected card ID)

### `customer/`
- `customer_id` (document ID)
- `customer_status` (boolean)
- `customer_current_shift_id` (string or array of strings)
- `customer_subscription_end_date` (array of Timestamps)
- `customer_latest_subscription_end` (Timestamp|null — backfilled field)

### `customer_shifts/`
- `shift_id` (document ID)
- `shift_status` (boolean)
- `shift_start_time` (Timestamp)
- `shift_end_time` (Timestamp)
- `shift_customer_id` (string)
- `shift_cancellation_reason` (string — `"expired"` when auto-expired)

### `access_logs/`
- `access_logs/` (single document)
  - `logs` (array of raw pipe-delimited strings)
- `ACCESS_LOGS_NNNN/` (individual log documents)
  - `log_card_id` (string — card_data value)
  - `log_status` (string — granted/denied/pending)
  - `log_type` (string — IN, OUT, VOID)
  - `log_device_id` (string — MAC address)
  - `log_timestamp` (string — raw timestamp from device)
  - `log_entity_id` (string — customer/user ID)
  - `log_entity_type` (string — "customer" or "user")
  - `updated_at` (serverTimestamp)

### `active_cards/`
- `active_cards_csv/` (single document)
  - `cards` (string — CSV content)
  - `updated_at` (serverTimestamp)

### `businesses/` (root-level)
- `business_id` (document ID)
- `business_time_extension` (number — minutes)
- `business_expiration_duration` (number — grace days)

### `businessess/` (root-level)
- `business_devices/{macAddress}/`
  - `device_status` (boolean/string)

### `devices/` (root-level)
- `firmware_updates/` (single document)