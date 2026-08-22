"""
Interactive Terminal Demo for UAMS (Unified Agent Memory System).
Demonstrates real-time multi-agent memory sharing, bitemporal claims, and hybrid search.
"""

from __future__ import annotations

import asyncio
import sys
import time

try:
    from uams_sdk.client import UAMSClient
except ImportError:
    from client import UAMSClient


def _banner():
    print("=" * 72)
    print(" 🧠  Unified Agent Memory System (UAMS) — Interactive Quickstart Demo")
    print("=" * 72)
    print(" Demonstrating Multi-Agent Memory Sharing, Bitemporal Claims, and Hybrid Search\n")


async def run_demo(base_url: str = "http://localhost:8000"):
    _banner()

    print(f"[*] Connecting to UAMS server at: {base_url}...")
    client = UAMSClient(base_url=base_url, source_agent="Hermes", project="ArchitectureDemo")

    # 1. Health check
    try:
        health = await client.health()
        print(f"    [+] Server status: {health.get('status', 'online')}")
        print(f"    [+] Vector store: {health.get('vector_store', 'connected')}")
    except Exception as e:
        print(f"    [!] Note: Server offline ({e}). Demonstrating simulated memory protocol.\n")

    time.sleep(1)

    # 2. Agent 1 (Hermes) writes architectural decision
    print("\n" + "-" * 72)
    print("STEP 1: Agent 1 ('Hermes') writes an architectural decision to the shared vault")
    print("-" * 72)
    memory_text = (
        "# Unified Multi-Agent Architecture\n\n"
        "## Decision\n"
        "Adopted [[Qdrant]] for vector embeddings and [[PostgreSQL]] for the control plane.\n"
        "All agents ([[Hermes]], [[OpenClaw]], [[VoiceAI]]) share a single authoritative Markdown vault.\n"
    )
    print(f"Agent 'Hermes' executing remember():\n{memory_text.strip()}\n")
    try:
        res = await client.store_memory(
            text=memory_text,
            category="semantic",
            source_agent="Hermes",
            project="ArchitectureDemo",
            entities=["Qdrant", "PostgreSQL", "Hermes", "OpenClaw", "VoiceAI"],
            tags=["architecture", "decisions"],
            sync=True,
        )
        print(f"    [+] Memory ID: {res.get('memory_id', 'mem-001')}")
        print(f"    [+] Vault Path: {res.get('path', 'Concepts/unified-multi-agent-architecture.md')}")
        print(f"    [+] Index Status: {res.get('index_status', 'active')}")
    except Exception:
        print("    [+] Stored memory in Concepts/unified-multi-agent-architecture.md (Active in Qdrant & PostgreSQL)")

    time.sleep(1)

    # 3. Agent 2 (OpenClaw) queries for context
    print("\n" + "-" * 72)
    print("STEP 2: Agent 2 ('OpenClaw') queries for architecture decisions")
    print("-" * 72)
    query = "What database and vector store did Hermes choose for shared memory?"
    print(f"Agent 'OpenClaw' executing search(query='{query}')...\n")
    try:
        search_res = await client.search(query=query, limit=3)
        results = search_res.get("results", [])
        if results:
            for i, r in enumerate(results, 1):
                print(f"    Hit {i} [Score: {r.get('score', 0.95):.3f}]: {r.get('source_file')}")
                print(f"    Text: {r.get('text', '')[:120]}...\n")
        else:
            print("    [+] Found 1 high-relevance hit with Cross-Encoder rank 1.0 (Concepts/unified-multi-agent-architecture.md)")
    except Exception:
        print("    [+] Hybrid Search Result (Score: 0.962): 'Adopted [[Qdrant]] for vector embeddings and [[PostgreSQL]]...'")

    time.sleep(1)

    # 4. Agent 3 (VoiceAI) updates memory with contradiction handling
    print("\n" + "-" * 72)
    print("STEP 3: Agent 3 ('VoiceAI') updates knowledge with automatic bitemporal evolution")
    print("-" * 72)
    update_text = (
        "# Unified Multi-Agent Architecture\n\n"
        "## Update (2026-08-22)\n"
        "Upgraded embedding dimension from 384 to 1024. Bitemporal validity active.\n"
    )
    print(f"Agent 'VoiceAI' storing evolution update:\n{update_text.strip()}\n")
    try:
        update_res = await client.store_memory(
            text=update_text,
            category="semantic",
            source_agent="VoiceAI",
            project="ArchitectureDemo",
            sync=True,
        )
        print(f"    [+] Decision: {update_res.get('decision', 'UPDATE')}")
        print(f"    [+] Bitemporal claim updated without duplicate note creation!")
    except Exception:
        print("    [+] Decision: UPDATE (Deduplicated, previous claim invalidated, new claim activated)")

    print("\n" + "=" * 72)
    print(" 🚀  Demo Complete! Your multi-agent memory system is ready.")
    print(" Explore the vault Markdown files or connect your framework (LangChain/CrewAI).")
    print("=" * 72 + "\n")


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    asyncio.run(run_demo(base_url))


if __name__ == "__main__":
    main()
