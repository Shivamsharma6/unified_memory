"""
End-to-End Multi-Agent Team Collaboration Demo.
Demonstrates 3 specialized agents (Planner, Coder, Reviewer) sharing a single UAMS brain.
"""

from __future__ import annotations

import asyncio
from uams_sdk.client import UAMSClient


async def planner_agent(client: UAMSClient):
    print("\n[🤖 1. Planner Agent]")
    plan_text = (
        "# Feature Implementation Plan: Auth Middleware\n\n"
        "## Decisions\n"
        "Adopted JWT authentication with 24-hour expiration for all microservices.\n"
        "All services must query [[AuthService]] for token verification.\n"
    )
    print("Planner storing feature architecture in shared memory...")
    res = await client.store_memory(
        text=plan_text,
        category="semantic",
        source_agent="PlannerAgent",
        project="AuthMigration",
        entities=["AuthService", "JWT"],
        tags=["auth", "architecture", "plan"],
        sync=True,
    )
    print(f"Plan stored! Memory ID: {res.get('memory_id')}")


async def coder_agent(client: UAMSClient):
    print("\n[🤖 2. Coder Agent]")
    coder_client = UAMSClient(source_agent="CoderAgent", project="AuthMigration")
    print("Coder Agent querying shared memory for auth architecture plan...")
    search_res = await coder_client.search("What token system and expiration was decided for auth?")
    top_hit = search_res.get("results", [{}])[0]
    print(f"Retrieved Context: {top_hit.get('text', '')[:100]}...\n")

    code_outcome = (
        "# Implementation Task: JWT Middleware Implementation\n\n"
        "Implemented JWT middleware in Python FastAPI connecting to [[AuthService]].\n"
        "Tokens expire in 24 hours per [[PlannerAgent]] specifications.\n"
    )
    print("Coder storing implementation summary in shared memory...")
    res = await coder_client.store_memory(
        text=code_outcome,
        category="episodic",
        source_agent="CoderAgent",
        project="AuthMigration",
        sync=True,
    )
    print(f"Implementation recorded! Memory ID: {res.get('memory_id')}")


async def reviewer_agent(client: UAMSClient):
    print("\n[🤖 3. Reviewer Agent]")
    reviewer_client = UAMSClient(source_agent="ReviewerAgent", project="AuthMigration")
    print("Reviewer Agent querying for both plan and implementation...")
    review_query = "What did Planner decide vs what did Coder implement for AuthService?"
    search_res = await reviewer_client.search(review_query, limit=2)
    for i, r in enumerate(search_res.get("results", []), 1):
        print(f"Evidence {i} [{r.get('source_file')}]: {r.get('text', '')[:80]}...")

    print("\nReview Complete: Implementation matches architectural specification perfectly!")


async def main():
    print("=" * 65)
    print(" 🚀  UAMS Multi-Agent Collaboration Simulation")
    print("=" * 65)

    client = UAMSClient(base_url="http://localhost:8000")
    try:
        await planner_agent(client)
        await coder_agent(client)
        await reviewer_agent(client)
    except Exception as e:
        print(f"Note: Run with a live server for live execution. (Offline trace: {e})")

    print("\n" + "=" * 65)
    print(" Multi-Agent Simulation Complete!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
