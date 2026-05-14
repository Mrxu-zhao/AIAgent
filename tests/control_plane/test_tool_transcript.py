import json
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.executor import ToolExecutor  # noqa: E402
from tools.spec import ToolExecutionContext, ToolResult, ToolSpec  # noqa: E402
from tools.transcript import ToolTranscriptStore  # noqa: E402


class ToolTranscriptTests(unittest.TestCase):
    def test_execute_many_writes_transcript_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcript = ToolTranscriptStore(Path(tmp) / "tool-runtime" / "tool-transcript.jsonl")

            def handler(_context, payload):
                return ToolResult.ok_result(
                    content=f"dispatched:{payload['task']}",
                    structured_data={"task": payload["task"]},
                    artifacts=["artifact.txt"],
                )

            tool = ToolSpec(
                name="dispatch_task",
                description="dispatch a task",
                input_schema={},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=handler,
            )
            context = ToolExecutionContext(
                task_id="tool-task-3",
                agent_id="architect",
                backend="hermes",
                knowledge_bundle={"paths": [".hermes/team/knowledge/status.md"]},
            )

            ToolExecutor(transcript_store=transcript).execute_many(
                context,
                [(tool, {"task": "设计 tool runtime"})],
            )

            rows = [
                json.loads(line)
                for line in transcript.path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["tool_name"], "dispatch_task")
            self.assertEqual(rows[0]["task_id"], "tool-task-3")
            self.assertEqual(rows[0]["knowledge_paths"], [".hermes/team/knowledge/status.md"])
            self.assertTrue(rows[0]["ok"])


if __name__ == "__main__":
    unittest.main()
