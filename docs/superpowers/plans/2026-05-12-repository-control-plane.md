# Repository Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在全仓库之上建立第一版仓库级控制平面，支持任务卡、事件流、状态仓、冲突检测、失败隔离、聚合报告与调度框架专项回归验证，并打通 `Hermes` 直接执行路径且为 `OpenClaw` 预留适配接口。

**Architecture:** 新增 `.hermes/team/control_plane/` 作为仓库级治理层，先提供任务模型、事件日志、状态快照、冲突检测与执行器，再把 `.hermes/team/调度框架` 的 P0 正确性修复纳入该控制平面统一管理。执行器采用适配器模式：`HermesExecutorAdapter` 在第一阶段真正调用现有 `hermes team dispatch` / `team-dispatch.sh`，`OpenClawExecutorAdapter` 仅提供统一接口与未实现占位，避免第一阶段扩散成双后端兼容项目。测试使用标准库 `unittest`，性能基线与报告通过 Python 脚本和 JSON/Markdown 产物落盘。

**Tech Stack:** Python 3、dataclasses、pathlib、json、threading、time、subprocess、unittest、现有 `.hermes/team/调度框架`

---

## 文件结构

- Create: `.hermes/team/control_plane/__init__.py`
- Create: `.hermes/team/control_plane/models.py`
- Create: `.hermes/team/control_plane/store.py`
- Create: `.hermes/team/control_plane/conflicts.py`
- Create: `.hermes/team/control_plane/executor.py`
- Create: `.hermes/team/control_plane/adapters.py`
- Create: `.hermes/team/control_plane/baseline.py`
- Create: `.hermes/team/control_plane/aggregator.py`
- Create: `.hermes/team/control_plane/reporting.py`
- Create: `.hermes/team/control_plane/tasks.py`
- Create: `.hermes/team/control_plane/README.md`
- Create: `tests/control_plane/__init__.py`
- Create: `tests/control_plane/test_models.py`
- Create: `tests/control_plane/test_store.py`
- Create: `tests/control_plane/test_conflicts.py`
- Create: `tests/control_plane/test_executor.py`
- Create: `tests/control_plane/test_adapters.py`
- Create: `tests/control_plane/test_baseline.py`
- Create: `tests/control_plane/test_aggregator.py`
- Modify: `.hermes/team/调度框架/core/monitor.py`
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Modify: `.hermes/team/调度框架/cli/team-cli.py`
- Modify: `.hermes/team/调度框架/README_v2.md`
- Create: `.hermes/team/control_plane/artifacts/.gitkeep`
- Create: `.hermes/team/control_plane/state/.gitkeep`
- Create: `.hermes/team/control_plane/events/.gitkeep`

## 任务拆分原则

- 先交付协议与状态底座，再交付执行器与冲突治理。
- 执行器层采用 `Hermes` 直接执行、`OpenClaw` 预留适配接口 的单实装策略。
- 在控制平面底座稳定后，再修复调度框架 P0 正确性问题。
- 性能基线、聚合器和最终报告作为最后一层，消费前面任务产物。
- 每个任务完成后都要运行对应测试，并提交一次小粒度 commit。

### Task 1: 控制平面任务模型与目录骨架

**Files:**
- Create: `.hermes/team/control_plane/__init__.py`
- Create: `.hermes/team/control_plane/models.py`
- Create: `.hermes/team/control_plane/tasks.py`
- Create: `tests/control_plane/__init__.py`
- Create: `tests/control_plane/test_models.py`

- [ ] **Step 1: 写任务模型失败测试**

```python
import unittest

from .test_support import load_control_plane_module

models = load_control_plane_module("models")


class TaskModelTests(unittest.TestCase):
    def test_task_card_requires_unique_identity_fields(self):
        card = models.TaskCard(
            task_id="WS-A-P0-001",
            title="修复监控死锁",
            goal="让 dashboard 调用可返回",
            scope=[".hermes/team/调度框架/core/monitor.py"],
            lock_scope=models.LockScope(
                files=[".hermes/team/调度框架/core/monitor.py"],
                modules=["monitor"],
                contracts=[],
            ),
            inputs=["assessment_report_2026-05-12.md"],
            outputs=["monitor fix diff"],
            dependencies=[],
            owner_agent="backend-1",
            review_agent="architect",
            priority=models.TaskPriority.P0,
            timeout_seconds=1800,
            retry_policy=models.RetryPolicy(max_attempts=2, backoff_seconds=[0, 60]),
            rollback_policy=models.RollbackPolicy(mode="code"),
            acceptance_criteria=["dashboard 调用可返回"],
        )

        self.assertEqual(card.task_id, "WS-A-P0-001")
        self.assertEqual(card.status, models.TaskStatus.PLANNED)
        self.assertEqual(card.priority.value, "P0")

    def test_task_event_captures_state_transition(self):
        event = models.TaskEvent(
            event_id="evt-001",
            task_id="WS-B-P1-001",
            event_type=models.EventType.TASK_STARTED,
            agent_id="backend-2",
            timestamp=1710000000.0,
            attempt=1,
            status_before=models.TaskStatus.READY,
            status_after=models.TaskStatus.RUNNING,
            summary="开始执行协议建模",
            artifact_refs=[],
            lock_scope={"files": [], "modules": [], "contracts": []},
            depends_on=[],
            metrics_delta={},
            error_code=None,
        )

        self.assertEqual(event.status_after, models.TaskStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 添加测试辅助模块并运行失败**

```python
# tests/control_plane/test_support.py
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROL_PLANE_DIR = ROOT / ".hermes" / "team" / "control_plane"


