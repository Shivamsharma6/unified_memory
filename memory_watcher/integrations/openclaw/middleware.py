import logging
from typing import Dict, Any, Tuple
from .client import UAMSClient

logger = logging.getLogger(__name__)

class MemoryMiddleware:
    """
    Middleware hook for OpenClaw/Hermes agent loop.
    Automatically intercepts user prompts, fetches relevant compressed context,
    and injects it before the LLM generates a response.
    """
    def __init__(self):
        self.client = UAMSClient()
        self.max_context_tokens = 1500

    async def pre_process_prompt(self, user_prompt: str) -> str:
        """
        Hook this before sending the prompt to the LLM.
        """
        logger.info(f"Auto-searching memory for prompt: {user_prompt[:50]}...")
        
        # 1. Fetch compressed context optimized for token limits
        context_res = await self.client.get_context(task=user_prompt, max_tokens=self.max_context_tokens)
        
        if "error" in context_res or not context_res.get("context"):
            logger.debug("No relevant context found or memory system unavailable.")
            return user_prompt
            
        context_str = context_res["context"]
        tokens_used = context_res.get("tokens", 0)
        
        logger.info(f"Retrieved {tokens_used} tokens of memory context.")

        # 2. Inject context into the prompt
        augmented_prompt = (
            f"You have access to the following relevant memories and context:\n"
            f"<memory_context>\n{context_str}\n</memory_context>\n\n"
            f"User Request: {user_prompt}"
        )
        return augmented_prompt

    async def post_process_response(self, user_prompt: str, agent_response: str):
        """
        Hook this after the LLM generates a response.
        Optionally parses the response for implicit 'store' commands, or 
        logs the conversation turn to conversational memory.
        """
        # Conversational memory logging could happen here asynchronously
        pass
