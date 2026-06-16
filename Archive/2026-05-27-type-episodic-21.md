---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:39:41.856617+00:00'
tags:
- '#cloud-functions'
- '#rtdb'
- '#data-structure'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Cloud Functions — RTDB Structure

## Summary
# Cloud Functions — RTDB Structure

## `sentri/active_cards_version/{businessId}`
- **Type:** String (ISO timestamp or epoch ms)
- **Purpose:** Cache invalidation token for POS terminals
- **Written by:** `writeActiveCardsCsvForBusiness()`, `onDeviceUpdated`, `onOtaUpdate`, `syncActiveCardsCsvVersion`
- **Read by:** POS mobile app (real-time listener)
- **Behavior:** When value changes, POS clients re-fetch active-cards CSV from Firestore

## RTDB Path Pattern
`/sentri/active_cards_version/{businessId}`

## RTDB Instance
`sentri-ban2r1-default-rtdb.asia-southeast1.firebasedatabase.app`

## RTDB Client
`admin.database().ref()` — Firebase Admin SDK RTDB client

## Key Detail
RTDB is used **only** for real-time cache invalidation. ... [Distilled] ... POS clients listen to RTDB for change notifications, then re-fetch the actual data from Firestore.

## Raw Logs
# Cloud Functions — RTDB Structure

## Summary
# Cloud Functions — RTDB Structure

## `sentri/active_cards_version/{businessId}`
- **Type:** String (ISO timestamp or epoch ms)
- **Purpose:** Cache invalidation token for POS terminals
- **Written by:** `writeActiveCardsCsvForBusiness()`, `onDeviceUpdated`, `onOtaUpdate`, `syncActiveCardsCsvVersion`
- **Read by:** POS mobile app (real-time listener)
- **Behavior:** When value changes, POS clients re-fetch active-cards CSV from Firestore

## RTDB Path Pattern
`/sentri/active_cards_version/{businessId}`

## RTDB Instance
`sentri-ban2r1-default-rtdb.asia-southeast1.firebasedatabase.app`

## RTDB Client
`admin.database().ref()` — Firebase Admin SDK RTDB client

## Key Detail
RTDB is used **only** for real-time cache invalidation. The source of truth is always Firestore. POS clients listen to RTDB for change notifications, then re-fetch the actual data from Firestore.