def load_control_plane_module(name: str):
    file_path = CONTROL_PLANE_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"control_plane_{name}", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
```

Run: `python -m unittest tests.control_plane.test_models -v`  
Expected: FAIL with `FileNotFoundError` or import failure for `models.py`

- [ ] **Step 3: 写最小任务模型实现**

```python
# .hermes/team/control_plane/models.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TaskPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class TaskStatus(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    REVIEWING = "reviewing"
    DONE = "done"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class EventType(str, Enum):
    TASK_REGISTERED = "task_registered"
    TASK_READY = "task_ready"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_BLOCKED = "task_blocked"
    TASK_CONFLICT_DETECTED = "task_conflict_detected"
    TASK_RETRYING = "task_retrying"
    TASK_FAILED = "task_failed"
    TASK_ROLLED_BACK = "task_rolled_back"
    TASK_COMPLETED = "task_completed"
    ARTIFACT_PUBLISHED = "artifact_published"
    REVIEW_PASSED = "review_passed"
    REVIEW_FAILED = "review_failed"


@dataclass
class LockScope:
    files: List[str]
    modules: List[str]
    contracts: List[str]


@dataclass
class RetryPolicy:
    max_attempts: int
    backoff_seconds: List[int]


@dataclass
class RollbackPolicy:
    mode: str


@dataclass
class TaskCard:
    task_id: str
    title: str
    goal: str
    scope: List[str]
    lock_scope: LockScope
    inputs: List[str]
    outputs: List[str]
    dependencies: List[str]
    owner_agent: str
    review_agent: str
    priority: TaskPriority
    timeout_seconds: int
    retry_policy: RetryPolicy
    rollback_policy: RollbackPolicy
    acceptance_criteria: List[str]
    status: TaskStatus = TaskStatus.PLANNED
    evidence: List[str] = field(default_factory=list)


@dataclass
class TaskEvent:
    event_id: str
    task_id: str
    event_type: EventType
    agent_id: str
    timestamp: float
    attempt: int
    status_before: TaskStatus
    status_after: TaskStatus
    summary: str
    artifact_refs: List[str]
    lock_scope: Dict[str, List[str]]
    depends_on: List[str]
    metrics_delta: Dict[str, float]
    error_code: Optional[str]
```

- [ ] **Step 4: 导出模块入口**

```python
# .hermes/team/control_plane/__init__.py
from .models import (
    EventType,
    LockScope,
    RetryPolicy,
    RollbackPolicy,
    TaskCard,
    TaskEvent,
    TaskPriority,
    TaskStatus,
)

__all__ = [
    "EventType",
    "LockScope",
    "RetryPolicy",
    "RollbackPolicy",
    "TaskCard",
    "TaskEvent",
    "TaskPriority",
    "TaskStatus",
]
```

- [ ] **Step 5: 定义第一批任务注册表**

```python
# .hermes/team/control_plane/tasks.py
from .models import LockScope, RetryPolicy, RollbackPolicy, TaskCard, TaskPriority


TASKS = [
    TaskCard(
        task_id="WS-A-P0-001",
        title="修复监控死锁",
        goal="让 dashboard 查询在锁竞争下仍可返回",
        scope=[".hermes/team/调度框架/core/monitor.py"],
        lock_scope=LockScope(
            files=[".hermes/team/调度框架/core/monitor.py"],
            modules=["monitor"],
            contracts=[],
        ),
        inputs=["assessment_report_2026-05-12.md"],
        outputs=["monitor deadlock fix", "unit test output"],
        dependencies=[],
        owner_agent="backend-1",
        review_agent="architect",
        priority=TaskPriority.P0,
        timeout_seconds=1800,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=[0, 60]),
        rollback_policy=RollbackPolicy(mode="code"),
        acceptance_criteria=["dashboard 调用 100 次均返回"],
    ),
]
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_models -v`  
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add .hermes/team/control_plane/__init__.py .hermes/team/control_plane/models.py .hermes/team/control_plane/tasks.py tests/control_plane/__init__.py tests/control_plane/test_support.py tests/control_plane/test_models.py
git commit -m "feat(control-plane): add task models and registry"
```

