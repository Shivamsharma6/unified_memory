---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:39:52.088925+00:00'
tags:
- '#cloud-functions'
- '#caching'
- '#global-state'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
Implemented global caches (globalCardAssignmentCache and globalEntityCache) to optimize performance in Cloud Run/Functions by storing card assignments and entity data across warm invocations. Key architectural decision: Caches are per-instance, meaning they do not share state between concurrent instances and are cleared during cold starts. Expected behavior: The first invocation after a scale-to-zero event will trigger full database reads (cache miss), while subsequent calls on the same instance will benefit from high-speed resolution (cache hit).

## Raw Logs
# Cloud Functions — Global Caches (Cross-Execution)

## Summary
# Cloud Functions — Global Caches (Cross-Execution)

## `globalCardAssignmentCache` (Map)
- **Key:** `${businessId}:${cardData}` (e.g., `"biz123:ABC123"`)
- **Value:** `{ log_entity_id: string, log_entity_type: string }`
- **Purpose:** Maps card_data values to the customer/user they're assigned to. Used by `processAccessLogsForBusiness` to resolve raw log entries to entity IDs.
- **Lifecycle:** Survives across Cloud Run cold starts (warm instance cache). Lost on cold start.
- **Populated by:** `processAccessLogsForBusiness` — reads all cards and populates the cache.

## `globalEntityCache` (Map)
- **Key:** Entity ID (string)
- **Value:** Entity data (object)
- **Purpose:** Caches customer/user data across invocations. Used by `processAccessLogsForBusiness` to avoid redundant reads.
- **Lifecycle:** Survives across Cloud Run cold starts (warm instance cache). Lost on cold start.
- **Populated by:** `processAccessLogsForBusiness` — reads customer/user documents and caches them.

## Key Detail
These caches are **per-Cloud-Run-instance** — not shared across instances. They survive cold starts (warm instances) but are lost when Cloud Run scales to zero. This means:
- First invocation after cold start: cache miss → reads all cards
- Subsequent invocations (warm): cache hit → fast resolution
- Multiple concurrent instances: each has its own cache (no cross-instance sharing)