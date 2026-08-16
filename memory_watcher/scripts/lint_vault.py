#!/usr/bin/env python3
"""CLI Linter for UAMS Markdown memory vault."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

WATCHER_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = WATCHER_ROOT.parent
sys.path.insert(0, str(WATCHER_ROOT))

from api.routers.validation import validate_entire_vault


async def run_linter(args: argparse.Namespace) -> int:
    os.environ["UAMS_VAULT_PATH"] = str(Path(args.vault).resolve())
    summary = await validate_entire_vault()

    print("\n" + "=" * 60)
    print(" 🛡️  UAMS VAULT LINT REPORT")
    print("=" * 60)
    print(f"  Total Notes Scanned:          {summary.total_scanned}")
    print(f"  Valid Notes:                  {summary.valid_count}")
    print(f"  Notes with Errors:            {summary.invalid_count}")
    print(f"  Warnings:                     {summary.warning_count}")
    print(f"  Unresolved Wikilinks:         {summary.broken_wikilinks_count}")
    print(f"  Notes Lacking Explicit ID:    {summary.notes_missing_explicit_id}")
    print("=" * 60)

    if summary.issues:
        print("\n=== Issues Summary (Top 25) ===")
        for issue in summary.issues[:25]:
            badge = "❌ [ERROR]" if issue["severity"] == "error" else ("⚠️  [WARN]" if issue["severity"] == "warning" else "ℹ️  [INFO]")
            print(f"{badge} {issue['path']}: {issue['code']} - {issue['message']}")

    if summary.invalid_count > 0 and args.strict:
        print("\n❌ Vault linting failed under strict mode.")
        return 1

    print("\n✅ Vault linting passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", default=str(VAULT_ROOT), help="Path to the memory vault root")
    parser.add_argument("--strict", action="store_true", help="Fail with exit code 1 if errors found")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(run_linter(args))


if __name__ == "__main__":
    raise SystemExit(main())
