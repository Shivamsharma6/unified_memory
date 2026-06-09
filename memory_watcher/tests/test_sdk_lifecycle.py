import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "uams_sdk"))

from uams_sdk.client import UAMSClient


class RecordingClient(UAMSClient):
    def __init__(self):
        super().__init__(base_url="http://uams.test")
        self.requests = []

    async def _request(self, method, endpoint, json_data=None, use_cache=False):
        self.requests.append(
            {
                "method": method,
                "endpoint": endpoint,
                "json": json_data or {},
                "use_cache": use_cache,
            }
        )
        if endpoint == "/procedures":
            return {"procedures": ["Procedure memory"]}
        if endpoint == "/context":
            return {"context": "Historical context"}
        if endpoint == "/remember":
            return {"status": "success", "path": "Daily/test.md", "indexed": True}
        raise AssertionError(f"Unexpected request: {method} {endpoint}")


class TestSDKLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_begin_task_fetches_procedures_and_context(self):
        client = RecordingClient()

        result = await client.begin_task("Fix login timeout", max_tokens=700)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["procedures"], ["Procedure memory"])
        self.assertEqual(result["context"], "Historical context")
        self.assertIn("Always call", result["memory_policy"])
        self.assertEqual(
            [(r["endpoint"], r["json"]) for r in client.requests],
            [
                ("/procedures", {"task": "Fix login timeout"}),
                ("/context", {"task": "Fix login timeout", "max_tokens": 700}),
            ],
        )

    async def test_end_task_stores_distilled_lifecycle_memory(self):
        client = RecordingClient()

        result = await client.end_task(
            task="Fix login timeout",
            outcome="Added a regression test and fixed the timeout handling.",
            files=["auth/session.py"],
            decisions=["Keep timeout policy local-first"],
            fixes=["Adjusted session refresh grace window"],
            entities=["Login Timeout"],
        )

        self.assertTrue(result["ok"])
        remember_request = client.requests[-1]
        self.assertEqual(remember_request["endpoint"], "/remember")
        self.assertEqual(remember_request["json"]["category"], "episodic")
        self.assertIn("#auto-distilled", remember_request["json"]["tags"])
        self.assertIn("[[Login Timeout]]", remember_request["json"]["text"])
        self.assertIn("auth/session.py", remember_request["json"]["text"])


if __name__ == "__main__":
    unittest.main()
