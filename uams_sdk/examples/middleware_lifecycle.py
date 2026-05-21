import asyncio
from uams_sdk import AutonomousMemoryMiddleware

async def run_lifecycle():
    middleware = AutonomousMemoryMiddleware()
    
    user_prompt = "I keep getting a FileLockError when trying to edit AGENTS.md. Can you fix the python script?"
    
    print("--- 1. PRE-TASK (Context Injection) ---")
    augmented_prompt = await middleware.pre_task(user_prompt)
    print(augmented_prompt[:500] + "...\n[TRUNCATED FOR DISPLAY]\n")
    
    # Mocking the LLM doing the work...
    print("--- 2. AGENT EXECUTION (Mocked) ---")
    print("Agent is reading context, extracting the PatchScript procedure, and fixing the code...\n")
    
    mock_agent_response = """
I have analyzed the context. The FileLockError occurs because the watchdog observer holds a lock.
The solution was to implement an asynchronous lock release mechanism in the debouncer loop before opening the file for writing.
I fixed this by adding `await asyncio.sleep(0.1)` after observer events and using `aiofiles` for non-blocking file operations.
The code has been successfully updated and tested.
"""
    
    print("--- 3. POST-TASK (Knowledge Extraction) ---")
    await middleware.post_task(user_prompt, mock_agent_response)

if __name__ == "__main__":
    asyncio.run(run_lifecycle())
