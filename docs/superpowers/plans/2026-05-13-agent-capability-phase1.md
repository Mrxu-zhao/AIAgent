# Agent Capability Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal upper-layer agent capability loop that improves routing decisions, workflow context passing, and structured handoff generation.

**Architecture:** Extend the existing Python control-plane and framework modules in place. `TaskRouter` gains intent extraction and explainable routing, `WorkflowEngine` normalizes step outputs into reusable context and generates handoffs across agent boundaries, and `HandoffPayload` expands with backward-compatible metadata.

**Tech Stack:** Python, `unittest`, dataclasses, existing control-plane config/runtime modules

---

### Task 1: Lock Handoff Contract With Tests

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.py`

- [ ] **Step 1: Write the failing test**

```python
def test_handoff_payload_supports_extended_metadata(self):
    payload = handoff_module.HandoffPayload.create(
        source_backend="hermes",
        target_backend="openclaw",
        task_id="task-1",
        summary="handoff",
        context={"files": ["a.py"]},
        source_agent="architect",
        target_agent="backend-1",
        source_step="design",
        target_step="implement",
        reason="role transition",
        artifacts=["spec.md"],
        open_questions=["接口是否分页"],
        risks=["需求变更"],
    )

    data = payload.to_dict()

    self.assertEqual(data["source_agent"], "architect")
    self.assertEqual(data["artifacts"], ["spec.md"])
    self.assertTrue(handoff_module.validate_handoff_payload(data))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_handoff -v`
Expected: FAIL because `HandoffPayload.create()` and/or `to_dict()` do not support the new metadata fields.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class HandoffPayload:
    source_backend: str
    target_backend: str
    task_id: str
    summary: str
    context: Dict[str, Any]
    created_at: float
    source_agent: str | None = None
    target_agent: str | None = None
    source_step: str | None = None
    target_step: str | None = None
    reason: str | None = None
    artifacts: list[str] | None = None
    open_questions: list[str] | None = None
    risks: list[str] | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_handoff -v`
Expected: PASS

### Task 2: Add Intent-Aware Routing

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_task_router.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\task_router.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_route_task_prefers_explicit_alias_and_records_reason(self):
    router = task_router_module.TaskRouter()

    agent_id, task = router.route_task("请后端 review 这个接口设计")

    self.assertEqual(agent_id, "backend-1")
    self.assertEqual(task.intent["requested_agent"], "backend-1")
    self.assertEqual(task.intent["collaboration_mode"], "review")
    self.assertEqual(task.routing_reason["strategy"], "explicit-agent")

def test_analyze_task_intent_detects_role_and_deliverables(self):
    router = task_router_module.TaskRouter()

    intent = router.analyze_task_intent("交给 architect 产出 spec 并评审风险")

    self.assertEqual(intent.requested_role, "architect")
    self.assertIn("spec", intent.deliverables)
    self.assertIn("critical", intent.risk_flags)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_task_router -v`
Expected: FAIL because `TaskRouter` does not expose `analyze_task_intent()` and `Task` has no `intent` or `routing_reason`.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class TaskIntent:
    task_type: TaskType
    requested_agent: Optional[str] = None
    requested_role: Optional[str] = None
    collaboration_mode: str = "single"
    deliverables: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
```

```python
def analyze_task_intent(self, content: str) -> TaskIntent:
    ...

def select_best_agent(self, intent: TaskIntent, priority: TaskPriority) -> Tuple[str, Dict[str, str]]:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_task_router -v`
Expected: PASS

### Task 3: Add Step Context And Automatic Handoffs

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_workflow_engine_returns_step_contexts_and_handoffs(self):
    router = router_module.TaskRouter()
    engine = workflow_module.WorkflowEngine(task_router=router, message_bus=None, runtime_store=None)
    workflow = engine.create_workflow(
        "wf-handoff",
        "handoff",
        "demo",
        [
            {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "产出接口 spec"},
            {"id": "implement", "name": "实现", "type": "sequential", "agent": "backend-1", "task": "根据 {design_summary} 完成代码"},
        ],
    )

    result = engine.execute_workflow(workflow.id)

    self.assertIn("step_contexts", result)
    self.assertIn("design", result["step_contexts"])
    self.assertEqual(len(result["handoffs"]), 1)
    self.assertEqual(result["handoffs"][0]["source_step"], "design")
    self.assertEqual(result["handoffs"][0]["target_step"], "implement")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_workflow_runtime -v`
Expected: FAIL because workflow results do not include `step_contexts` or `handoffs`.

- [ ] **Step 3: Write minimal implementation**

```python
def _build_step_context(self, step: WorkflowStep, result: Dict, task_content: str) -> Dict[str, Any]:
    ...

def _merge_step_context_into_variables(self, workflow: Workflow, step_context: Dict[str, Any]) -> None:
    ...

def _build_handoff_payload(...):
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_workflow_runtime -v`
Expected: PASS

### Task 4: Run Targeted Regression And Repo Checks

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\task_router.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.py`

- [ ] **Step 1: Add any CLI assertions needed for workflow result shape**

```python
self.assertIn("handoffs", result)
self.assertIn("step_contexts", result)
```

- [ ] **Step 2: Run targeted control-plane tests**

Run: `python -m unittest tests.control_plane.test_handoff tests.control_plane.test_task_router tests.control_plane.test_workflow_runtime tests.control_plane.test_unified_cli -v`
Expected: PASS

- [ ] **Step 3: Run lint-equivalent checks**

Run: `python -m ruff check .hermes/team/control_plane .hermes/team/调度框架/core tests/control_plane`
Expected: `All checks passed`

- [ ] **Step 4: Run diagnostics check**

Run: get diagnostics for:
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\task_router.py`
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.py`
Expected: no new diagnostics
