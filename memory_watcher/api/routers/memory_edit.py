"""
Self-Editing Memory Endpoints.
Allows agents to correct, update, or delete their own memories with audit trail.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/memory", tags=["Memory Edit"])


class EditRequest(BaseModel):
    path: str
    old_text: str
    new_text: str

class DeleteRequest(BaseModel):
    path: str
    reason: str = "agent_correction"

class AddLinkRequest(BaseModel):
    path: str
    entity: str
    context: Optional[str] = None


def _vault_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _audit_log_path() -> Path:
    root = _vault_root()
    log_dir = root / "Logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir / "memory_edits.md"


def _log_edit(action: str, path: str, details: str = ""):
    log_path = _audit_log_path()
    timestamp = datetime.now().isoformat()
    entry = f"- [{timestamp}] **{action}** `{path}` {details}\n"
    with open(log_path, "a") as f:
        f.write(entry)


@router.post("/edit")
async def edit_memory(request: EditRequest):
    file_path = _vault_root() / request.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")
    content = file_path.read_text(encoding="utf-8")
    if request.old_text not in content:
        raise HTTPException(status_code=400, detail="old_text not found in file")
    backup_path = file_path.with_suffix(f".backup-{datetime.now().strftime('%Y%m%d%H%M%S')}.md")
    shutil.copy2(file_path, backup_path)
    new_content = content.replace(request.old_text, request.new_text, 1)
    file_path.write_text(new_content, encoding="utf-8")
    _log_edit("EDIT", request.path, f"replaced `{request.old_text[:50]}...`")
    return {"status": "success", "path": request.path, "backup": str(backup_path.name), "message": "Memory edited."}


@router.post("/delete")
async def delete_memory(request: DeleteRequest):
    file_path = _vault_root() / request.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")
    archive_dir = _vault_root() / "Archive"
    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / file_path.name
    shutil.move(str(file_path), str(archive_path))
    _log_edit("DELETE", request.path, f"reason: {request.reason}")
    return {"status": "success", "path": request.path, "archived_to": str(archive_path.relative_to(_vault_root())), "message": "Memory archived."}


@router.post("/add-link")
async def add_link(request: AddLinkRequest):
    file_path = _vault_root() / request.path
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
    file_path.write_text(content, encoding="utf-8")
    _log_edit("ADD_LINK", request.path, f"added {link}")
    return {"status": "success", "path": request.path, "entity": request.entity, "message": f"Link {link} added."}