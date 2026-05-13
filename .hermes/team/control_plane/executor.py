import time
from uuid import uuid4

from adapters import get_executor_adapter
from models import EventType, TaskEvent, TaskStatus


class ControlPlaneExecutor:
    def __init__(self, store):
        self.store = store

    def build_dispatch_command(self, adapter, agent_id: str, task: str):
        return adapter.build_dispatch_command(agent_id, task)

    def _is_version_conflict(self, exc):
        return exc.__class__.__name__ == "VersionConflictError"

    def resolve_adapter(self, card, adapter):
        if getattr(card, "executor_backend", None):
            return get_executor_adapter(card.executor_backend)
        return adapter

    def execute_task(self, card, adapter, command_runner):
        adapter = self.resolve_adapter(card, adapter)
        command = self.build_dispatch_command(adapter, card.owner_agent, card.goal)
        snapshot = self.store.read_snapshot(card.task_id)
        expected_start_version = snapshot["version"]

        try:
            self.store.append_event(
                TaskEvent(
                    event_id=f"evt-{uuid4().hex}",
                    task_id=card.task_id,
                    event_type=EventType.TASK_STARTED,
                    agent_id=card.owner_agent,
                    timestamp=time.time(),
                    attempt=1,
                    status_before=TaskStatus.READY,
                    status_after=TaskStatus.RUNNING,
                    summary="task started",
                    artifact_refs=[],
                    lock_scope={
                        "files": card.lock_scope.files,
                        "modules": card.lock_scope.modules,
                        "contracts": card.lock_scope.contracts,
                    },
                    depends_on=card.dependencies,
                    metrics_delta={},
                    error_code=None,
                ),
                expected_version=expected_start_version,
            )
        except Exception as exc:
            if not self._is_version_conflict(exc):
                raise
            return {
                "success": False,
                "command": command,
                "stdout": "",
                "stderr": str(exc),
                "error_code": "VERSION_CONFLICT",
            }

        expected_terminal_version = expected_start_version + 1
        result = command_runner(command)
        if result.returncode == 0:
            try:
                self.store.append_event(
                    TaskEvent(
                        event_id=f"evt-{uuid4().hex}",
                        task_id=card.task_id,
                        event_type=EventType.TASK_COMPLETED,
                        agent_id=card.owner_agent,
                        timestamp=time.time(),
                        attempt=1,
                        status_before=TaskStatus.RUNNING,
                        status_after=TaskStatus.DONE,
                        summary="task completed",
                        artifact_refs=[],
                        lock_scope={
                            "files": card.lock_scope.files,
                            "modules": card.lock_scope.modules,
                            "contracts": card.lock_scope.contracts,
                        },
                        depends_on=card.dependencies,
                        metrics_delta={},
                        error_code=None,
                    ),
                    expected_version=expected_terminal_version,
                )
            except Exception as exc:
                if not self._is_version_conflict(exc):
                    raise
                return {
                    "success": False,
                    "command": command,
                    "stdout": result.stdout,
                    "stderr": str(exc),
                    "error_code": "VERSION_CONFLICT",
                }
            return {"success": True, "command": command, "stdout": result.stdout, "stderr": result.stderr}

        try:
            self.store.append_event(
                TaskEvent(
                    event_id=f"evt-{uuid4().hex}",
                    task_id=card.task_id,
                    event_type=EventType.TASK_FAILED,
                    agent_id=card.owner_agent,
                    timestamp=time.time(),
                    attempt=1,
                    status_before=TaskStatus.RUNNING,
                    status_after=TaskStatus.FAILED,
                    summary="task failed",
                    artifact_refs=[],
                    lock_scope={
                        "files": card.lock_scope.files,
                        "modules": card.lock_scope.modules,
                        "contracts": card.lock_scope.contracts,
                    },
                    depends_on=card.dependencies,
                    metrics_delta={},
                    error_code=f"PROCESS_EXIT_{result.returncode}",
                ),
                expected_version=expected_terminal_version,
            )
        except Exception as exc:
            if not self._is_version_conflict(exc):
                raise
            return {
                "success": False,
                "command": command,
                "stdout": result.stdout,
                "stderr": str(exc),
                "error_code": "VERSION_CONFLICT",
            }
        return {"success": False, "command": command, "stdout": result.stdout, "stderr": result.stderr}

    def compute_blocked_tasks(self, failed_task_id, graph):
        return sorted(task_id for task_id, deps in graph.items() if failed_task_id in deps)

    def classify_failure(self, error_code: str):
        if error_code.startswith("TRANSIENT_"):
            return "transient"
        if error_code.startswith("DEPENDENCY_"):
            return "dependency"
        return "deterministic"

    def should_retry(self, attempt: int, max_attempts: int, failure_kind: str):
        return failure_kind == "transient" and attempt < max_attempts
