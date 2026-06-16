---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:40:19.667946+00:00'
tags:
- '#cloud-functions'
- '#deployment'
- '#firebase.json'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Cloud Functions — Deployment Configuration

## Summary
# Cloud Functions — Deployment Configuration

## `firebase.json` (Lines 1-120)
```json
{
  "functions": {
    "source": "functions",
    "runtime": "nodejs24",
    "ignore": ["node_modules", ".git", "firebase-debug.log", "firebase-debug.*.log"],
    "predeploy": ["npx firebase-tools deploy --only functions:access-logs,functions:active-cards,functions:shifts,functions:backups"]
  },
  "emulators": {
    "functions": { "port": 5001 },
    "firestore": { "port": 8080 },
    "database": { "port": 9000 },
    "storage": { "port": 9199 },
    "auth": { "port": 9099 },
    "pubsub": { "port": 8085 },
    "ui": { "enabled": true, "port": 4000 }
  }
}
```

## Deployment Targets (4 services)
1. ... [Distilled] ... This is the **optimised deployment target** — the monolithic version deploys all 16 services.

## Raw Logs
# Cloud Functions — Deployment Configuration

## Summary
# Cloud Functions — Deployment Configuration

## `firebase.json` (Lines 1-120)
```json
{
  "functions": {
    "source": "functions",
    "runtime": "nodejs24",
    "ignore": ["node_modules", ".git", "firebase-debug.log", "firebase-debug.*.log"],
    "predeploy": ["npx firebase-tools deploy --only functions:access-logs,functions:active-cards,functions:shifts,functions:backups"]
  },
  "emulators": {
    "functions": { "port": 5001 },
    "firestore": { "port": 8080 },
    "database": { "port": 9000 },
    "storage": { "port": 9199 },
    "auth": { "port": 9099 },
    "pubsub": { "port": 8085 },
    "ui": { "enabled": true, "port": 4000 }
  }
}
```

## Deployment Targets (4 services)
1. `functions:access-logs` — `FUNCTION_TARGET=onAccessLogsWrite`
2. `functions:active-cards` — `FUNCTION_TARGET=rebuildActiveCardsCsvForBusiness`
3. `functions:shifts` — `FUNCTION_TARGET=autoExpireShifts`
4. `functions:backups` — `FUNCTION_TARGET=scheduledFirestoreBackup`

## `package.json` (Dependencies)
- `firebase-admin` (Firebase Admin SDK)
- `firebase-functions` (v2)
- `@google-cloud/firestore` (Firestore Admin Client for backups)
- `@google-cloud/backup` (Firestore Backup Client)

## Key Detail
The `predeploy` script only deploys 4 services (not 16). This is the **optimised deployment target** — the monolithic version deploys all 16 services.