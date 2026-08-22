import importlib
import py_compile
import sys
from pathlib import Path


def test_scripts_compile_without_syntax_errors():
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    embed_upgrade_path = scripts_dir / "embed_upgrade.py"
    reindex_path = scripts_dir / "reindex.py"

    py_compile.compile(str(embed_upgrade_path), doraise=True)
    py_compile.compile(str(reindex_path), doraise=True)


def test_embed_upgrade_has_valid_pointstruct_construction():
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    content = (scripts_dir / "embed_upgrade.py").read_text(encoding="utf-8")
    assert " models.PointStruct(" not in content
    assert "qdrant_models.PointStruct(" in content

