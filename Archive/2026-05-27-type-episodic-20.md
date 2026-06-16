---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:39:34.183999+00:00'
tags:
- '#cloud-functions'
- '#optimisation'
- '#plan'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Cloud Functions — Optimisation Plan (cloud functions optimisation.md)

## Summary
# Cloud Functions — Optimisation Plan (cloud functions optimisation.md)

## Current Architecture (Monolithic)
- **Single build image** deployed to 16+ Cloud Run services
- **Same code** in every service, differentiated only by `FUNCTION_TARGET` env var
- **Cold starts** on every invocation (no warm instances)
- **RTDB writes** on every active-cards change (high frequency)
- **Global cache** (`globalCardAssignmentCache`, `globalEntityCache`) survives warm starts but is lost on cold starts

## Proposed Architecture (Split)
- **4 separate services** (instead of 16):
  1. ... [Distilled] ... **`backups`** — `scheduledFirestoreBackup`, `manualFirestoreBackup` (backup operations)

## Benefits
- **Independent scaling** — high-frequency services (active-cards) get more instances, low-frequency (backups) get fewer
- **Faster cold starts** — smaller code bundles (access-logs: ~300 lines, active-cards: ~600 lines, shifts: ~150 lines, backups: ~50 lines)
- **Independent deployment** — change one service without redeploying all 16
- **Better cost control** — allocate resources where needed
- **Clearer ownership** — each service has a single responsibility

## RTDB Optimisation
- **Current:** RTDB version bump on every active-cards change (high frequency)
- **Proposed:** Keep RTDB for POS client cache invalidation (it's the right tool for real-time push)
- **Optimisation:** Consider debouncing RTDB writes (batch version bumps)

## Firestore Indexes Required
- `businesses/{businessId}/cards` — `card_status` (single-field)
- `businesses/{businessId}/cards` — `card_data` (single-field)
- `customer_shifts` (collection-group) — `shift_status` (single-field)
- `businesses/{businessId}/access_logs` — `access_logs` (single-field)

## Raw Logs
# Cloud Functions — Optimisation Plan (cloud functions optimisation.md)

## Summary
# Cloud Functions — Optimisation Plan (cloud functions optimisation.md)

## Current Architecture (Monolithic)
- **Single build image** deployed to 16+ Cloud Run services
- **Same code** in every service, differentiated only by `FUNCTION_TARGET` env var
- **Cold starts** on every invocation (no warm instances)
- **RTDB writes** on every active-cards change (high frequency)
- **Global cache** (`globalCardAssignmentCache`, `globalEntityCache`) survives warm starts but is lost on cold starts

## Proposed Architecture (Split)
- **4 separate services** (instead of 16):
  1. **`access-logs`** — `onAccessLogsWrite`, `processAccessLogs` (access log processing)
  2. **`active-cards`** — `onCardWrite`, `onShiftWrite`, `onBusinessUserWrite`, `onDeviceUpdated`, `onOtaUpdate`, `dailyRebuild`, `rebuildActiveCards`, `rebuildActiveCardsCsv`, `syncActiveCardsCsvVersion`, `rebuildActiveCardsCsvForBusiness`, `writeActiveCardsCsvForBusiness`, `buildActiveCardsCsv` (core pipeline)
  3. **`shifts`** — `onCustomerWrite` (paused), `autoExpireShifts` (shift management)
  4. **`backups`** — `scheduledFirestoreBackup`, `manualFirestoreBackup` (backup operations)

## Benefits
- **Independent scaling** — high-frequency services (active-cards) get more instances, low-frequency (backups) get fewer
- **Faster cold starts** — smaller code bundles (access-logs: ~300 lines, active-cards: ~600 lines, shifts: ~150 lines, backups: ~50 lines)
- **Independent deployment** — change one service without redeploying all 16
- **Better cost control** — allocate resources where needed
- **Clearer ownership** — each service has a single responsibility

## RTDB Optimisation
- **Current:** RTDB version bump on every active-cards change (high frequency)
- **Proposed:** Keep RTDB for POS client cache invalidation (it's the right tool for real-time push)
- **Optimisation:** Consider debouncing RTDB writes (batch version bumps)

## Firestore Indexes Required
- `businesses/{businessId}/cards` — `card_status` (single-field)
- `businesses/{businessId}/cards` — `card_data` (single-field)
- `customer_shifts` (collection-group) — `shift_status` (single-field)
- `businesses/{businessId}/access_logs` — `access_logs` (single-field)