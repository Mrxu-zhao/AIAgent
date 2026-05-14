# Agent Capability A Closure B Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先把 agent 能力线正式封口，再继续补齐 `handoff -> TaskCard -> 自动执行 -> workflow continuation/resume`，完成文档、治理、契约和 continuation 的一体化收尾。

**Architecture:** A 段先收口文档、运行时产物目录和对外契约，避免 continuation 做完后再返工协议与状态目录。B 段在现有 `HandoffCoordinator`、`TaskStore`、`WorkflowRunStore` 与 unified CLI 之上，先实现 handoff 自动 dispatch `TaskCard`，再实现最小 `resume_workflow(workflow_id)`，并让 handoff/task/workflow 三层状态可查询、可审计。

**Tech Stack:** Python 3.13, `unittest`, JSON file stores, existing `WorkflowRunStore` / `HandoffRunStore` / `TaskStore` / `ControlPlaneExecutor` / unified CLI / governance modules

---

### Task 1: 文档总览与对外契约收口

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\docs\architecture\control-plane-overview.md`
- Create: `d:\KIMIK2.5\AIAgent\docs\contracts\handoff-contract.md`
- Create: `d:\KIMIK2.5\AIAgent\docs\contracts\provider-contracts.md`
- Create: `d:\KIMIK2.5\AIAgent\docs\runtime\runtime-governance.md`
- Create: `d:\KIMIK2.5\AIAgent\docs\runtime\handoff-and-continuation.md`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\README.md`

- [ ] **Step 1: Write the failing documentation-oriented test**

```python
def test_control_plane_readme_links_to_overview_and_runtime_governance(self):
    readme = Path(".hermes/team/control_plane/README.md").read_text(encoding="utf-8")
    assert "docs/architecture/control-plane-overview.md" in readme
    assert "docs/runtime/runtime-governance.md" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_documentation_contracts.DocumentationContractsTests.test_control_plane_readme_links_to_overview_and_runtime_governance`
Expected: FAIL because the docs and links do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```md
# Control Plane Overview

- 当前推荐入口
- phase1-7 能力总览
- 已支持边界
- 未支持边界
- 推荐查询与治理入口
```

