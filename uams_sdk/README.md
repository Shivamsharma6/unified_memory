# UAMS Shared Memory SDK

A unified, asynchronous Python SDK for the **Unified Agent Memory System (UAMS)**. 
Designed to be shared natively by both **Hermes** and **OpenClaw** agents.

## Features
- **Unified Client:** One standard interface for all agents.
- **Async First:** Built on `httpx` for non-blocking operations.
- **Intelligent Caching:** Built-in TTL caching with automatic invalidation on writes.
- **Full API Coverage:** Semantic search, graph traversal, context compression, and writes.

## Installation
```bash
pip install -e .
```

## Usage
```python
import asyncio
from uams_sdk import UAMSClient

async def main():
    client = UAMSClient(base_url="http://localhost:8000")
    
    # Retrieve optimized context
    context = await client.retrieve_context("How do I fix Docker file locks?")
    print(context)
    
    # Store a new memory
    await client.store_memory("User prefers dark mode.", tags=["#preferences"])

asyncio.run(main())
```
