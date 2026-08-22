"""
Self-Editing Memory Endpoints.
Allows agents to correct, update, or delete their own memories with audit trail.
"""

import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models.memory_record import atomic_write, resolve_vault_path

router = APIRouter(prefix="/memory", tags=["Memory Edit"])
_audit_lock = threading.Lock()


class EditRequest(BaseModel):
    path: str
    old_text: str
    new_text: str
    expected_revision_id: Optional[str] = None
    expected_hash: Optional[str] = None

class DeleteRequest(BaseModel):
    path: str
    reason: str = "agent_correction"

class AddLinkRequest(BaseModel):
    path: str
    entity: str
    context: Optional[str] = None


@router.get("/status/{memory_id}")
async def memory_status(memory_id: str, request: Request):
    store = getattr(request.app.state, "control_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="PostgreSQL control plane is unavailable")
    try:
        parsed_memory_id = uuid.UUID(memory_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="memory_id must be a UUID") from error
    status = await store.get_memory_status(parsed_memory_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
    return status


def _vault_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _audit_log_path() -> Path:
    root = _vault_root()
    log_dir = root / "Logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir / "memory_edits.md"


def _log_edit(action: str, path: str, details: str = ""):
    with _audit_lock:
        log_path = _audit_log_path()
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = f"- [{timestamp}] **{action}** `{path}` {details}\n"
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8") + entry
        else:
            content = f"""---
type: procedural
status: active
aliases:
  - Memory Edit Audit Log
tags:
  - "#audit"
  - "#memory"
entities:
  - "[[Unified Agent Memory System]]"
timestamps:
  created: {timestamp}
  updated: {timestamp}
---
# Memory Edit Audit Log

## Events

{entry}"""
        atomic_write(log_path, content)


def _safe_request_path(requested: str) -> Path:
    try:
        return resolve_vault_path(_vault_root(), requested)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _backup(file_path: Path) -> Path:
    root = _vault_root().resolve()
    relative = file_path.relative_to(root)
    backup_dir = root / ".uams" / "backups" / relative.parent
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / f"{file_path.stem}-{stamp}-{uuid.uuid4().hex[:8]}.md"
    shutil.copy2(file_path, backup_path)
    return backup_path


@router.post("/edit")
async def edit_memory(request: EditRequest):
    file_path = _safe_request_path(request.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")
    content = file_path.read_text(encoding="utf-8")

    if request.expected_hash:
        import hashlib
        current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if request.expected_hash != current_hash:
            raise HTTPException(
                status_code=409,
                detail=f"Conflict: content hash mismatch (current: {current_hash[:12]}..., expected: {request.expected_hash[:12]}...)",
            )

    if request.old_text not in content:
        raise HTTPException(status_code=400, detail="old_text not found in file")
    backup_path = _backup(file_path)
    new_content = content.replace(request.old_text, request.new_text, 1)
    atomic_write(file_path, new_content)
    _log_edit("EDIT", request.path, f"replaced `{request.old_text[:50]}...`")
    return {
        "status": "success",
        "path": request.path,
        "backup": backup_path.relative_to(_vault_root()).as_posix(),
        "index_status": "pending",
        "message": "Memory edited.",
    }



@router.post("/delete")
async def delete_memory(request: DeleteRequest):
    file_path = _safe_request_path(request.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")
    archive_dir = _vault_root() / "Archive"
    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / file_path.name
    if archive_path.exists():
        archive_path = archive_dir / f"{file_path.stem}-{uuid.uuid4().hex[:8]}{file_path.suffix}"
    shutil.move(str(file_path), str(archive_path))
    _log_edit("DELETE", request.path, f"reason: {request.reason}")
    return {"status": "success", "path": request.path, "archived_to": str(archive_path.relative_to(_vault_root())), "message": "Memory archived."}


@router.post("/add-link")
async def add_link(request: AddLinkRequest):
    file_path = _safe_request_path(request.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")
    content = file_path.read_text(encoding="utf-8")
    link = f"[[{request.entity}]]"
    if link in content:
        return {"status": "noop", "message": f"Link {link} already exists."}
    if "tags:" in content:
        content = re.sub(r'(tags:\s*\[)', f'\\1"{link}", ', content, count=1)
    context_line = f"\n\nReferenced: {link}" if request.context else f"\n\nSee also: {link}"
    content += context_line
    atomic_write(file_path, content)
    _log_edit("ADD_LINK", request.path, f"added {link}")
    return {"status": "success", "path": request.path, "entity": request.entity, "message": f"Link {link} added."}
