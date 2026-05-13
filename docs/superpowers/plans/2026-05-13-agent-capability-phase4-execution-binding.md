# Agent Capability Phase 4 Execution Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通 `workflow -> TaskCard -> ControlPlaneExecutor` 的真实执行绑定，让 backend recommendation 真正驱动 provider 选择，同时保留未注入依赖时的模拟执行路径。

**Architecture:** 在 `WorkflowEngine` 内增加一条可选的真实执行路径：当注入 control plane store / executor / adapter / command_runner 时，把 workflow step 映射成临时 `TaskCard` 并交给 `ControlPlaneExecutor.execute_task()`；否则维持当前模拟执行。backend 绑定优先级固定为 `step 显式 backend > routing/backend recommendation > inherited backend > default executor`，并把真实执行结果继续沉淀为 `step_context`。

**Tech Stack:** Python 3.13, `unittest`, dataclasses, existing control_plane executor/adapters/store, 调度框架 `workflow_engine`

---

### Task 1: 锁定 Workflow 的真实执行入口

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workflow_uses_control_plane_executor_when_dependencies_are_provided(self):
    events = []

    class FakeExecutor:
        def execute_task(self, card, adapter, command_runner):
            events.append(
                {
                    "task_id": card.task_id,
                    "goal": card.goal,
                    "owner_agent": card.owner_agent,
                    "executor_backend": card.executor_backend,
                }
            )
            return {
                "success": True,
                "command": ["openclaw-live", "task", "run"],
                "stdout": "ok",
                "stderr": "",
            }

    engine = workflow_module.WorkflowEngine(
        task_router=None,
        message_bus=None,
        runtime_store=None,
        control_plane_store=object(),
        control_plane_executor=FakeExecutor(),
        control_plane_adapter=object(),
        command_runner=lambda command: None,
    )
    workflow = engine.create_workflow(
        "wf-exec-bind",
        "exec-bind",
        "demo",
        [
            {
                "id": "implement",
                "name": "实现",
                "type": "sequential",
                "agent": "backend-1",
                "task": "实现代码",
            }
        ],
    )
    workflow.variables["backend_recommendation"] = {"selected_backend": "openclaw"}

    result = engine.execute_workflow(workflow.id)

    self.assertEqual(events[0]["executor_backend"], "openclaw")
    self.assertEqual(result["step_contexts"]["implement"]["execution"]["command"], ["openclaw-live", "task", "run"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_uses_control_plane_executor_when_dependencies_are_provided`
Expected: FAIL because `WorkflowEngine.__init__()` does not accept control plane execution dependencies yet.

- [ ] **Step 3: Write minimal implementation**

```python
def __init__(
    self,
    task_router=None,
    message_bus=None,
    runtime_store=None,
    provider_registry=None,
    control_plane_store=None,
    control_plane_executor=None,
    control_plane_adapter=None,
    command_runner=None,
):
    self.task_router = task_router
    self.message_bus = message_bus
    self.runtime_store = runtime_store
    self.provider_registry = provider_registry or build_default_provider_registry()
    self.control_plane_store = control_plane_store
    self.control_plane_executor = control_plane_executor
    self.control_plane_adapter = control_plane_adapter
    self.command_runner = command_runner
```

```python
def _can_use_control_plane_execution(self) -> bool:
    return all(
        dependency is not None
        for dependency in (
            self.control_plane_store,
            self.control_plane_executor,
            self.control_plane_adapter,
            self.command_runner,
        )
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_uses_control_plane_executor_when_dependencies_are_provided`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py
git commit -m "feat: add control plane execution entry to workflow engine"
```

### Task 2: 把 Workflow Step 映射为临时 TaskCard

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workflow_builds_task_card_with_inherited_backend(self):
    engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
    workflow = engine.create_workflow(
        "wf-card-map",
        "card-map",
        "demo",
        [
            {
                "id": "implement",
                "name": "实现",
                "type": "sequential",
                "agent": "backend-1",
                "task": "实现代码",
            }
        ],
    )
    workflow.variables["backend_recommendation"] = {"selected_backend": "openclaw"}
    step = workflow.steps[0]

    card = engine._build_task_card_for_step(workflow, step, "实现代码", "backend-1", "openclaw")

    self.assertEqual(card.task_id, "wf-wf-card-map-implement")
    self.assertEqual(card.owner_agent, "backend-1")
    self.assertEqual(card.executor_backend, "openclaw")
    self.assertEqual(card.goal, "实现代码")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_builds_task_card_with_inherited_backend`
Expected: FAIL because `_build_task_card_for_step()` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def _build_task_card_for_step(self, workflow, step, task_content, agent_id, executor_backend):
    return TaskCard(
        task_id=f"wf-{workflow.id}-{step.id}",
        title=f"Workflow step {step.id}",
        goal=task_content,
        scope=[workflow.id, step.id],
        lock_scope=LockScope(files=[], modules=["workflow"], contracts=[]),
        inputs=["workflow-step"],
        outputs=["stdout", "stderr"],
        dependencies=[],
        owner_agent=agent_id,
        review_agent=agent_id,
        priority=TaskPriority.P1,
        timeout_seconds=max(1, int(step.timeout)),
        retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=[0]),
        rollback_policy=RollbackPolicy(mode="manual"),
        acceptance_criteria=[f"step {step.id} executed"],
        executor_backend=executor_backend,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_builds_task_card_with_inherited_backend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py
git commit -m "feat: map workflow steps to temporary task cards"
```

### Task 3: 锁定 Backend 绑定优先级

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_step_backend_override_beats_inherited_backend(self):
    engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
    workflow = engine.create_workflow(
        "wf-backend-priority",
        "backend-priority",
        "demo",
        [
            {
                "id": "implement",
                "name": "实现",
                "type": "sequential",
                "agent": "backend-1",
                "task": "实现代码",
            }
        ],
    )
    workflow.variables["backend_recommendation"] = {"selected_backend": "openclaw"}
    step = workflow.steps[0]
    step.backend = "hermes"

    selected = engine._resolve_step_backend(workflow, step, {"backend_recommendation": {"selected_backend": "openclaw"}})

    self.assertEqual(selected, "hermes")
```

```python
def test_routing_backend_recommendation_beats_inherited_backend(self):
    engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
    workflow = engine.create_workflow(
        "wf-routing-priority",
        "routing-priority",
        "demo",
        [
            {
                "id": "implement",
                "name": "实现",
                "type": "sequential",
                "agent": "backend-1",
                "task": "实现代码",
            }
        ],
    )
    workflow.variables["backend_recommendation"] = {"selected_backend": "hermes"}

    selected = engine._resolve_step_backend(
        workflow,
        workflow.steps[0],
        {"backend_recommendation": {"selected_backend": "openclaw"}},
    )

    self.assertEqual(selected, "openclaw")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_step_backend_override_beats_inherited_backend tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_routing_backend_recommendation_beats_inherited_backend`
Expected: FAIL because `_resolve_step_backend()` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def _resolve_step_backend(self, workflow, step, task_result=None):
    explicit_backend = getattr(step, "backend", None)
    if explicit_backend:
        return explicit_backend
    task_result = task_result or {}
    recommendation = task_result.get("backend_recommendation") or {}
    if recommendation.get("selected_backend"):
        return recommendation["selected_backend"]
    inherited = workflow.variables.get("backend_recommendation", {})
    if isinstance(inherited, dict) and inherited.get("selected_backend"):
        return inherited["selected_backend"]
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_step_backend_override_beats_inherited_backend tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_routing_backend_recommendation_beats_inherited_backend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py
git commit -m "feat: resolve workflow step backend priority"
```

### Task 4: 打通真实执行路径并返回执行结果

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workflow_real_execution_records_execution_payload(self):
    class FakeStore:
        def __init__(self):
            self.state_dir = None

    class FakeExecutor:
        def execute_task(self, card, adapter, command_runner):
            return {
                "success": True,
                "command": ["hermes", "team", "dispatch", "-a", card.owner_agent, "-t", card.goal],
                "stdout": "done",
                "stderr": "",
            }

    engine = workflow_module.WorkflowEngine(
        task_router=None,
        message_bus=None,
        runtime_store=None,
        control_plane_store=FakeStore(),
        control_plane_executor=FakeExecutor(),
        control_plane_adapter=object(),
        command_runner=lambda command: None,
    )
    workflow = engine.create_workflow(
        "wf-real-exec",
        "real-exec",
        "demo",
        [
            {"id": "implement", "name": "实现", "type": "sequential", "agent": "backend-1", "task": "实现代码"}
        ],
    )

    result = engine.execute_workflow(workflow.id)

    self.assertEqual(result["step_contexts"]["implement"]["execution"]["stdout"], "done")
    self.assertEqual(result["step_contexts"]["implement"]["execution"]["executor_backend"], "hermes")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_real_execution_records_execution_payload`
Expected: FAIL because real execution payload is not returned in `step_contexts`.

- [ ] **Step 3: Write minimal implementation**

```python
def _execute_via_control_plane(self, workflow, step, task_content, agent_id, task_result):
    executor_backend = self._resolve_step_backend(workflow, step, task_result) or self.config.default_executor
    card = self._build_task_card_for_step(workflow, step, task_content, agent_id, executor_backend)
    outcome = self.control_plane_executor.execute_task(
        card,
        self.control_plane_adapter,
        self.command_runner,
    )
    return {
        "success": outcome["success"],
        "output": outcome.get("stdout") or task_content,
        "agent": agent_id,
        "backend_recommendation": {"selected_backend": executor_backend},
        "inherited_backend": executor_backend,
        "execution": {
            "command": outcome.get("command", []),
            "stdout": outcome.get("stdout", ""),
            "stderr": outcome.get("stderr", ""),
            "executor_backend": executor_backend,
        },
    }
```

```python
if self._can_use_control_plane_execution():
    return self._execute_via_control_plane(workflow, step, task_content, agent_id, task.routing_reason)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_real_execution_records_execution_payload`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py
git commit -m "feat: bind workflow execution to control plane executor"
```

### Task 5: 保持模拟路径不回退

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workflow_keeps_simulated_execution_without_control_plane_dependencies(self):
    engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
    workflow = engine.create_workflow(
        "wf-simulated",
        "simulated",
        "demo",
        [
            {"id": "implement", "name": "实现", "type": "sequential", "agent": "backend-1", "task": "实现代码"}
        ],
    )

    result = engine.execute_workflow(workflow.id)

    self.assertEqual(result["step_contexts"]["implement"]["summary"], "模拟执行: 实现代码")
    self.assertNotIn("execution", result["step_contexts"]["implement"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_keeps_simulated_execution_without_control_plane_dependencies`
Expected: FAIL if the real execution binding accidentally changes the existing simulated path shape.

- [ ] **Step 3: Write minimal implementation**

```python
def _build_step_context(self, step, result, task_content):
    context = {
        ...
    }
    if isinstance(result, dict) and result.get("execution"):
        context["execution"] = dict(result["execution"])
    return context
```

```python
if not self._can_use_control_plane_execution():
    return {
        "success": True,
        "output": f"模拟执行: {task_content}",
        "agent": step.agent or "auto",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_keeps_simulated_execution_without_control_plane_dependencies`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py
git commit -m "test: preserve simulated workflow execution path"
```

### Task 6: 回归执行链路与诊断

**Files:**
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_executor.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_adapters.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_task_router.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_provider_registry.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`

- [ ] **Step 1: Run focused regression**

Run: `python -m unittest tests.control_plane.test_task_router tests.control_plane.test_workflow_runtime tests.control_plane.test_executor tests.control_plane.test_adapters tests.control_plane.test_handoff tests.control_plane.test_provider_registry tests.control_plane.test_unified_cli`
Expected: PASS

- [ ] **Step 2: Run broader framework regression**

Run: `python -m unittest tests.control_plane.test_framework_workflow tests.control_plane.test_persistent_bus`
Expected: PASS

- [ ] **Step 3: Run diagnostics checks**

Run diagnostics for:
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_executor.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_adapters.py`

Expected: no new diagnostics

- [ ] **Step 4: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\tests\control_plane
git commit -m "test: cover workflow execution binding"
```

---

## Self-Review Checklist

- **Spec coverage:** Task 1 覆盖真实执行入口；Task 2 覆盖 TaskCard 映射；Task 3 覆盖 backend 优先级；Task 4 覆盖真实执行 payload；Task 5 覆盖模拟路径兼容；Task 6 覆盖回归与诊断。
- **Placeholder scan:** 无 `TODO/TBD`；每一步都有具体测试、命令或代码片段。
- **Type consistency:** `executor_backend` 始终落在 `TaskCard`；`execution` 仅作为真实执行路径的 `step_context` 扩展字段；真实/模拟路径共享 `success/output/agent` 基础结构。

---

Plan complete and saved to `docs/superpowers/plans/2026-05-13-agent-capability-phase4-execution-binding.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration  
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
