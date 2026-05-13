# Agent Capability Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the second-phase upper-layer agent capability loop with reviewer-aware routing, accumulated collaboration context, and explainable backend handoffs.

**Architecture:** Extend the first-phase routing and workflow structures in place. `TaskRouter` adds reviewer-first soft constraints and fallback reasoning, `WorkflowEngine` aggregates per-step outputs into a global collaboration context, and `HandoffPayload` records backend candidates, selected backend, and backend rationale without changing real provider execution.

**Tech Stack:** Python, `unittest`, dataclasses, existing control-plane config/runtime modules

---

### Task 1: Lock Reviewer Routing Behavior With Tests

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_task_router.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\task_router.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_review_task_prefers_qa_pool(self):
    router = task_router_module.TaskRouter()

    agent_id, task = router.route_task("请 review 这个接口变更，给出回归建议")

    self.assertEqual(agent_id, "qa-functional")
    self.assertEqual(task.routing_reason["review_policy"], "soft-prefer-reviewer")
    self.assertFalse(task.routing_reason["fallback_used"])

def test_review_task_falls_back_when_qa_pool_is_full(self):
    router = task_router_module.TaskRouter()
    router.agents["qa-functional"].current_tasks = router.agents["qa-functional"].max_tasks
    router.agents["qa-performance"].current_tasks = router.agents["qa-performance"].max_tasks

    agent_id, task = router.route_task("请 review 这个接口变更，给出回归建议")

    self.assertNotIn(agent_id, {"qa-functional", "qa-performance"})
    self.assertTrue(task.routing_reason["fallback_used"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_task_router -v`
Expected: FAIL because reviewer pool preference and fallback explanation do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def _reviewer_candidate_pool(self, intent: TaskIntent) -> List[str]:
    if "performance" in intent.risk_flags:
        return ["qa-performance", "qa-functional"]
    return ["qa-functional", "qa-performance"]
```

```python
return selected_agent, {
    "strategy": "reviewer-preferred",
    "review_policy": "soft-prefer-reviewer",
    "fallback_used": fallback_used,
    "candidate_pool": candidate_pool,
    "excluded_agents": excluded_agents,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_task_router -v`
Expected: PASS

### Task 2: Lock Collaboration Context Aggregation With Tests

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workflow_engine_accumulates_collaboration_context(self):
    engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
    workflow = engine.create_workflow(
        "wf-collab",
        "collab",
        "demo",
        [
            {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
            {"id": "review", "name": "评审", "type": "sequential", "agent": "qa-functional", "task": "评审 {design_summary}", "dependencies": ["design"]},
        ],
    )

    engine._execute_agent_task = lambda step, task_content: {
        "success": True,
        "output": f"{step.id}:{task_content}",
        "agent": step.agent,
        "artifacts": [f"{step.id}.md"],
        "open_questions": [f"{step.id}-q"],
        "risks": [f"{step.id}-risk"],
        "decisions": [{"summary": f"{step.id}-decision"}],
    }
    result = engine.execute_workflow(workflow.id)

    self.assertIn("collaboration_context", result)
    self.assertEqual(result["collaboration_context"]["artifacts"], ["design.md", "review.md"])
    self.assertEqual(len(result["collaboration_context"]["decisions"]), 2)
```

- [ ] **Step 2: Run tests to verify it fails**

Run: `python -m unittest tests.control_plane.test_workflow_runtime -v`
Expected: FAIL because workflow results do not include `collaboration_context`.

- [ ] **Step 3: Write minimal implementation**

```python
workflow.variables.setdefault(
    "collaboration_context",
    {"artifacts": [], "open_questions": [], "risks": [], "decisions": []},
)
```

```python
def _merge_unique_list(target: List[str], values: List[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)
```

- [ ] **Step 4: Run tests to verify it passes**

Run: `python -m unittest tests.control_plane.test_workflow_runtime -v`
Expected: PASS

### Task 3: Lock Backend Explanation Fields With Tests

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_handoff_payload_supports_backend_explanation_fields(self):
    payload = handoff_module.HandoffPayload.create(
        source_backend="hermes",
        target_backend="openclaw",
        task_id="task-2",
        summary="handoff",
        context={},
        selected_backend="openclaw",
        backend_candidates=["hermes", "openclaw"],
        backend_reason="needs external execution",
        review_policy="soft-prefer-reviewer",
    )

    data = payload.to_dict()

    self.assertEqual(data["selected_backend"], "openclaw")
    self.assertEqual(data["backend_candidates"], ["hermes", "openclaw"])
    self.assertTrue(handoff_module.validate_handoff_payload(data))
```

```python
def test_workflow_handoff_contains_backend_reason(self):
    ...
    self.assertIn("selected_backend", result["handoffs"][0])
    self.assertIn("backend_reason", result["handoffs"][0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_handoff tests.control_plane.test_workflow_runtime -v`
Expected: FAIL because backend explanation fields are not yet supported.

- [ ] **Step 3: Write minimal implementation**

```python
selected_backend: Optional[str] = None
backend_candidates: List[str] = field(default_factory=list)
backend_reason: Optional[str] = None
review_policy: Optional[str] = None
```

```python
backend_recommendation = step_context.get("backend_recommendation") or {}
selected_backend = backend_recommendation.get("selected_backend", source_backend)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_handoff tests.control_plane.test_workflow_runtime -v`
Expected: PASS

### Task 4: Run Targeted Regression And Diagnostics

**Files:**
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\task_router.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_task_router.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff.py`

- [ ] **Step 1: Run targeted tests**

Run: `python -m unittest tests.control_plane.test_task_router tests.control_plane.test_workflow_runtime tests.control_plane.test_handoff -v`
Expected: PASS

- [ ] **Step 2: Run scoped ruff checks**

Run: `python -m ruff check .hermes/team/control_plane/protocols/handoff.py .hermes/team/调度框架/core/task_router.py .hermes/team/调度框架/core/workflow_engine.py tests/control_plane/test_task_router.py tests/control_plane/test_workflow_runtime.py tests/control_plane/test_handoff.py`
Expected: `All checks passed!`

- [ ] **Step 3: Run diagnostics checks**

Run diagnostics for:
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\task_router.py`
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_task_router.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff.py`
Expected: no new diagnostics
