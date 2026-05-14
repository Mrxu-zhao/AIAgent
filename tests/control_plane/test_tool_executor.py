import threading
import time
import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.executor import ToolExecutor  # noqa: E402
from tools.spec import ToolExecutionContext, ToolResult, ToolSpec  # noqa: E402


class ToolExecutorTests(unittest.TestCase):
    def test_execute_many_keeps_request_order_for_parallel_safe_tools(self):
        started = []
        finished = []
        lock = threading.Lock()

        def handler(_context, payload):
            with lock:
                started.append(payload["name"])
            time.sleep(payload["delay"])
            with lock:
                finished.append(payload["name"])
            return ToolResult.ok_result(content=payload["name"])

        alpha = ToolSpec(
            name="alpha",
            description="parallel alpha",
            input_schema={},
            is_read_only=True,
            is_concurrency_safe=True,
            handler=handler,
        )
        beta = ToolSpec(
            name="beta",
            description="parallel beta",
            input_schema={},
            is_read_only=True,
            is_concurrency_safe=True,
            handler=handler,
        )
        context = ToolExecutionContext(task_id="tool-task-1", agent_id="architect", backend="hermes")

        results = ToolExecutor().execute_many(
            context,
            [
                (alpha, {"name": "alpha", "delay": 0.03}),
                (beta, {"name": "beta", "delay": 0.0}),
            ],
        )

        self.assertEqual([item.content for item in results], ["alpha", "beta"])
        self.assertEqual(sorted(started), ["alpha", "beta"])
        self.assertEqual(sorted(finished), ["alpha", "beta"])

    def test_execute_many_runs_non_concurrency_safe_tools_sequentially(self):
        trace = []

        def handler(_context, payload):
            trace.append(f"start:{payload['name']}")
            time.sleep(0.01)
            trace.append(f"end:{payload['name']}")
            return ToolResult.ok_result(content=payload["name"])

        write_a = ToolSpec(
            name="write-a",
            description="write a",
            input_schema={},
            is_read_only=False,
            is_concurrency_safe=False,
            handler=handler,
        )
        write_b = ToolSpec(
            name="write-b",
            description="write b",
            input_schema={},
            is_read_only=False,
            is_concurrency_safe=False,
            handler=handler,
        )
        context = ToolExecutionContext(task_id="tool-task-2", agent_id="backend-1", backend="hermes")

        results = ToolExecutor().execute_many(
            context,
            [
                (write_a, {"name": "write-a"}),
                (write_b, {"name": "write-b"}),
            ],
        )

        self.assertEqual([item.content for item in results], ["write-a", "write-b"])
        self.assertEqual(
            trace,
            ["start:write-a", "end:write-a", "start:write-b", "end:write-b"],
        )

    def test_execute_many_denies_write_tool_for_viewer(self):
        tool = ToolSpec(
            name="route_task",
            description="route task",
            input_schema={},
            is_read_only=False,
            is_concurrency_safe=False,
            handler=lambda *_: ToolResult.ok_result(content="should-not-run"),
            action="tool.route",
            requires_approval=False,
            is_sensitive=False,
        )
        context = ToolExecutionContext(
            task_id="tool-task-9",
            agent_id="architect",
            backend="hermes",
            intent={},
            knowledge_bundle={},
            actor="viewer",
            session_id="session-1",
        )

        result = ToolExecutor().execute_many(context, [(tool, {"task": "review"})])[0]

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "PERMISSION_DENIED")

    def test_execute_many_requires_approval_for_sensitive_tool(self):
        tool = ToolSpec(
            name="dispatch_task",
            description="dispatch task",
            input_schema={},
            is_read_only=False,
            is_concurrency_safe=False,
            handler=lambda *_: ToolResult.ok_result(content="should-not-run"),
            action="provider.openclaw.live",
            requires_approval=True,
            is_sensitive=True,
        )
        context = ToolExecutionContext(
            task_id="tool-task-10",
            agent_id="architect",
            backend="openclaw",
            intent={},
            knowledge_bundle={},
            actor="admin",
            session_id="session-2",
        )

        result = ToolExecutor().execute_many(context, [(tool, {"task": "execute"})])[0]

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "APPROVAL_REQUIRED")


if __name__ == "__main__":
    unittest.main()
