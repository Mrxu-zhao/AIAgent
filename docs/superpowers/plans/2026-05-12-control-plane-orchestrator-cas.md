# Control Plane Orchestrator CAS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为仓库级控制平面新增并行调度器，将 CAS 语义从单任务执行路径上推到高层多任务并行调度。

**Architecture:** 新增 `.hermes/team/control_plane/orchestrator.py` 作为高层并发编排入口，由它负责就绪任务选择、并发执行、版本冲突解释和失败阻塞传播。单任务终态写入仍由 `ControlPlaneExecutor` 负责，调度器只写高层协调事件并消费 `expected_version`，避免双写终态。

**Tech Stack:** Python 3、dataclasses、json、pathlib、concurrent.futures、unittest、现有 `TaskStore` / `ControlPlaneExecutor`

---

## 文件结构

- Create: `.hermes/team/control_plane/orchestrator.py`
- Modify: `.hermes/team/control_plane/__init__.py`
- Modify: `.hermes/team/control_plane/README.md`
- Modify: `.hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md`
- Create: `tests/control_plane/test_orchestrator.py`

## 任务拆分原则

- 先写调度器失败测试，再实现最小调度能力。
- 先只实现“并行 ready 任务 + CAS 冲突解释 + 失败阻塞传播”，不扩展到旧调度框架内部。
- 调度器不直接写 `done` / `failed` 终态，终态继续由 `ControlPlaneExecutor` 负责。
- 每个任务完成后都要运行对应测试，并提交一次小粒度 commit。

### Task 1: 调度器依赖图与就绪任务选择

**Files:**
- Create: `tests/control_plane/test_orchestrator.py`
- Create: `.hermes/team/control_plane/orchestrator.py`

- [ ] **Step 1: 写依赖图和就绪任务失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from .test_support import load_control_plane_module

models = load_control_plane_module("models")
store_module = load_control_plane_module("store")
orchestrator_module = load_control_plane_module("orchestrator")


def make_card(task_id, dependencies=None, status=None):
    card = models.TaskCard(
        task_id=task_id,
        title=f"title-{task_id}",
        goal=f"goal-{task_id}",
        scope=[".hermes/team/control_plane/orchestrator.py"],
        lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
        inputs=["spec"],
        outputs=["summary"],
        dependencies=dependencies or [],
        owner_agent="backend-2",
        review_agent="architect",
        priority=models.TaskPriority.P1,
        timeout_seconds=1200,
        retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
        rollback_policy=models.RollbackPolicy(mode="state"),
        acceptance_criteria=["orchestrator can schedule task"],
        status=status or models.TaskStatus.PLANNED,
    )
    return card


class OrchestratorGraphTests(unittest.TestCase):
    def test_build_dependency_graph_returns_forward_and_reverse_edges(self):
        cards = [
            make_card("WS-B-P1-010"),
            make_card("WS-B-P1-011", dependencies=["WS-B-P1-010"]),
            make_card("WS-B-P1-012", dependencies=["WS-B-P1-010"]),
        ]

        graph = orchestrator_module.build_dependency_graph(cards)

        self.assertEqual(graph["forward"]["WS-B-P1-011"], ["WS-B-P1-010"])
        self.assertEqual(
            sorted(graph["reverse"]["WS-B-P1-010"]),
            ["WS-B-P1-011", "WS-B-P1-012"],
        )

    def test_get_ready_tasks_returns_only_tasks_with_satisfied_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            cards = [
                make_card("WS-B-P1-020"),
                make_card("WS-B-P1-021", dependencies=["WS-B-P1-020"]),
                make_card("WS-B-P1-022"),
            ]
            for card in cards:
                store.register_task(card)

            ready = orchestrator_module.get_ready_tasks(cards, store)

            self.assertEqual(
                [card.task_id for card in ready],
                ["WS-B-P1-020", "WS-B-P1-022"],
            )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorGraphTests -v`  
Expected: FAIL with `FileNotFoundError` or missing `build_dependency_graph`

- [ ] **Step 3: 写最小调度器依赖图与就绪任务实现**

```python
# .hermes/team/control_plane/orchestrator.py
from collections import defaultdict

from models import TaskStatus


def build_dependency_graph(cards):
    forward = {card.task_id: list(card.dependencies) for card in cards}
    reverse = defaultdict(list)
    for card in cards:
        for dependency in card.dependencies:
            reverse[dependency].append(card.task_id)
    for card in cards:
        reverse.setdefault(card.task_id, [])
    return {"forward": forward, "reverse": dict(reverse)}


