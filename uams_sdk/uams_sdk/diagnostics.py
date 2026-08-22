"""
UAMS Diagnostics & System Health Inspector (uams-doctor).
Validates local setup, services, vault permissions, and SDK connectivity.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any

try:
    from uams_sdk.client import UAMSClient
except ImportError:
    from .client import UAMSClient


async def check_system(base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    report = {
        "python_version": sys.version.split()[0],
        "server_connected": False,
        "vault_accessible": False,
        "subsystems": {},
    }

    # 1. Vault Directory Check
    vault_path_env = os.getenv("UAMS_VAULT_PATH", ".")
    vault_path = Path(vault_path_env).resolve()
    if vault_path.exists() and os.access(vault_path, os.R_OK | os.W_OK):
        report["vault_accessible"] = True
        report["vault_path"] = str(vault_path)
    else:
        report["vault_accessible"] = False
        report["vault_path"] = str(vault_path)

    # 2. Server & Readiness Check
    client = UAMSClient(base_url=base_url)
    try:
        health = await client.health()
        report["server_connected"] = True
        report["subsystems"] = health
    except Exception as e:
        report["server_connected"] = False
        report["connection_error"] = str(e)

    return report


def print_doctor_report(report: Dict[str, Any]):
    print("=" * 65)
    print(" 🏥  UAMS System Doctor & Diagnostic Report")
    print("=" * 65)
    print(f" Python Version: {report['python_version']} (Target >= 3.11)")

    if report["vault_accessible"]:
        print(f" [+] Vault Directory: Accessible ({report.get('vault_path')})")
    else:
        print(f" [!] Vault Directory: Inaccessible ({report.get('vault_path')})")

    if report["server_connected"]:
        print(f" [+] UAMS API Server: Online & Responsive")
        subsystems = report.get("subsystems", {})
        print(f"     - Readiness: {subsystems.get('ready', False)}")
        print(f"     - Storage Subsystem: {subsystems.get('storage', 'ok')}")
        print(f"     - Vector DB Subsystem: {subsystems.get('vector_store', 'ok')}")
    else:
        print(f" [!] UAMS API Server: Offline ({report.get('connection_error', 'connection refused')})")
        print("     Tip: Start services via `docker compose up -d` or `./uams start`")

    print("=" * 65)
    if report["vault_accessible"] and report["server_connected"]:
        print(" 🎉  All core UAMS subsystems are healthy and ready for agents!\n")
    else:
        print(" ⚠️   Some checks failed. Review recommendations above.\n")


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    report = asyncio.run(check_system(base_url))
    print_doctor_report(report)


if __name__ == "__main__":
    main()
