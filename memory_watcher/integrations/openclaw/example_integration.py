import asyncio
from middleware import MemoryMiddleware
from tools import search_memory, store_memory

async def mock_agent_loop():
    middleware = MemoryMiddleware()
    
    user_input = "What were the core rules for the memory vault?"
    
    # 1. Pre-process (Middleware automatically searches and augments)
    augmented_prompt = await middleware.pre_process_prompt(user_input)
    
    print("--- Augmented Prompt Sent to LLM ---")
    print(augmented_prompt)
    print("------------------------------------")
    
    # 2. LLM Execution (Mocked)
    # The LLM reads the augmented prompt and might decide to use a tool
    print("\n--- LLM Tool Execution ---")
    tool_result = await search_memory("AGENTS.md core rules")
    print(tool_result)

if __name__ == "__main__":
    asyncio.run(mock_agent_loop())