```md
# Handoff Contract

- payload 真源：`control_plane/protocols/handoff.py`
- schema 真源：`control_plane/protocols/handoff.schema.json`
- bus envelope：`MessageType.HANDOFF + {"task_id","context"}`
- `selected_backend/target_backend/backend_reason` 语义
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_documentation_contracts.DocumentationContractsTests.test_control_plane_readme_links_to_overview_and_runtime_governance`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\docs\architecture\control-plane-overview.md d:\KIMIK2.5\AIAgent\docs\contracts\handoff-contract.md d:\KIMIK2.5\AIAgent\docs\contracts\provider-contracts.md d:\KIMIK2.5\AIAgent\docs\runtime\runtime-governance.md d:\KIMIK2.5\AIAgent\docs\runtime\handoff-and-continuation.md d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\README.md
git commit -m "docs: close out agent capability line"
```

### Task 2: 对齐 handoff schema 与代码协议

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.schema.json`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff.py`

- [ ] **Step 1: Write the failing test**

```python
def test_handoff_schema_includes_extended_backend_and_review_fields(self):
    schema = json.loads(Path(".hermes/team/control_plane/protocols/handoff.schema.json").read_text(encoding="utf-8"))
    properties = schema["properties"]
    assert "source_agent" in properties
    assert "target_agent" in properties
    assert "selected_backend" in properties
    assert "backend_candidates" in properties
    assert "backend_reason" in properties
    assert "review_policy" in properties
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_handoff.HandoffProtocolTests.test_handoff_schema_includes_extended_backend_and_review_fields`
Expected: FAIL because the current schema is slimmer than `handoff.py`.

- [ ] **Step 3: Write minimal implementation**

```json
{
  "properties": {
    "source_agent": {"type": "string"},
    "target_agent": {"type": "string"},
    "source_step": {"type": "string"},
    "target_step": {"type": "string"},
    "selected_backend": {"type": "string"},
    "backend_candidates": {"type": "array", "items": {"type": "string"}},
    "backend_reason": {"type": "string"},
    "review_policy": {"type": ["string", "null"]}
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_handoff.HandoffProtocolTests.test_handoff_schema_includes_extended_backend_and_review_fields`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.schema.json d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff.py
git commit -m "feat: align handoff schema with payload contract"
```

### Task 3: 运行时目录分层与 store 路径治理

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\config.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
def test_default_runtime_directories_use_runs_subtree(self):
    config = config_module.load_control_plane_config()
    self.assertIn("state/runs/workflow_runtime", config.directories["workflow_runtime_dir"].replace("\\", "/"))
```

```python
def test_handoff_run_store_defaults_to_runs_handoffs_directory(self):
    store = runtime_module.HandoffRunStore()
    self.assertIn("state/runs/handoffs", str(store.base_dir).replace("\\", "/"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_default_runtime_directories_use_runs_subtree tests.control_plane.test_handoff_runtime.HandoffRunStoreTests.test_handoff_run_store_defaults_to_runs_handoffs_directory`
Expected: FAIL because runtime still defaults to legacy mixed directories.

- [ ] **Step 3: Write minimal implementation**

```python
# config.py
"workflow_runtime_dir": str(base / "state" / "runs" / "workflow_runtime"),
"handoff_runtime_dir": str(base / "state" / "runs" / "handoffs"),
"runtime_fixtures_dir": str(base / "state" / "fixtures"),
```

```python
# handoff_runtime.py
def __init__(self, base_dir: Optional[Path] = None):
    root = Path(base_dir) if base_dir is not None else Path(load_control_plane_config().directories["handoff_runtime_dir"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_default_runtime_directories_use_runs_subtree tests.control_plane.test_handoff_runtime.HandoffRunStoreTests.test_handoff_run_store_defaults_to_runs_handoffs_directory`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\config.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\workflow_runtime.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_runtime.py
git commit -m "feat: separate runtime runs from fixtures"
```

### Task 4: 为 runtime stores 增加治理接口与 CLI 治理动作

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\rbac.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_governance.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_query_handoff_prune_removes_filtered_runtime_records(self):
    result = cli_module.main(["query", "handoff", "--status", "failed", "--prune", "--actor", "operator"])
    self.assertGreaterEqual(result["deleted_count"], 1)
```

```python
def test_query_handoff_prune_requires_operator_or_admin(self):
    with self.assertRaises(PermissionError):
        cli_module.main(["query", "handoff", "--status", "failed", "--prune", "--actor", "viewer"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_unified_cli.UnifiedCLITests.test_query_handoff_prune_removes_filtered_runtime_records tests.control_plane.test_unified_cli.UnifiedCLITests.test_query_handoff_prune_requires_operator_or_admin`
Expected: FAIL because prune/archive management actions do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# handoff_runtime.py
def delete_records(self, workflow_id=None, target_agent=None, status=None):
    records = self.list_records(workflow_id=workflow_id, target_agent=target_agent, status=status)
    for record in records:
        (self.records_dir / f"{record['message_id']}.json").unlink(missing_ok=True)
    return len(records)
```

```python
# cli.py query handoff
if args.prune:
    if not policy.is_allowed(args.actor, "query.handoff.manage"):
        raise PermissionError("actor is not allowed to prune handoff runtime")
    deleted = store.delete_records(workflow_id=args.workflow_id, target_agent=args.target_agent, status=args.status)
    payload = {"deleted_count": deleted}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_unified_cli.UnifiedCLITests.test_query_handoff_prune_removes_filtered_runtime_records tests.control_plane.test_unified_cli.UnifiedCLITests.test_query_handoff_prune_requires_operator_or_admin`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\workflow_runtime.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\rbac.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_governance.py
git commit -m "feat: add runtime governance actions"
```

### Task 5: handoff 自动 dispatch 物化 TaskCard

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\executor.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`

- [ ] **Step 1: Write the failing test**

```python
def test_handoff_coordinator_dispatches_materialized_task_once(self):
    dispatched = []

    class FakeDispatcher:
        def execute_task(self, card, adapter):
            dispatched.append(card.task_id)
            return {"status": "done", "stdout": "ok", "stderr": ""}

    coordinator = coordinator_module.HandoffCoordinator(
        bus,
        task_store=store,
        dispatcher=FakeDispatcher(),
        adapter=object(),
    )
    result = coordinator.consume_for("backend-1")

    self.assertEqual(result["status"], "dispatched")
    self.assertEqual(dispatched, ["handoff-wf-1-design-implement"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator.HandoffCoordinatorTests.test_handoff_coordinator_dispatches_materialized_task_once`
Expected: FAIL because `HandoffCoordinator` does not auto-dispatch materialized tasks yet.

- [ ] **Step 3: Write minimal implementation**

```python
class HandoffCoordinator:
    def __init__(self, bus, task_store=None, handoff_store=None, runtime_store=None, dispatcher=None, adapter=None):
        self.dispatcher = dispatcher
        self.adapter = adapter
```

```python
def _dispatch_materialized_task(self, record, payload):
    if not self.dispatcher or not record.materialized_task_id:
        return
    task_card = self._build_task_card(payload)
    self.dispatcher.execute_task(task_card, self.adapter)
    record.status = "dispatched"
    record.dispatched_at = time.time()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator.HandoffCoordinatorTests.test_handoff_coordinator_dispatches_materialized_task_once`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\executor.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py
git commit -m "feat: auto-dispatch materialized handoff tasks"
```

### Task 6: 实现最小 workflow continuation / resume

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\continuation.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Create: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_continuation.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_resume_workflow_reconstructs_pending_steps_from_snapshot_and_events(self):
    store.record_workflow_started("wf-1", {"name": "demo"})
    store.record_step_event("wf-1", "design", "completed", {"summary": "done"})
    store.record_step_event("wf-1", "implement", "pending", {})

    state = continuation_module.resume_workflow("wf-1", runtime_store=store)
    self.assertEqual(state["completed_steps"], ["design"])
    self.assertEqual(state["ready_steps"], ["implement"])
```

```python
def test_handoff_dispatch_can_trigger_workflow_resume(self):
    result = coordinator.consume_for("backend-1")
    self.assertEqual(result["continuation_status"], "continued")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_continuation tests.control_plane.test_handoff_coordinator`
Expected: FAIL because `continuation.py` and workflow resume logic do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def resume_workflow(workflow_id: str, runtime_store):
    snapshot = runtime_store.read_snapshot(workflow_id)
    events = runtime_store.list_step_events(workflow_id)
    completed = []
    pending = []
    for event in events:
        if event["status"] == "completed":
            completed.append(event["step_id"])
        elif event["status"] in {"pending", "handoff_materialized"}:
            pending.append(event["step_id"])
    return {
        "workflow_id": workflow_id,
        "snapshot": snapshot,
        "completed_steps": sorted(set(completed)),
        "ready_steps": sorted(set(step for step in pending if step not in completed)),
    }
```

```python
# handoff_coordinator.py
if self.runtime_store and record.workflow_id:
    continuation = resume_workflow(record.workflow_id, self.runtime_store)
    record.continuation_workflow_id = record.workflow_id
    record.continuation_status = "continued" if continuation["ready_steps"] else "noop"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_continuation tests.control_plane.test_handoff_coordinator`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\continuation.py d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\workflow_runtime.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_continuation.py
git commit -m "feat: add minimal workflow continuation"
```

### Task 7: continuation 查询、回退与事件对齐

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_continuation.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_query_handoff_returns_continuation_metadata(self):
    result = cli_module.main(["query", "handoff", "--message-id", "msg-1", "--actor", "viewer"])
    self.assertEqual(result["records"][0]["continuation_status"], "continued")
```

```python
def test_continuation_failure_falls_back_to_dispatched_state(self):
    coordinator = coordinator_module.HandoffCoordinator(..., runtime_store=BrokenRuntimeStore())
    result = coordinator.consume_for("backend-1")
    self.assertEqual(result["status"], "dispatched")
    self.assertEqual(result["continuation_status"], "failed")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_unified_cli tests.control_plane.test_continuation tests.control_plane.test_handoff_coordinator`
Expected: FAIL because continuation metadata and fallback states are not yet fully surfaced.

- [ ] **Step 3: Write minimal implementation**

```python
try:
    continuation = resume_workflow(record.workflow_id, self.runtime_store)
    record.continuation_status = "continued" if continuation["ready_steps"] else "noop"
except Exception as exc:
    record.continuation_status = "failed"
    record.error = str(exc)
```

```python
# cli query handoff result should include persisted continuation fields unchanged
payload = {"records": records}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_unified_cli tests.control_plane.test_continuation tests.control_plane.test_handoff_coordinator`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_continuation.py
git commit -m "feat: surface continuation status and fallback"
```

### Task 8: 总回归与诊断收尾

**Files:**
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\continuation.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\workflow_runtime.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\rbac.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_runtime.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_continuation.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_governance.py`

- [ ] **Step 1: Run focused regression**

Run: `python -m unittest tests.control_plane.test_handoff tests.control_plane.test_handoff_coordinator tests.control_plane.test_handoff_runtime tests.control_plane.test_workflow_runtime tests.control_plane.test_continuation tests.control_plane.test_unified_cli tests.control_plane.test_governance`
Expected: PASS

- [ ] **Step 2: Run broader related regression**

Run: `python -m unittest tests.control_plane.test_persistent_bus tests.control_plane.test_task_router tests.control_plane.test_framework_workflow tests.control_plane.test_provider_registry tests.control_plane.test_executor tests.control_plane.test_adapters tests.control_plane.test_store tests.control_plane.test_tool_cli tests.control_plane.test_tool_session_store`
Expected: PASS

- [ ] **Step 3: Run diagnostics**

Run diagnostics for all files listed above.
Expected: no new diagnostics

- [ ] **Step 4: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\docs d:\KIMIK2.5\AIAgent\.hermes\team\control_plane d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core d:\KIMIK2.5\AIAgent\tests\control_plane
git commit -m "feat: close and continue agent capability line"
```

---

## Self-Review Checklist

- **Spec coverage:** Task 1-4 完成 A 段的文档、契约、目录治理、CLI 治理；Task 5-7 完成 B 段的自动 dispatch、workflow continuation、查询与回退；Task 8 负责总回归与诊断。
- **Placeholder scan:** 无 `TBD/TODO`；每一步都包含具体测试、命令或实现片段。
- **Type consistency:** `materialized_task_id`、`dispatched_at`、`continuation_status`、`query.handoff.manage`、`state/runs/*` 等名称在各任务中保持一致。
