import logging
import re
from typing import Dict, Any, List, Optional
from .client import UAMSClient

logger = logging.getLogger(__name__)

class AutonomousMemoryMiddleware:
    """
    Advanced Automatic Memory Middleware for Hermes & OpenClaw.
    Automatically orchestrates memory injection before tasks and knowledge extraction after tasks.
    """
    def __init__(self, client: Optional[UAMSClient] = None):
        self.client = client or UAMSClient()
        self.max_context_tokens = 2000

    def _detect_task_type(self, prompt: str) -> str:
        """1. Detect task type via heuristic."""
        q = prompt.lower()
        if any(w in q for w in ["code", "script", "debug", "error", "refactor", "build"]):
            return "coding"
        if any(w in q for w in ["explain", "research", "what is", "why", "how does"]):
            return "research"
        return "general"

    async def pre_task(self, user_prompt: str) -> str:
        """
        Executed BEFORE the agent sees the prompt.
        1. Detect task type
        2. Retrieve procedures first
        3. Retrieve relevant memory automatically
        4. Compress context
        5. Inject memory into prompt
        """
        task_type = self._detect_task_type(user_prompt)
        logger.info(f"[UAMS Middleware] Task detected as '{task_type}'. Fetching memory...")

        # 3. Retrieve Procedures First
        procedures = await self.client.retrieve_procedures(user_prompt)
        proc_text = "\n".join(procedures) if procedures else "No specific operating procedures found."

        # 2 & 4. Retrieve & Compress Context
        # The API's /context endpoint natively handles extraction, graph-expansion, and compression
        context = await self.client.retrieve_context(user_prompt, max_tokens=self.max_context_tokens)
        context_text = context if context else "No historical context found."

        # 5. Inject memory into prompt
        augmented_prompt = f"""<uams_context>
[System] Task Type: {task_type.capitalize()}

[Operating Procedures]
{proc_text}

[Historical Memory & Graph Context]
{context_text}
</uams_context>

User Request: {user_prompt}"""

        return augmented_prompt

    def _extract_insights(self, response: str) -> List[Dict[str, Any]]:
        """
        Heuristic to extract durable knowledge from the agent's response.
        In production, this could be a lightweight LLM call.
        """
        insights = []
        
        # Look for explicit decisions, fixes, or procedures in the text
        fix_match = re.search(r'(?i)(?:I fixed this by|The solution was|Resolution:)(.*?)(?:\n\n|$)', response, re.DOTALL)
        if fix_match:
            insights.append({"text": f"Fix applied: {fix_match.group(1).strip()}", "category": "procedural"})
            
        decision_match = re.search(r'(?i)(?:I have decided to|Decision:)(.*?)(?:\n\n|$)', response, re.DOTALL)
        if decision_match:
            insights.append({"text": f"Decision made: {decision_match.group(1).strip()}", "category": "semantic"})

        # Fallback to episodic if we just completed a significant task successfully
        if not insights and ("successfully" in response.lower() or "completed" in response.lower()):
            # We'll just take the first sentence as an episodic summary
            first_sentence = response.split('.')[0] + "."
            insights.append({"text": f"Task completed: {first_sentence}", "category": "episodic"})

        return insights

    async def post_task(self, user_prompt: str, agent_response: str) -> None:
        """
        Executed AFTER the agent finishes the task.
        1. Determine if durable knowledge was generated
        2. Distill reusable insights
        3. Store procedural memory
        4. Update graph relationships (Triggered by the store endpoint internally)
        """
        logger.info("[UAMS Middleware] Evaluating task output for durable knowledge...")
        
        insights = self._extract_insights(agent_response)
        
        if not insights:
            logger.debug("[UAMS Middleware] No durable knowledge detected in response.")
            return

        for insight in insights:
            logger.info(f"[UAMS Middleware] Distilled Insight ({insight['category']}): {insight['text'][:50]}...")
            
            # 3 & 4. Store memory and update relationships
            # The UAMS watcher handles graph relationship updates upon file creation
            await self.client.store_memory(
                text=f"Derived from task: '{user_prompt}'\n\n{insight['text']}", 
                category=insight['category'],
                tags=["#auto-distilled", f"#{self._detect_task_type(user_prompt)}"]
            )
            
        logger.info("[UAMS Middleware] Knowledge successfully synchronized to the Unified Memory System.")