### Task 2: 状态仓与事件日志

**Files:**
- Create: `.hermes/team/control_plane/store.py`
- Create: `.hermes/team/control_plane/state/.gitkeep`
- Create: `.hermes/team/control_plane/events/.gitkeep`
- Create: `tests/control_plane/test_store.py`

- [ ] **Step 1: 写状态仓失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from .test_support import load_control_plane_module

models = load_control_plane_module("models")
store_module = load_control_plane_module("store")


class TaskStoreTests(unittest.TestCase):
    def test_append_event_updates_snapshot_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            card = models.TaskCard(
                task_id="WS-B-P1-001",
                title="定义协议",
                goal="建立事件协议",
                scope=[".hermes/team/control_plane/models.py"],
                lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
                inputs=["spec"],
                outputs=["models diff"],
                dependencies=[],
                owner_agent="backend-2",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1200,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="state"),
                acceptance_criteria=["状态仓可落盘"],
            )
            store.register_task(card)
            event = models.TaskEvent(
                event_id="evt-001",
                task_id=card.task_id,
                event_type=models.EventType.TASK_STARTED,
                agent_id="backend-2",
                timestamp=1.0,
                attempt=1,
                status_before=models.TaskStatus.READY,
                status_after=models.TaskStatus.RUNNING,
                summary="start",
                artifact_refs=[],
                lock_scope={"files": [], "modules": ["control_plane"], "contracts": []},
                depends_on=[],
                metrics_delta={},
                error_code=None,
            )
            store.append_event(event)
            snapshot = store.read_snapshot(card.task_id)

            self.assertEqual(snapshot["status"], "running")
            self.assertEqual(snapshot["version"], 2)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_store -v`  
Expected: FAIL with import failure for `TaskStore`

- [ ] **Step 3: 写最小状态仓实现**

```python
# .hermes/team/control_plane/store.py
import json
from dataclasses import asdict
from pathlib import Path


