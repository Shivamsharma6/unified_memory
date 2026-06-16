---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:36:23.866653+00:00'
tags:
- '#cloud-functions'
- '#access-logs'
- '#callable'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Function: `processAccessLogs` (Lines 908-917)

## Summary
# Function: `processAccessLogs` (Lines 908-917)

**Type:** 🔗 HTTP Callable (`onCall`)
**Signature:** `https` (callable)
**URL:** `https://us-central1-sentri-ban2r1.cloudfunctions.net/processAccessLogs`

**What it does:** Callable endpoint that processes **queued raw access log entries** for a given business. ... [Distilled] ... **Parameters:** `{ businessId: string }`

**Client usage:**
```js
const processLogs = httpsCallable(functions, 'processAccessLogs');
await processLogs({ businessId: 'some-business-id' });
```

**Database operations:**
- **Firestore (read):** `businessess/{bizId}/access_logs/access_logs` — fetches `logs` array field
- **Firestore (read):** `businessess/{bizId}/cards/` — `where("card_data", "in", [...])` chunks of 30 (card-to-entity lookup)
- **Firestore (write):** `businessess/{bizId}/access_logs/ACCESS_LOGS_NNNN` — one doc per log row via **Firestore transaction** (sequence-safe via `next_id_LOGS`)
- **Firestore (write):** `businessess/{bizId}/access_logs/access_logs` — resets `{ logs: [] }` to clear queue

**Log document structure:**
```
ACCESS_LOGS_{NNNN}/
  log_card_id       — card_data value that triggered the entry
  log_status        — granted/denied/pending
  log_type          — IN, OUT, VOID
  log_device_id     — MAC address of device
  log_timestamp     — raw timestamp from device
  log_entity_id     — customer/user ID (from card lookup)
  log_entity_type   — "customer" or "user"
  updated_at        — serverTimestamp
```

**Delegates to:** `processQueuedAccessLogsForBusiness()` → `processAccessLogsForBusiness()`

## Raw Logs
# Function: `processAccessLogs` (Lines 908-917)

## Summary
# Function: `processAccessLogs` (Lines 908-917)

**Type:** 🔗 HTTP Callable (`onCall`)
**Signature:** `https` (callable)
**URL:** `https://us-central1-sentri-ban2r1.cloudfunctions.net/processAccessLogs`

**What it does:** Callable endpoint that processes **queued raw access log entries** for a given business. Reads pending `businessess/{bizId}/access_logs/access_logs` sub-document, maps each row to a card via card-to-entity lookup, writes structured log documents into `businessess/{bizId}/access_logs/ACCESS_LOGS_NNNN`.

**Parameters:** `{ businessId: string }`

**Client usage:**
```js
const processLogs = httpsCallable(functions, 'processAccessLogs');
await processLogs({ businessId: 'some-business-id' });
```

**Database operations:**
- **Firestore (read):** `businessess/{bizId}/access_logs/access_logs` — fetches `logs` array field
- **Firestore (read):** `businessess/{bizId}/cards/` — `where("card_data", "in", [...])` chunks of 30 (card-to-entity lookup)
- **Firestore (write):** `businessess/{bizId}/access_logs/ACCESS_LOGS_NNNN` — one doc per log row via **Firestore transaction** (sequence-safe via `next_id_LOGS`)
- **Firestore (write):** `businessess/{bizId}/access_logs/access_logs` — resets `{ logs: [] }` to clear queue

**Log document structure:**
```
ACCESS_LOGS_{NNNN}/
  log_card_id       — card_data value that triggered the entry
  log_status        — granted/denied/pending
  log_type          — IN, OUT, VOID
  log_device_id     — MAC address of device
  log_timestamp     — raw timestamp from device
  log_entity_id     — customer/user ID (from card lookup)
  log_entity_type   — "customer" or "user"
  updated_at        — serverTimestamp
```

**Delegates to:** `processQueuedAccessLogsForBusiness()` → `processAccessLogsForBusiness()`