def get_ready_tasks(cards, store):
    snapshots = {card.task_id: store.read_snapshot(card.task_id) for card in cards}
    ready = []
    terminal = {"done", "failed", "blocked", "cancelled"}
    for card in cards:
        snapshot = snapshots[card.task_id]
        if snapshot["status"] in terminal:
            continue
        if all(snapshots[dependency]["status"] == "done" for dependency in card.dependencies):
            ready.append(card)
    return ready
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorGraphTests -v`  
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/orchestrator.py tests/control_plane/test_orchestrator.py
git commit -m "feat(control-plane): add orchestrator graph helpers"
```

### Task 2: 多任务并行执行与调度摘要

**Files:**
- Modify: `tests/control_plane/test_orchestrator.py`
- Modify: `.hermes/team/control_plane/orchestrator.py`

- [ ] **Step 1: 写并行执行失败测试**

```python
class OrchestratorRunTests(unittest.TestCase):
    def test_run_executes_multiple_ready_tasks_and_collects_done_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            cards = [
                make_card("WS-B-P1-030"),
                make_card("WS-B-P1-031"),
            ]
            for card in cards:
                store.register_task(card)

            class Adapter:
                def build_dispatch_command(self, agent_id, task):
                    return ["dispatch", agent_id, task]

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            def command_runner(command):
                return Result()

            executor = orchestrator_module.ControlPlaneExecutor(store=store)
            orchestrator = orchestrator_module.ControlPlaneOrchestrator(store=store, executor=executor)

            summary = orchestrator.run(
                cards,
                adapter=Adapter(),
                command_runner=command_runner,
                max_workers=2,
            )

            self.assertEqual(sorted(summary["done_tasks"]), ["WS-B-P1-030", "WS-B-P1-031"])
            self.assertEqual(summary["failed_tasks"], [])
            self.assertEqual(summary["blocked_tasks"], [])
            self.assertEqual(summary["conflicted_tasks"], [])
            self.assertGreaterEqual(summary["rounds"], 1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorRunTests.test_run_executes_multiple_ready_tasks_and_collects_done_summary -v`  
Expected: FAIL with missing `ControlPlaneOrchestrator`

- [ ] **Step 3: 写最小并行运行实现**

