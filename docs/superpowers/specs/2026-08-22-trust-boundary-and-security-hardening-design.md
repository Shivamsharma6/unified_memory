# Architecture Design: Trust Boundary Hardening, Path Containment, Per-Agent Auth, and Resilient Security

**Date**: 2026-08-22
**Author**: Antigravity (Pair Programming with Shivam Sharma)
**Status**: Approved

---

## 1. Problem Statement
The UAMS API had critical security vulnerabilities:
1. **Concrete Path Traversal in Quality Router**: `/memory/quality` and `/memory/quality/batch` used raw path concatenation (`vault_root / request.path`) without containment verification, allowing arbitrary filesystem reads (`../../../../etc/passwd`).
2. **Unbacked Destructive Operations**: `/memory/delete` moved files directly to `Archive/` without creating a timestamped backup in `.uams/backups/`.
3. **Missing Authentication & Per-Agent Identity Verification**: Endpoints had zero authentication and lacked caller token validation and agent whitelisting/revocation.
4. **Information Leakage via Unsanitized 500 Responses**: Raw Python exception strings leaking internal filesystem paths and stack traces were returned in HTTP responses.
5. **Unbounded Synchronous Full-Vault Scans**: `/validate` could freeze the asyncio event loop indefinitely during large corpus scans.

---

## 2. Technical Architecture & Security Model

```
                    Incoming Request (e.g. from Hermes / OpenClaw / API client)
                                                │
                                                ▼
                               ┌────────────────────────────────┐
                               │   Authentication & Caller ID   │
                               │   (api/security.py)            │
                               │  - Bearer Token / API Key check│
                               │  - Agent Whitelist verification│
                               │  - Extracted caller identity   │
                               └────────────────┬───────────────┘
                                                │
                                                ▼
                               ┌────────────────────────────────┐
                               │     Path Containment Guard     │
                               │  resolve_vault_path(vault_root)│
                               │  - Rejects traversal escapes   │
                               └────────────────┬───────────────┘
                                                │
                                                ▼
                               ┌────────────────────────────────┐
                               │     Protected Core Router      │
                               │  - /quality (contained read)   │
                               │  - /delete (durable backup)    │
                               │  - /edit (optimistic locking)  │
                               │  - /validate (bounded async)   │
                               └────────────────────────────────┘
```

---

## 3. Subsystem Detailed Changes

### Component 1: Strict Path Containment (`api/routers/quality.py`)
- Refactor `memory_quality` and `batch_quality` to use `resolve_vault_path(vault_root, path)`.
- If a path escapes the vault, raise `HTTPException(status_code=400, detail="Invalid path: Path is outside the memory vault")`.

### Component 2: Durable Backups for Deletions (`api/routers/memory_edit.py`)
- In `delete_memory()`:
  - Call `_backup(file_path)` to save an immutable copy in `.uams/backups/`.
  - Include `"backup": backup_path.relative_to(_vault_root()).as_posix()` in the response payload.

### Component 3: Security & Caller Identity Layer (`api/security.py`)
- Create `api/security.py`:
  - `verify_agent_auth(request: Request) -> str`:
    - Checks `UAMS_API_KEY` (if set) against `Authorization: Bearer <token>` or `X-API-Key`.
    - Checks `UAMS_ALLOWED_AGENTS` against caller agent identity (`X-Agent-Id` or header).
    - If `UAMS_AUTH_REQUIRED=true` and credentials missing, raises `HTTP 401 Unauthorized`.
    - If agent identity is not permitted in whitelist, raises `HTTP 403 Forbidden`.

### Component 4: Error Sanitization & Bounded Scans
- Wrap file read errors in `quality.py` with sanitized responses.
- In `api/routers/validation.py`:
  - Add `limit: int = 500` parameter to `validate_entire_vault` and run file reads in non-blocking threads.
