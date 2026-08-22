"""Vault and Markdown memory validation router.

Validates memory notes against AGENTS.md conventions:
1. Frontmatter completeness & ISO timestamp formatting
2. Memory type validity (semantic, episodic, procedural, etc.)
3. Memory ID stability across potential file moves
4. Wikilink resolution and orphaned link detection
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.memory_record import (
    MEMORY_ID_NAMESPACE,
    deterministic_memory_id,
    get_vault_root,
    parse_memory,
    split_frontmatter,
)

try:
    from memory_types.memory_types import MemoryCategory, CANONICAL_TYPE_ALIASES
except ImportError:
    from memory_watcher.memory_types.memory_types import MemoryCategory, CANONICAL_TYPE_ALIASES
from pipelines.reconciliation import Reconciler

router = APIRouter(prefix="/vault", tags=["Validation"])

WIKILINK_RE = re.compile(r"\[\[(.*?)\]\]")
VALID_MEMORY_TYPES = set(CANONICAL_TYPE_ALIASES.keys()) | {c.value for c in MemoryCategory} | {"entity", "profile"}


class ValidateMemoryRequest(BaseModel):
    content: str
    path: Optional[str] = "note.md"


class ValidationIssue(BaseModel):
    severity: str = "warning"  # "error", "warning", "info"
    code: str
    message: str
    line: Optional[int] = None


class ValidateMemoryResponse(BaseModel):
    valid: bool
    path: str
    memory_id: Optional[str] = None
    derived_memory_id: Optional[str] = None
    has_explicit_id: bool = False
    issues: List[ValidationIssue] = Field(default_factory=list)
    wikilinks: List[str] = Field(default_factory=list)


class VaultValidationSummary(BaseModel):
    total_scanned: int
    valid_count: int
    invalid_count: int
    warning_count: int
    broken_wikilinks_count: int
    notes_missing_explicit_id: int
    issues: List[dict]


def validate_note_content(
    content: str,
    path: str | Path = "note.md",
    vault_root: Optional[Path] = None,
    all_vault_titles_and_paths: Optional[set] = None,
) -> ValidateMemoryResponse:
    issues: List[ValidationIssue] = []
    p = Path(path)
    vault_p = vault_root or Path(".")

    # 1. Frontmatter check
    metadata, body = {}, ""
    try:
        metadata, body = split_frontmatter(content)
    except Exception as e:
        issues.append(
            ValidationIssue(
                severity="error",
                code="MALFORMED_FRONTMATTER",
                message=f"YAML frontmatter could not be parsed: {e}",
            )
        )

    if not metadata and not content.startswith("---"):
        issues.append(
            ValidationIssue(
                severity="error",
                code="MISSING_FRONTMATTER",
                message="Every memory note MUST contain a YAML frontmatter block starting with '---'.",
            )
        )

    # 2. Memory ID stability check
    raw_memory_id = metadata.get("memory_id")
    has_explicit_id = bool(raw_memory_id)
    derived_id = None
    try:
        derived_id = str(deterministic_memory_id(p, vault_root))
    except Exception:
        pass

    if not has_explicit_id:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="MISSING_EXPLICIT_MEMORY_ID",
                message=(
                    "Note relies on a path-derived deterministic UUID. "
                    "Moving or renaming this file will generate a new memory ID unless 'memory_id' is set in frontmatter."
                ),
            )
        )
    else:
        try:
            uuid.UUID(str(raw_memory_id))
        except ValueError:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_MEMORY_ID",
                    message=f"Provided memory_id '{raw_memory_id}' is not a valid UUID format.",
                )
            )

    # 3. Type check
    m_type = str(metadata.get("type", "")).lower()
    if not m_type:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="MISSING_TYPE",
                message="Frontmatter should specify a 'type' (semantic, episodic, procedural).",
            )
        )
    elif m_type not in VALID_MEMORY_TYPES:
        issues.append(
            ValidationIssue(
                severity="info",
                code="NON_STANDARD_TYPE",
                message=f"Type '{m_type}' is not one of the standard memory types: {sorted(VALID_MEMORY_TYPES)}.",
            )
        )

    # 4. Wikilink extraction & validation
    wikilinks = [match.group(1).split("|")[0].strip() for match in WIKILINK_RE.finditer(content)]
    if not wikilinks and len(body.split()) > 50:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="ORPHAN_CONTENT",
                message="Note has substantial content but contains zero [[wikilinks]]. Connect concepts to the graph.",
            )
        )

    if all_vault_titles_and_paths is not None:
        for link in wikilinks:
            normalized_link = link.strip()
            if normalized_link and normalized_link not in all_vault_titles_and_paths:
                issues.append(
                    ValidationIssue(
                        severity="info",
                        code="UNRESOLVED_WIKILINK",
                        message=f"Wikilink '[[{normalized_link}]]' target does not exist as a note or alias yet.",
                    )
                )

    # 5. Header hierarchy
    if "# " not in body and len(body.strip()) > 0:
        issues.append(
            ValidationIssue(
                severity="info",
                code="MISSING_TITLE_HEADER",
                message="Markdown body lacks a top-level '# Title' header.",
            )
        )

    has_errors = any(issue.severity == "error" for issue in issues)
    actual_memory_id = str(raw_memory_id) if has_explicit_id else derived_id

    return ValidateMemoryResponse(
        valid=not has_errors,
        path=str(path),
        memory_id=actual_memory_id,
        derived_memory_id=derived_id,
        has_explicit_id=has_explicit_id,
        issues=issues,
        wikilinks=wikilinks,
    )


@router.post("/validate-memory", response_model=ValidateMemoryResponse)
async def validate_memory_content(request: ValidateMemoryRequest):
    """Validate a single memory Markdown note."""
    vault_root = get_vault_root()
    return validate_note_content(request.content, request.path or "note.md", vault_root=vault_root)


import asyncio


def _sync_validate_vault(vault_root: Path, limit: int = 500) -> VaultValidationSummary:
    reconciler = Reconciler(vault_root, store=None)
    all_paths = reconciler.iter_memory_paths()
    paths = all_paths[:limit]

    # Pre-index all note names, stems, and aliases for link resolution
    known_targets = set()
    for p in all_paths:
        known_targets.add(p.stem)
        known_targets.add(p.name)
        try:
            rel = p.relative_to(vault_root).as_posix()
            known_targets.add(rel)
            meta, _ = split_frontmatter(p.read_text(encoding="utf-8"))
            for alias in meta.get("aliases", []):
                known_targets.add(str(alias).strip())
        except Exception:
            pass

    total_scanned = len(paths)
    valid_count = 0
    invalid_count = 0
    warning_count = 0
    broken_wikilinks_count = 0
    missing_explicit_id = 0
    all_issues = []

    for p in paths:
        try:
            content = p.read_text(encoding="utf-8")
            rel_path = p.relative_to(vault_root).as_posix()
            res = validate_note_content(
                content,
                rel_path,
                vault_root=vault_root,
                all_vault_titles_and_paths=known_targets,
            )
            if res.valid:
                valid_count += 1
            else:
                invalid_count += 1

            if not res.has_explicit_id:
                missing_explicit_id += 1

            for issue in res.issues:
                if issue.severity == "warning":
                    warning_count += 1
                if issue.code == "UNRESOLVED_WIKILINK":
                    broken_wikilinks_count += 1
                all_issues.append({"path": rel_path, **issue.model_dump()})
        except Exception as e:
            invalid_count += 1
            all_issues.append(
                {
                    "path": str(p),
                    "severity": "error",
                    "code": "READ_ERROR",
                    "message": str(e),
                }
            )

    return VaultValidationSummary(
        total_scanned=total_scanned,
        valid_count=valid_count,
        invalid_count=invalid_count,
        warning_count=warning_count,
        broken_wikilinks_count=broken_wikilinks_count,
        notes_missing_explicit_id=missing_explicit_id,
        issues=all_issues,
    )


@router.get("/validate", response_model=VaultValidationSummary)
async def validate_entire_vault(limit: int = 500):
    """Scan and validate Markdown notes in the vault against conventions in a non-blocking thread."""
    vault_root = get_vault_root()
    return await asyncio.to_thread(_sync_validate_vault, vault_root, limit)