```python
# .hermes/team/control_plane/orchestrator.py
from concurrent.futures import ThreadPoolExecutor, as_completed

from executor import ControlPlaneExecutor


class ControlPlaneOrchestrator:
    def __init__(self, store, executor=None):
        self.store = store
        self.executor = executor or ControlPlaneExecutor(store=store)

    def run(self, cards, adapter, command_runner, max_workers=2):
        done_tasks = []
        failed_tasks = []
        blocked_tasks = []
        conflicted_tasks = []
        rounds = 0

        while True:
            ready_cards = [
                card for card in get_ready_tasks(cards, self.store)
                if self.store.read_snapshot(card.task_id)["status"] in ("planned", "ready")
            ]
            if not ready_cards:
                break

            rounds += 1
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {
                    pool.submit(self.executor.execute_task, card, adapter, command_runner): card
                    for card in ready_cards
                }
                for future in as_completed(future_map):
                    card = future_map[future]
                    result = future.result()
                    if result["success"]:
                        done_tasks.append(card.task_id)
                    elif result.get("error_code") == "VERSION_CONFLICT":
                        conflicted_tasks.append(card.task_id)
                    else:
                        failed_tasks.append(card.task_id)

        return {
            "done_tasks": sorted(set(done_tasks)),
            "failed_tasks": sorted(set(failed_tasks)),
            "blocked_tasks": sorted(set(blocked_tasks)),
            "conflicted_tasks": sorted(set(conflicted_tasks)),
            "rounds": rounds,
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorRunTests.test_run_executes_multiple_ready_tasks_and_collects_done_summary -v`  
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/orchestrator.py tests/control_plane/test_orchestrator.py
git commit -m "feat(control-plane): add orchestrator parallel run loop"
```

### Task 3: 失败阻塞传播与协调事件

**Files:**
- Modify: `tests/control_plane/test_orchestrator.py`
- Modify: `.hermes/team/control_plane/orchestrator.py`

- [ ] **Step 1: 写失败阻塞传播失败测试**

```python
    def test_failed_task_blocks_only_direct_dependents(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            cards = [
                make_card("WS-B-P1-040"),
                make_card("WS-B-P1-041", dependencies=["WS-B-P1-040"]),
                make_card("WS-B-P1-042"),
            ]
            for card in cards:
                store.register_task(card)

            class Adapter:
                def build_dispatch_command(self, agent_id, task):
                    return ["dispatch", agent_id, task]

            class SuccessResult:
                returncode = 0
                stdout = "ok"
                stderr = ""

            class FailureResult:
                returncode = 1
                stdout = ""
                stderr = "boom"

            def command_runner(command):
                if "goal-WS-B-P1-040" in command[-1]:
                    return FailureResult()
                return SuccessResult()

            orchestrator = orchestrator_module.ControlPlaneOrchestrator(store=store)
            summary = orchestrator.run(cards, adapter=Adapter(), command_runner=command_runner, max_workers=2)

            blocked_snapshot = store.read_snapshot("WS-B-P1-041")
            independent_snapshot = store.read_snapshot("WS-B-P1-042")

            self.assertEqual(summary["failed_tasks"], ["WS-B-P1-040"])
            self.assertEqual(summary["blocked_tasks"], ["WS-B-P1-041"])
            self.assertEqual(blocked_snapshot["status"], "blocked")
            self.assertEqual(independent_snapshot["status"], "done")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorRunTests.test_failed_task_blocks_only_direct_dependents -v`  
Expected: FAIL because dependents are not blocked yet

- [ ] **Step 3: 写最小失败阻塞传播与协调事件实现**

```python
# .hermes/team/control_plane/orchestrator.py
import time
from uuid import uuid4

from models import EventType, TaskEvent, TaskStatus


class ControlPlaneOrchestrator:
    ...
    def block_dependents(self, task_id, cards):
        graph = build_dependency_graph(cards)
        blocked = []
        for dependent_id in graph["reverse"].get(task_id, []):
            snapshot = self.store.read_snapshot(dependent_id)
            if snapshot["status"] in ("done", "failed", "blocked", "cancelled"):
                continue
            event = TaskEvent(
                event_id=f"evt-{uuid4().hex}",
                task_id=dependent_id,
                event_type=EventType.TASK_BLOCKED,
                agent_id="control-plane-orchestrator",
                timestamp=time.time(),
                attempt=1,
                status_before=TaskStatus(snapshot["status"]),
                status_after=TaskStatus.BLOCKED,
                summary=f"blocked by failed dependency {task_id}",
                artifact_refs=[],
                lock_scope={"files": [], "modules": ["control_plane"], "contracts": []},
                depends_on=[task_id],
                metrics_delta={},
                error_code="DEPENDENCY_BLOCKED",
            )
            self.store.append_event(event, expected_version=snapshot["version"])
            blocked.append(dependent_id)
        return blocked

    def run(self, cards, adapter, command_runner, max_workers=2):
        ...
                    else:
                        failed_tasks.append(card.task_id)
                        blocked_tasks.extend(self.block_dependents(card.task_id, cards))
        ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorRunTests.test_failed_task_blocks_only_direct_dependents -v`  
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/orchestrator.py tests/control_plane/test_orchestrator.py
git commit -m "feat(control-plane): add dependent blocking in orchestrator"
```

### Task 4: 版本冲突解释与冲突事件

**Files:**
- Modify: `tests/control_plane/test_orchestrator.py`
- Modify: `.hermes/team/control_plane/orchestrator.py`

- [ ] **Step 1: 写版本冲突失败测试**

```python
    def test_version_conflict_is_recorded_without_marking_task_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            card = make_card("WS-B-P1-050")
            store.register_task(card)

            class Adapter:
                def build_dispatch_command(self, agent_id, task):
                    return ["dispatch", agent_id, task]

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            def command_runner(command):
                store.append_event(
                    models.TaskEvent(
                        event_id="evt-external-conflict",
                        task_id=card.task_id,
                        event_type=models.EventType.TASK_PROGRESS,
                        agent_id="reviewer",
                        timestamp=2.0,
                        attempt=1,
                        status_before=models.TaskStatus.RUNNING,
                        status_after=models.TaskStatus.RUNNING,
                        summary="external update",
                        artifact_refs=[],
                        lock_scope={"files": [], "modules": ["control_plane"], "contracts": []},
                        depends_on=[],
                        metrics_delta={},
                        error_code=None,
                    ),
                    expected_version=2,
                )
                return Result()

            orchestrator = orchestrator_module.ControlPlaneOrchestrator(store=store)
            summary = orchestrator.run([card], adapter=Adapter(), command_runner=command_runner, max_workers=1)

            snapshot = store.read_snapshot(card.task_id)
            events = store.list_events(card.task_id)

            self.assertEqual(summary["conflicted_tasks"], ["WS-B-P1-050"])
            self.assertEqual(summary["failed_tasks"], [])
            self.assertEqual(snapshot["status"], "running")
            self.assertIn("task_conflict_detected", [event["event_type"] for event in events])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorRunTests.test_version_conflict_is_recorded_without_marking_task_failed -v`  
Expected: FAIL because orchestrator does not write conflict event yet

- [ ] **Step 3: 写最小冲突解释与冲突事件实现**

```python
# .hermes/team/control_plane/orchestrator.py
    def record_conflict(self, card, summary):
        snapshot = self.store.read_snapshot(card.task_id)
        event = TaskEvent(
            event_id=f"evt-{uuid4().hex}",
            task_id=card.task_id,
            event_type=EventType.TASK_CONFLICT_DETECTED,
            agent_id="control-plane-orchestrator",
            timestamp=time.time(),
            attempt=1,
            status_before=TaskStatus(snapshot["status"]),
            status_after=TaskStatus(snapshot["status"]),
            summary=summary,
            artifact_refs=[],
            lock_scope={
                "files": card.lock_scope.files,
                "modules": card.lock_scope.modules,
                "contracts": card.lock_scope.contracts,
            },
            depends_on=card.dependencies,
            metrics_delta={},
            error_code="VERSION_CONFLICT",
        )
        self.store.append_event(event, expected_version=snapshot["version"])

    def run(self, cards, adapter, command_runner, max_workers=2):
        ...
                    elif result.get("error_code") == "VERSION_CONFLICT":
                        conflicted_tasks.append(card.task_id)
                        self.record_conflict(card, "orchestrator observed version conflict")
        ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorRunTests.test_version_conflict_is_recorded_without_marking_task_failed -v`  
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/orchestrator.py tests/control_plane/test_orchestrator.py
git commit -m "feat(control-plane): add orchestrator conflict handling"
```

### Task 5: 导出入口、文档与全量验证

**Files:**
- Modify: `.hermes/team/control_plane/__init__.py`
- Modify: `.hermes/team/control_plane/README.md`
- Modify: `.hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md`
- Modify: `tests/control_plane/test_orchestrator.py`

- [ ] **Step 1: 写导出入口失败测试**

```python
class OrchestratorExportTests(unittest.TestCase):
    def test_orchestrator_module_exports_control_plane_orchestrator(self):
        package = load_control_plane_module("__init__")
        self.assertTrue(hasattr(package, "ControlPlaneOrchestrator"))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorExportTests -v`  
Expected: FAIL because `__init__.py` does not export orchestrator yet

- [ ] **Step 3: 更新模块导出和文档**

```python
# .hermes/team/control_plane/__init__.py
from orchestrator import ControlPlaneOrchestrator, build_dependency_graph, get_ready_tasks

__all__ = [
    ...
    "ControlPlaneOrchestrator",
    "build_dependency_graph",
    "get_ready_tasks",
]
```

```markdown
# .hermes/team/control_plane/README.md
## 当前边界
- `ControlPlaneOrchestrator` 已负责高层多任务并行调度，并把 CAS 语义上推到 ready 任务选择、冲突解释和依赖阻塞传播。
- 调度器不直接写 `done` / `failed` 终态，终态仍由 `ControlPlaneExecutor` 负责。
```

```markdown
# .hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md
- 已新增 `ControlPlaneOrchestrator`，支持多任务并行调度、`VERSION_CONFLICT` 解释和直接依赖阻塞传播。
- 测试结果更新为最新总数，并将“下一步建议”收敛到更高层调度编排或真实负载验证。
```

- [ ] **Step 4: 运行导出测试确认通过**

Run: `python -m unittest tests.control_plane.test_orchestrator.OrchestratorExportTests -v`  
Expected: `OK`

- [ ] **Step 5: 运行控制平面全量测试**

Run: `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`  
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add .hermes/team/control_plane/__init__.py .hermes/team/control_plane/README.md .hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md .hermes/team/control_plane/orchestrator.py tests/control_plane/test_orchestrator.py
git commit -m "feat(control-plane): add orchestrator CAS scheduling"
```

## 自检

- 规格覆盖检查：
  - `ControlPlaneOrchestrator`、就绪任务选择、并行运行、`VERSION_CONFLICT` 解释和失败阻塞传播均有对应任务。
  - 文档与导出入口更新已覆盖到 README、执行摘要和包导出。
- 占位符检查：
  - 计划中未使用 `TODO`、`TBD`、`implement later` 等占位语句。
- 类型一致性检查：
  - 计划统一使用 `ControlPlaneOrchestrator`、`build_dependency_graph(cards)`、`get_ready_tasks(cards, store)`、`run(cards, adapter, command_runner, max_workers=2)`、`block_dependents(task_id, cards)`。
  - 冲突路径统一使用 `error_code = "VERSION_CONFLICT"` 与 `task_conflict_detected` 事件。
