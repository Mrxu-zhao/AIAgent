import time
from uuid import uuid4

from models import EventType, TaskStatus, TaskEvent


class ControlPlaneExecutor:
    def __init__(self, store):
        self.store = store

    def build_dispatch_command(self, adapter, agent_id: str, task: str):
        return adapter.build_dispatch_command(agent_id, task)

    def execute_task(self, card, adapter, command_runner):
        command = self.build_dispatch_command(adapter, card.owner_agent, card.goal)
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
            )
        )
        result = command_runner(command)
        if result.returncode == 0:
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
                )
            )
            return {"success": True, "command": command, "stdout": result.stdout, "stderr": result.stderr}

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
            )
        )
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
