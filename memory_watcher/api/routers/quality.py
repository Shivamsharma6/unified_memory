"""
Memory Quality Scoring for UAMS.
Rates memories on frontmatter completeness, link density, structural quality, content length.
"""

import re
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/memory", tags=["Quality"])


class QualityRequest(BaseModel):
    path: str
    content: str = ""


def score_memory(content: str) -> Dict[str, Any]:
    checks = {}

    # Frontmatter
    fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    has_frontmatter = fm_match is not None
    checks["has_frontmatter"] = has_frontmatter

    fm_content = fm_match.group(1) if has_frontmatter else ""
    checks["has_type"] = "type:" in fm_content
    checks["has_date"] = "date:" in fm_content
    checks["has_tags"] = "tags:" in fm_content

    # Entities
    wikilinks = re.findall(r'\[\[(.*?)\]\]', content)
    checks["wikilink_count"] = len(wikilinks)
    checks["unique_entities"] = len(set(wikilinks))

    # Content body
    body = content[fm_match.end():] if has_frontmatter else content

    headers = re.findall(r'^#{1,3}\s+', body, re.MULTILINE)
    checks["has_headers"] = len(headers) > 0
    checks["header_count"] = len(headers)

    code_blocks = re.findall(r'```', body)
    checks["has_code_blocks"] = len(code_blocks) >= 2

    bullet_points = re.findall(r'^[-*]\s+', body, re.MULTILINE)
    checks["has_bullet_points"] = len(bullet_points) > 0

    word_count = len(body.split())
    checks["word_count"] = word_count
    checks["appropriate_length"] = 50 <= word_count <= 1500

    # Score
    score = 0.0
    max_score = 10.0

    if has_frontmatter: score += 1.5
    if checks["has_type"]: score += 0.5
    if checks["has_date"]: score += 0.5
    if checks["has_tags"]: score += 0.5
    if checks["wikilink_count"] >= 1: score += min(1.5, checks["wikilink_count"] * 0.3)
    if checks["has_headers"]: score += 0.5
    if checks["has_bullet_points"]: score += 0.5
    if checks["has_code_blocks"]: score += 0.5
    if checks["appropriate_length"]: score += 1.0
    elif word_count < 20: score += 0.0
    else: score += 0.3

    if word_count > 300 and not checks["has_headers"]: score -= 1.0

    score = max(0.0, min(1.0, score / max_score))

    return {
        "score": round(score, 3),
        "checks": checks,
        "grade": "A" if score >= 0.8 else "B" if score >= 0.6 else "C" if score >= 0.4 else "D" if score >= 0.2 else "F",
    }


from models.memory_record import get_vault_root, resolve_vault_path


@router.post("/quality")
async def memory_quality(request: QualityRequest):
    if request.content:
        return score_memory(request.content)
    vault_root = get_vault_root()
    try:
        file_path = resolve_vault_path(vault_root, request.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read memory content")
    result = score_memory(content)
    result["path"] = request.path
    return result


@router.post("/quality/batch")
async def batch_quality(paths: list[str]):
    results = []
    vault_root = get_vault_root()
    for path in paths:
        try:
            file_path = resolve_vault_path(vault_root, path)
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    result = score_memory(content)
                    result["path"] = path
                    results.append(result)
                except Exception:
                    results.append({"path": path, "score": 0.0, "error": "read_failed"})
            else:
                results.append({"path": path, "score": 0.0, "error": "not_found"})
        except ValueError as e:
            results.append({"path": path, "score": 0.0, "error": f"invalid_path: {e}"})
    return {"results": results}