class TaskStore:
    def __init__(self, state_dir: Path, events_dir: Path):
        self.state_dir = Path(state_dir)
        self.events_dir = Path(events_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def register_task(self, card):
        snapshot = asdict(card)
        snapshot["priority"] = card.priority.value
        snapshot["status"] = card.status.value
        snapshot["version"] = 1
        snapshot["last_event_id"] = None
        snapshot["updated_at"] = None
        snapshot["updated_by"] = None
        self._write_json(self.state_dir / f"{card.task_id}.json", snapshot)

    def append_event(self, event):
        event_path = self.events_dir / f"{event.task_id}.jsonl"
        with event_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event), ensure_ascii=False, default=str) + "\n")
        snapshot = self.read_snapshot(event.task_id)
        snapshot["status"] = event.status_after.value
        snapshot["version"] += 1
        snapshot["last_event_id"] = event.event_id
        snapshot["updated_at"] = event.timestamp
        snapshot["updated_by"] = event.agent_id
        self._write_json(self.state_dir / f"{event.task_id}.json", snapshot)

    def read_snapshot(self, task_id: str):
        return json.loads((self.state_dir / f"{task_id}.json").read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: 创建目录占位文件**

```text
# .hermes/team/control_plane/state/.gitkeep

# .hermes/team/control_plane/events/.gitkeep
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_store -v`  
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add .hermes/team/control_plane/store.py .hermes/team/control_plane/state/.gitkeep .hermes/team/control_plane/events/.gitkeep tests/control_plane/test_store.py
git commit -m "feat(control-plane): add state store and event log"
```

### Task 3: 冲突检测与锁域规则

**Files:**
- Create: `.hermes/team/control_plane/conflicts.py`
- Create: `tests/control_plane/test_conflicts.py`

- [ ] **Step 1: 写冲突检测失败测试**

```python
import unittest

from .test_support import load_control_plane_module

models = load_control_plane_module("models")
conflicts = load_control_plane_module("conflicts")


class ConflictDetectorTests(unittest.TestCase):
    def test_file_scope_conflict_is_hard_block(self):
        left = models.LockScope(files=["a.py"], modules=["m1"], contracts=[])
        right = models.LockScope(files=["a.py"], modules=["m2"], contracts=[])
        verdict = conflicts.detect_conflict(left, right)

        self.assertEqual(verdict["level"], "hard")
        self.assertIn("files", verdict["conflicts"])

    def test_module_scope_conflict_is_soft_block(self):
        left = models.LockScope(files=["a.py"], modules=["monitor"], contracts=[])
        right = models.LockScope(files=["b.py"], modules=["monitor"], contracts=[])
        verdict = conflicts.detect_conflict(left, right)

        self.assertEqual(verdict["level"], "soft")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_conflicts -v`  
Expected: FAIL with missing `detect_conflict`

- [ ] **Step 3: 写最小冲突检测实现**

```python
# .hermes/team/control_plane/conflicts.py
def detect_conflict(left, right):
    file_conflicts = sorted(set(left.files) & set(right.files))
    module_conflicts = sorted(set(left.modules) & set(right.modules))
    contract_conflicts = sorted(set(left.contracts) & set(right.contracts))

    if file_conflicts:
        return {"level": "hard", "conflicts": {"files": file_conflicts}}
    if contract_conflicts:
        return {"level": "review", "conflicts": {"contracts": contract_conflicts}}
    if module_conflicts:
        return {"level": "soft", "conflicts": {"modules": module_conflicts}}
    return {"level": "none", "conflicts": {}}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_conflicts -v`  
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/conflicts.py tests/control_plane/test_conflicts.py
git commit -m "feat(control-plane): add conflict detector"
```

### Task 4: 执行器、超时、重试与回滚编排

**Files:**
- Create: `.hermes/team/control_plane/executor.py`
- Create: `tests/control_plane/test_executor.py`

- [ ] **Step 1: 写执行器失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from .test_support import load_control_plane_module

models = load_control_plane_module("models")
store_module = load_control_plane_module("store")
executor_module = load_control_plane_module("executor")


class ExecutorTests(unittest.TestCase):
    def test_failed_task_blocks_dependents_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            runner = executor_module.ControlPlaneExecutor(store)
            graph = {
                "WS-A-P0-001": [],
                "WS-A-P0-002": ["WS-A-P0-001"],
                "WS-D-P1-001": [],
            }

            blocked = runner.compute_blocked_tasks("WS-A-P0-001", graph)

            self.assertEqual(blocked, ["WS-A-P0-002"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_executor -v`  
Expected: FAIL with missing `ControlPlaneExecutor`

- [ ] **Step 3: 写最小执行器实现**

```python
# .hermes/team/control_plane/executor.py
class ControlPlaneExecutor:
    def __init__(self, store):
        self.store = store

    def compute_blocked_tasks(self, failed_task_id, graph):
        return sorted([task_id for task_id, deps in graph.items() if failed_task_id in deps])

    def classify_failure(self, error_code: str):
        if error_code.startswith("TRANSIENT_"):
            return "transient"
        if error_code.startswith("DEPENDENCY_"):
            return "dependency"
        return "deterministic"

    def should_retry(self, attempt: int, max_attempts: int, failure_kind: str):
        return failure_kind == "transient" and attempt < max_attempts
```

- [ ] **Step 4: 添加重试测试**

```python
    def test_transient_failure_retries_within_limit(self):
        runner = executor_module.ControlPlaneExecutor(store=None)
        self.assertTrue(runner.should_retry(1, 2, "transient"))
        self.assertFalse(runner.should_retry(2, 2, "transient"))
        self.assertFalse(runner.should_retry(1, 2, "deterministic"))
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_executor -v`  
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add .hermes/team/control_plane/executor.py tests/control_plane/test_executor.py
git commit -m "feat(control-plane): add executor failure policies"
```

### Task 4A: 执行器适配层（Hermes 直连，OpenClaw 预留）

**Files:**
- Create: `.hermes/team/control_plane/adapters.py`
- Create: `tests/control_plane/test_adapters.py`

- [ ] **Step 1: 写适配器失败测试**

```python
import unittest

from .test_support import load_control_plane_module

adapters_module = load_control_plane_module("adapters")


class AdapterTests(unittest.TestCase):
    def test_hermes_adapter_builds_dispatch_command(self):
        adapter = adapters_module.HermesExecutorAdapter(
            hermes_command="hermes",
            dispatch_script=".hermes/team/调度框架/scripts/team-dispatch.sh",
        )

        command = adapter.build_dispatch_command("architect", "分析任务")

        self.assertEqual(
            command,
            [
                "hermes",
                "team",
                "dispatch",
                "-a",
                "architect",
                "-t",
                "分析任务",
            ],
        )

    def test_openclaw_adapter_exposes_placeholder_contract(self):
        adapter = adapters_module.OpenClawExecutorAdapter()
        with self.assertRaises(NotImplementedError):
            adapter.build_dispatch_command("architect", "分析任务")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_adapters -v`  
Expected: FAIL with missing adapter classes

- [ ] **Step 3: 写最小适配器实现**

```python
# .hermes/team/control_plane/adapters.py
class HermesExecutorAdapter:
    def __init__(self, hermes_command="hermes", dispatch_script=None):
        self.hermes_command = hermes_command
        self.dispatch_script = dispatch_script

    def build_dispatch_command(self, agent_id: str, task: str):
        return [
            self.hermes_command,
            "team",
            "dispatch",
            "-a",
            agent_id,
            "-t",
            task,
        ]


class OpenClawExecutorAdapter:
    def build_dispatch_command(self, agent_id: str, task: str):
        raise NotImplementedError("OpenClaw adapter is reserved for a future phase")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_adapters -v`  
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/adapters.py tests/control_plane/test_adapters.py
git commit -m "feat(control-plane): add hermes adapter and openclaw placeholder"
```

### Task 5: 修复监控死锁并补回归测试

**Files:**
- Modify: `.hermes/team/调度框架/core/monitor.py`
- Create: `tests/control_plane/test_framework_monitor.py`

- [ ] **Step 1: 写死锁回归失败测试**

```python
import threading
import unittest

from .test_support import load_framework_module

monitor_module = load_framework_module("monitor")


class MonitorRegressionTests(unittest.TestCase):
    def test_dashboard_returns_without_deadlock(self):
        monitor = monitor_module.Monitor()
        result = {"done": False}

        def run():
            monitor.get_dashboard_data()
            result["done"] = True

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(1.0)

        self.assertTrue(result["done"], "dashboard 调用应在 1 秒内返回")
```

- [ ] **Step 2: 扩展测试辅助并运行失败**

```python
# tests/control_plane/test_support.py
FRAMEWORK_DIR = ROOT / ".hermes" / "team" / "调度框架" / "core"


def load_framework_module(name: str):
    file_path = FRAMEWORK_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"framework_{name}", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
```

Run: `python -m unittest tests.control_plane.test_framework_monitor -v`  
Expected: FAIL because thread stays alive or assertion fails

- [ ] **Step 3: 最小修复 monitor 锁重入问题**

```python
# .hermes/team/调度框架/core/monitor.py
import threading

...
        self._lock = threading.RLock()
...
    def _build_alert_payloads(self, alerts):
        return [
            {
                "id": a.id,
                "level": a.level,
                "message": a.message,
                "agent_id": a.agent_id,
                "timestamp": a.timestamp,
                "resolved": a.resolved,
                "resolved_at": a.resolved_at,
            }
            for a in alerts
        ]

    def _build_log_payloads(self, logs):
        return list(logs)

    def get_dashboard_data(self) -> Dict:
        with self._lock:
            total_alerts = len(self.alerts)
            unresolved_alerts = len([a for a in self.alerts if not a.resolved])
            critical_alerts = len([a for a in self.alerts if a.level == "critical" and not a.resolved])
            agent_loads = {}
            for name, values in self.metrics.items():
                if name.startswith("agent_load_") and values:
                    agent_id = name.replace("agent_load_", "")
                    agent_loads[agent_id] = values[-1].value

            recent_alerts = self._build_alert_payloads([a for a in self.alerts if not a.resolved][:5])
            recent_logs = self._build_log_payloads(list(self.logs)[-10:])
            return {
                "summary": {
                    "total_alerts": total_alerts,
                    "unresolved_alerts": unresolved_alerts,
                    "critical_alerts": critical_alerts,
                    "total_logs": len(self.logs),
                },
                "agent_loads": agent_loads,
                "recent_alerts": recent_alerts,
                "recent_logs": recent_logs,
            }
```

- [ ] **Step 4: 运行监控测试**

Run: `python -m unittest tests.control_plane.test_framework_monitor -v`  
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/调度框架/core/monitor.py tests/control_plane/test_framework_monitor.py tests/control_plane/test_support.py
git commit -m "fix(monitor): remove dashboard deadlock"
```

### Task 6: 修复工作流强制指定 agent 语义

**Files:**
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Create: `tests/control_plane/test_framework_workflow.py`

- [ ] **Step 1: 写工作流 agent 语义失败测试**

```python
import unittest

from .test_support import load_framework_module

workflow_module = load_framework_module("workflow_engine")
router_module = load_framework_module("task_router")


class WorkflowRegressionTests(unittest.TestCase):
    def test_step_agent_overrides_auto_routing(self):
        router = router_module.TaskRouter()
        engine = workflow_module.WorkflowEngine(task_router=router, message_bus=None)
        step = workflow_module.WorkflowStep(
            id="database",
            name="数据库设计",
            type=workflow_module.StepType.SEQUENTIAL,
            agent="dba",
            task_template="设计数据库表结构",
        )

        result = engine._execute_agent_task(step, "设计数据库表结构")

        self.assertEqual(result["agent"], "dba")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_framework_workflow -v`  
Expected: FAIL because result agent follows auto-routing

- [ ] **Step 3: 最小修复 `_execute_agent_task()`**

```python
# .hermes/team/调度框架/core/workflow_engine.py
    def _execute_agent_task(self, step: WorkflowStep, task_content: str) -> Dict:
        if self.task_router:
            if step.agent:
                agent_id, task = self.task_router.route_task(task_content)
                if agent_id != step.agent:
                    self.task_router.agents[agent_id].current_tasks = max(
                        0, self.task_router.agents[agent_id].current_tasks - 1
                    )
                    self.task_router.agents[step.agent].current_tasks += 1
                    task.assigned_agent = step.agent
                    agent_id = step.agent
                return {
                    "success": True,
                    "output": f"任务已分配给 {agent_id}: {task_content}",
                    "agent": agent_id,
                }
            agent_id, task = self.task_router.route_task(task_content)
            return {
                "success": True,
                "output": f"任务已分配给 {agent_id}: {task_content}",
                "agent": agent_id,
            }
        return {
            "success": True,
            "output": f"模拟执行: {task_content}",
            "agent": step.agent or "auto",
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_framework_workflow -v`  
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/调度框架/core/workflow_engine.py tests/control_plane/test_framework_workflow.py
git commit -m "fix(workflow): honor explicit step agent"
```

### Task 7: 补齐 CLI 监控生命周期

**Files:**
- Modify: `.hermes/team/调度框架/cli/team-cli.py`
- Create: `tests/control_plane/test_framework_cli.py`

- [ ] **Step 1: 写 CLI 生命周期失败测试**

```python
import unittest

from .test_support import load_cli_module

cli_module = load_cli_module("team-cli.py", "team_cli")


class CLILifecycleTests(unittest.TestCase):
    def test_team_cli_starts_monitor_on_init(self):
        cli = cli_module.TeamCLI()
        self.assertTrue(cli.monitor._running)
        cli.monitor.stop()
```

- [ ] **Step 2: 扩展测试辅助并运行失败**

```python
# tests/control_plane/test_support.py
CLI_DIR = ROOT / ".hermes" / "team" / "调度框架" / "cli"


def load_cli_module(file_name: str, alias: str):
    file_path = CLI_DIR / file_name
    spec = importlib.util.spec_from_file_location(alias, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
```

Run: `python -m unittest tests.control_plane.test_framework_cli -v`  
Expected: FAIL because `_running` is `False`

- [ ] **Step 3: 最小修复 TeamCLI 生命周期**

```python
# .hermes/team/调度框架/cli/team-cli.py
class TeamCLI:
    def __init__(self):
        self.router = get_router()
        self.bus = get_bus()
        self.monitor = get_monitor()
        self.recovery = get_recovery_manager(self.router)
        if not self.monitor._running:
            self.monitor.start()
        for agent_id in self.router.agents:
            self.bus.register_agent(agent_id)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_framework_cli -v`  
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/调度框架/cli/team-cli.py tests/control_plane/test_framework_cli.py tests/control_plane/test_support.py
git commit -m "fix(cli): start monitor lifecycle on initialization"
```

### Task 8: 性能基线采集与回归场景

**Files:**
- Create: `.hermes/team/control_plane/baseline.py`
- Create: `tests/control_plane/test_baseline.py`

- [ ] **Step 1: 写基线采集失败测试**

```python
import unittest

from .test_support import load_control_plane_module

baseline_module = load_control_plane_module("baseline")


class BaselineTests(unittest.TestCase):
    def test_summary_includes_avg_p95_and_max(self):
        summary = baseline_module.summarize_samples([10, 20, 30, 40, 50])
        self.assertEqual(summary["avg"], 30.0)
        self.assertEqual(summary["max"], 50)
        self.assertIn("p95", summary)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_baseline -v`  
Expected: FAIL with missing `summarize_samples`

- [ ] **Step 3: 写最小基线实现**

```python
# .hermes/team/control_plane/baseline.py
def summarize_samples(samples):
    ordered = sorted(samples)
    avg = sum(ordered) / len(ordered)
    p95_index = min(len(ordered) - 1, max(0, round(len(ordered) * 0.95) - 1))
    return {
        "avg": avg,
        "p95": ordered[p95_index],
        "max": ordered[-1],
    }
```

- [ ] **Step 4: 增加性能目标判定测试**

```python
    def test_performance_goal_requires_latency_and_cpu_reduction(self):
        verdict = baseline_module.compare_runs(
            before={"latency": 100.0, "cpu": 40.0},
            after={"latency": 75.0, "cpu": 32.0},
        )
        self.assertTrue(verdict["latency_ok"])
        self.assertTrue(verdict["cpu_ok"])
        self.assertTrue(verdict["overall_ok"])
```

- [ ] **Step 5: 扩展实现**

```python
def compare_runs(before, after):
    latency_drop = (before["latency"] - after["latency"]) / before["latency"]
    cpu_drop = (before["cpu"] - after["cpu"]) / before["cpu"]
    return {
        "latency_drop_ratio": latency_drop,
        "cpu_drop_ratio": cpu_drop,
        "latency_ok": latency_drop >= 0.20,
        "cpu_ok": cpu_drop >= 0.15,
        "overall_ok": latency_drop >= 0.20 and cpu_drop >= 0.15,
    }
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_baseline -v`  
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add .hermes/team/control_plane/baseline.py tests/control_plane/test_baseline.py
git commit -m "feat(control-plane): add baseline comparison helpers"
```

### Task 9: 聚合器、最终报告与 README 收口

**Files:**
- Create: `.hermes/team/control_plane/aggregator.py`
- Create: `.hermes/team/control_plane/reporting.py`
- Create: `.hermes/team/control_plane/README.md`
- Create: `.hermes/team/control_plane/run_benchmarks.py`
- Create: `.hermes/team/control_plane/artifacts/.gitkeep`
- Create: `tests/control_plane/test_aggregator.py`
- Create: `tests/control_plane/test_benchmark_runner.py`
- Modify: `.hermes/team/调度框架/README_v2.md`

- [ ] **Step 1: 写聚合器失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from .test_support import load_control_plane_module

aggregator_module = load_control_plane_module("aggregator")


class AggregatorTests(unittest.TestCase):
    def test_aggregator_builds_final_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = aggregator_module.build_report(
                output_dir=Path(tmp),
                task_summary={"done": 3, "failed": 0, "blocked": 1},
                performance_summary={"overall_ok": True},
            )
            self.assertIn("执行概览", report)
            self.assertIn("性能对比报告", report)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_aggregator -v`  
Expected: FAIL with missing `build_report`

- [ ] **Step 3: 写最小聚合器与 Markdown 报告生成**

```python
# .hermes/team/control_plane/aggregator.py
from pathlib import Path


def build_report(output_dir: Path, task_summary, performance_summary):
    output_dir.mkdir(parents=True, exist_ok=True)
    content = f"""# 控制平面执行报告

## 执行概览
- done: {task_summary['done']}
- failed: {task_summary['failed']}
- blocked: {task_summary['blocked']}

## 性能对比报告
- overall_ok: {performance_summary['overall_ok']}
"""
    report_path = output_dir / "final-report.md"
    report_path.write_text(content, encoding="utf-8")
    return content
```

- [ ] **Step 4: 写 README 使用说明**

```markdown
# 仓库级控制平面

## 目录
- `models.py`：任务卡与事件模型
- `store.py`：状态快照与事件日志
- `conflicts.py`：锁域冲突检测
- `executor.py`：失败隔离、重试与阻塞传播
- `baseline.py`：性能基线与目标判定
- `aggregator.py`：最终报告聚合

## 执行顺序
1. 注册任务
2. 写入状态仓
3. 执行冲突检测
4. 运行专项修复
5. 运行回归与性能验证
6. 生成最终报告
```

- [ ] **Step 5: 更新调度框架说明文档**

```markdown
## 与仓库级控制平面的关系

调度框架现在作为仓库级控制平面下的一个被治理 workstream。
P0 正确性修复、回归验证与性能指标由控制平面统一登记与聚合，不再仅依赖手工操作日志。
```

- [ ] **Step 6: 运行聚合器测试确认通过**

Run: `python -m unittest tests.control_plane.test_aggregator -v`  
Expected: `OK`

- [ ] **Step 7: 执行全量测试**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`  
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add .hermes/team/control_plane/aggregator.py .hermes/team/control_plane/reporting.py .hermes/team/control_plane/README.md .hermes/team/control_plane/artifacts/.gitkeep tests/control_plane/test_aggregator.py .hermes/team/调度框架/README_v2.md
git commit -m "feat(control-plane): add reporting and integration docs"
```

### Task 10: 独立 Benchmark Runner 与基线产物重建

**Files:**
- Create: `.hermes/team/control_plane/run_benchmarks.py`
- Create: `tests/control_plane/test_benchmark_runner.py`
- Modify: `.hermes/team/control_plane/README.md`

- [ ] **Step 1: 写 benchmark runner 失败测试**

```python
import json
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import load_control_plane_module

runner_module = load_control_plane_module("run_benchmarks")


class BenchmarkRunnerTests(unittest.TestCase):
    def test_runner_writes_before_and_current_baselines(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            def fake_capture_current(**kwargs):
                return {
                    "label": "current",
                    "load_profile": {"cpu_burn_iterations": 2000000},
                    "scenarios": {"dispatch": {"cpu_ms": {"avg": 10.0}, "latency_ms": {"avg": 10.0}}},
                }

            def fake_capture_before(**kwargs):
                return {
                    "label": "reconstructed-before",
                    "load_profile": {"cpu_burn_iterations": 2000000},
                    "scenarios": {"dispatch": {"cpu_ms": {"avg": 20.0}, "latency_ms": {"avg": 20.0}}},
                }

            report_path = runner_module.run_benchmarks(
                repo_root=base,
                artifacts_dir=base / "artifacts",
                capture_current=fake_capture_current,
                capture_before=fake_capture_before,
            )

            self.assertTrue((base / "artifacts" / "current-baseline.json").exists())
            self.assertTrue((base / "artifacts" / "before-baseline.json").exists())
            self.assertTrue(report_path.exists())

            report = (base / "artifacts" / "performance-report.md").read_text(encoding="utf-8")
            self.assertIn("dispatch", report)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_benchmark_runner -v`  
Expected: FAIL with missing `run_benchmarks.py` or `run_benchmarks()`

- [ ] **Step 3: 写最小 benchmark runner 实现**

```python
# .hermes/team/control_plane/run_benchmarks.py
import json
from pathlib import Path

import aggregator
import baseline


def run_benchmarks(
    repo_root: Path,
    artifacts_dir: Path,
    iterations: int = 5,
    load_profile=None,
    capture_current=None,
    capture_before=None,
):
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    load_profile = load_profile or {"cpu_burn_iterations": 2_000_000}
    capture_current = capture_current or (
        lambda **kwargs: baseline.capture_framework_baseline(
            iterations=iterations,
            label="current",
            load_profile=load_profile,
        )
    )
    capture_before = capture_before or (
        lambda **kwargs: baseline.capture_reconstructed_before_baseline(
            repo_root=repo_root,
            iterations=iterations,
        )
    )

    current_run = capture_current()
    before_run = capture_before()

    baseline.persist_benchmark_run(artifacts_dir / "current-baseline.json", current_run)
    baseline.persist_benchmark_run(artifacts_dir / "before-baseline.json", before_run)
    aggregator.build_performance_report(
        artifacts_dir,
        current_run=current_run,
        previous_run=before_run,
    )
    return artifacts_dir / "performance-report.md"


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[3]
    artifacts_dir = Path(__file__).resolve().parent / "artifacts"
    report_path = run_benchmarks(repo_root=repo_root, artifacts_dir=artifacts_dir)
    print(report_path)
```

- [ ] **Step 4: 更新 README 使用方式**

```markdown
## 基线与性能报告

运行以下命令重建当前基线、近似修复前基线与性能报告：

```bash
python .hermes/team/control_plane/run_benchmarks.py
```

输出产物：
- `.hermes/team/control_plane/artifacts/current-baseline.json`
- `.hermes/team/control_plane/artifacts/before-baseline.json`
- `.hermes/team/control_plane/artifacts/performance-report.md`
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_benchmark_runner -v`  
Expected: `OK`

- [ ] **Step 6: 重建基线产物**

Run: `python .hermes/team/control_plane/run_benchmarks.py`  
Expected: prints `...performance-report.md`

- [ ] **Step 7: 运行控制平面全量测试**

Run: `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`  
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add .hermes/team/control_plane/run_benchmarks.py .hermes/team/control_plane/README.md tests/control_plane/test_benchmark_runner.py .hermes/team/control_plane/artifacts/current-baseline.json .hermes/team/control_plane/artifacts/before-baseline.json .hermes/team/control_plane/artifacts/performance-report.md
git commit -m "feat(control-plane): add benchmark runner"
```

## 自检

- 规格覆盖检查：
  - 任务卡、状态仓、事件流、冲突检测、失败隔离、性能验证、最终报告均有对应任务。
  - 调度框架 P0 项包含死锁修复、`step.agent` 语义修复和 CLI 生命周期补齐。
- 占位符检查：
  - 计划中未使用 `TODO`、`TBD`、`implement later` 等占位语句。
- 类型一致性检查：
  - `TaskCard`、`TaskEvent`、`TaskStore`、`ControlPlaneExecutor`、`summarize_samples()`、`compare_runs()`、`build_report()` 在各任务间命名保持一致。
  - 新增 `run_benchmarks()` 作为独立入口，消费 `capture_framework_baseline()` 与 `capture_reconstructed_before_baseline()`，不改变既有函数命名。
