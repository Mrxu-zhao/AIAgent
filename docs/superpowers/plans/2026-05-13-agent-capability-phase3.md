# Agent Capability Phase 3 Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 agent 能力提升收尾：路由输出 backend 建议、workflow 继承 backend 并映射到执行层、handoff 事件上总线形成闭环。

**Architecture:** 在现有 TaskRouter/WorkflowEngine/MessageBus 上小步扩展，不改变 CLI 外观。先让路由产出 backend recommendation，再让 workflow 继承并把 executor_backend 透传到 control plane 执行入口，最后把 handoff 事件发布到消息总线供外部订阅。

**Tech Stack:** Python 3.13, unittest, control_plane provider registry, 调度框架 workflow_engine/message_bus

---

### Task 1: 路由输出 Backend 建议

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\task_router.py`
- Test: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_task_router.py`

- [ ] **Step 1: Write the failing test**

```python
def test_route_task_emits_backend_recommendation(self):
    router = task_router_module.TaskRouter()

    agent_id, task = router.route_task("需要外部执行的 review 任务")

    self.assertIn("backend_recommendation", task.routing_reason)
    self.assertIn(task.routing_reason["backend_recommendation"]["selected_backend"], {"hermes", "openclaw"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_task_router.TaskRouterIntentTests.test_route_task_emits_backend_recommendation`
Expected: FAIL with `"backend_recommendation" not found`

- [ ] **Step 3: Write minimal implementation**

```python
# in TaskRouter.select_best_agent() routing_reason payload
backend_recommendation = {
    "selected_backend": "openclaw" if intent.collaboration_mode == "review" else "hermes",
    "backend_reason": "review tasks prefer openclaw when external execution is acceptable",
}

return best_agent, {
    ...,
    "backend_recommendation": backend_recommendation,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_task_router.TaskRouterIntentTests.test_route_task_emits_backend_recommendation`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\task_router.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_task_router.py
git commit -m "feat: emit backend recommendation in routing"
```

### Task 2: Workflow 继承 Backend 建议并透传到执行层

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\runner.py`
- Test: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Test: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_executor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workflow_step_inherits_backend_recommendation(self):
    engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
    workflow = engine.create_workflow(
        "wf-backend-inherit",
        "backend-inherit",
        "demo",
        [
            {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
            {"id": "implement", "name": "实现", "type": "sequential", "agent": "backend-1", "task": "实现代码", "dependencies": ["design"]},
        ],
    )

    def fake_execute(step, task_content):
        result = {"success": True, "output": f"{step.id}:{task_content}", "agent": step.agent}
        if step.id == "design":
            result["backend_recommendation"] = {"selected_backend": "openclaw"}
        return result

    engine._execute_agent_task = fake_execute
    result = engine.execute_workflow(workflow.id)

    self.assertEqual(result["step_contexts"]["design"]["backend_recommendation"]["selected_backend"], "openclaw")
    self.assertEqual(result["step_contexts"]["implement"]["inherited_backend"], "openclaw")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_step_inherits_backend_recommendation`
Expected: FAIL with `"inherited_backend" not found`

- [ ] **Step 3: Write minimal implementation**

```python
# in workflow_engine._build_step_context()
return {
    ...,
    "backend_recommendation": result.get("backend_recommendation") if isinstance(result, dict) else None,
    "inherited_backend": result.get("inherited_backend") if isinstance(result, dict) else None,
}

# in workflow_engine._merge_step_context_into_variables()
if step_context.get("backend_recommendation"):
    workflow.variables["backend_recommendation"] = step_context["backend_recommendation"]
if step_context.get("inherited_backend"):
    workflow.variables["backend_recommendation"] = {
        "selected_backend": step_context["inherited_backend"]
    }

# in workflow_engine._execute_agent_task()
if self._active_workflow is not None:
    inherited = self._active_workflow.variables.get("backend_recommendation", {}).get("selected_backend")
    if inherited:
        result["inherited_backend"] = inherited
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_step_inherits_backend_recommendation`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py
git commit -m "feat: inherit backend recommendation across workflow steps"
```

### Task 3: Handoff 事件发布到消息总线

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Test: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workflow_emits_handoff_to_message_bus(self):
    events = []

    class FakeBus:
        def send(self, payload):
            events.append(payload)

    engine = workflow_module.WorkflowEngine(task_router=None, message_bus=FakeBus(), runtime_store=None)
    workflow = engine.create_workflow(
        "wf-bus-handoff",
        "bus-handoff",
        "demo",
        [
            {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
            {"id": "implement", "name": "实现", "type": "sequential", "agent": "backend-1", "task": "实现代码", "dependencies": ["design"]},
        ],
    )

    engine._execute_agent_task = lambda step, task_content: {"success": True, "output": "ok", "agent": step.agent}
    engine.execute_workflow(workflow.id)

    self.assertTrue(any(event.get("type") == "handoff" for event in events))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_emits_handoff_to_message_bus`
Expected: FAIL with `no handoff event`

- [ ] **Step 3: Write minimal implementation**

```python
# in workflow_engine._record_followup_handoffs(), after payload.to_dict()
handoff_payload = payload.to_dict()
workflow.handoffs.append(handoff_payload)
if self.message_bus:
    self.message_bus.send({"type": "handoff", "payload": handoff_payload})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_emits_handoff_to_message_bus`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py
git commit -m "feat: publish handoff payloads to message bus"
```

### Task 4: 回归与清理

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\docs\superpowers\plans\2026-05-13-agent-capability-phase3.md`
- Test: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_task_router.py`
- Test: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Test: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_adapters.py`
- Test: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_executor.py`

- [ ] **Step 1: Run full focused test set**

Run:
`python -m unittest tests.control_plane.test_task_router tests.control_plane.test_workflow_runtime tests.control_plane.test_adapters tests.control_plane.test_executor tests.control_plane.test_handoff tests.control_plane.test_provider_registry`

Expected: PASS

- [ ] **Step 2: Fix any regression**

Apply minimal fixes, re-run the same command until green.

- [ ] **Step 3: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\tests\control_plane
git commit -m "test: cover agent capability phase3 behaviors"
```

---

## Self-Review Checklist

- **Spec coverage:** Task 1 覆盖路由输出 backend recommendation；Task 2 覆盖 workflow 继承 backend 并为后续执行透传；Task 3 覆盖 handoff bus 发布；Task 4 覆盖回归。
- **Placeholder scan:** 无 `TODO/TBD`；每一步包含实际代码或命令。
- **Type consistency:** `backend_recommendation` 结构保持 `{selected_backend, backend_reason?}`；`inherited_backend` 仅作为 step_context 字段；消息总线 payload 统一为 `{"type": "handoff", "payload": ...}`。

---

Plan complete and saved to `docs/superpowers/plans/2026-05-13-agent-capability-phase3.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration  
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
