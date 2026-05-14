# Agent Capability Phase 6 Phase 7 Governed Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 handoff 在成功消费后自动物化成 `TaskCard`，并补齐持久查询、CLI 查询、RBAC 与审计闭环，把这条 agent 协作提升线收成可编排、可追踪、可治理的终态。

**Architecture:** phase6 在 `HandoffCoordinator` 上扩展最小物化逻辑，复用 `TaskStore.register_task()` 把 handoff 变成稳定的 control plane 任务，并把状态推进到 `materialized`。phase7 新增轻量 `HandoffRunStore` 提供持久查询，再把查询接入 unified CLI 的 `query` 子命令，并走 `RBAC + Audit`，为后续审批导出保留钩子。

**Tech Stack:** Python 3.13, `unittest`, dataclasses, JSON file stores, existing `TaskStore` / `WorkflowRunStore` / `HandoffCoordinator` / unified CLI / governance modules

---

### Task 1: 扩展 HandoffCoordinator 的物化状态与最小 TaskCard 桥接

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`
- Read: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\models.py`
- Read: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\store.py`

- [ ] **Step 1: Write the failing test**

```python
def test_handoff_coordinator_materializes_valid_handoff_into_task_card(self):
    coordinator_module = load_framework_module("handoff_coordinator")
    store_module = load_control_plane_module("store")
    temp_dir = Path(self.temp_dir.name)
    store = store_module.TaskStore(temp_dir / "tasks")

    bus = FakeAckBus(valid_handoff_message())
    coordinator = coordinator_module.HandoffCoordinator(bus, task_store=store)

    result = coordinator.consume_for("backend-1")
    snapshot = store.read_snapshot("handoff-wf-1-design-implement")

    self.assertEqual(result["status"], "materialized")
    self.assertEqual(result["materialized_task_id"], "handoff-wf-1-design-implement")
    self.assertEqual(snapshot["owner_agent"], "backend-1")
    self.assertEqual(snapshot["executor_backend"], "openclaw")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator.HandoffCoordinatorTests.test_handoff_coordinator_materializes_valid_handoff_into_task_card`
Expected: FAIL because `HandoffCoordinator` does not accept `task_store` and never materializes a `TaskCard`.

- [ ] **Step 3: Write minimal implementation**

```python
class HandoffCoordinator:
    def __init__(self, bus, task_store=None, runtime_store=None, audit_logger=None):
        self.bus = bus
        self.task_store = task_store
        self.runtime_store = runtime_store
        self.audit_logger = audit_logger
        self.records = []
```

```python
def build_task_card(self, payload: Dict[str, Any]) -> TaskCard:
    workflow_id = payload.get("context", {}).get("workflow_id", "handoff")
    source_step = payload.get("source_step", "source")
    target_step = payload.get("target_step", "target")
    task_id = f"handoff-{workflow_id}-{source_step}-{target_step}"
    return TaskCard(
        task_id=task_id,
        title=f"Handoff follow-up for {target_step}",
        description=payload.get("summary", ""),
        priority=TaskPriority.NORMAL,
        owner_agent=payload.get("target_agent", "unknown"),
        dependencies=[],
        lock_scope=LockScope(repo_path="."),
        retry_policy=RetryPolicy(max_attempts=1),
        rollback_policy=RollbackPolicy(mode="manual"),
        acceptance_criteria=["consume handoff context"],
        executor_backend=payload.get("selected_backend") or payload.get("target_backend"),
    )
```

```python
def materialize_record(self, record: HandoffRecord, payload: Dict[str, Any]) -> HandoffRecord:
    if not self.task_store:
        return record
    card = self.build_task_card(payload)
    if not self.task_store.read_snapshot(card.task_id):
        self.task_store.register_task(card)
    record.materialized_task_id = card.task_id
    record.materialized_at = time.time()
    record.status = "materialized"
    return record
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator.HandoffCoordinatorTests.test_handoff_coordinator_materializes_valid_handoff_into_task_card`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py
git commit -m "feat: materialize handoffs into task cards"
```

### Task 2: 锁定幂等物化与记录扩展

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_handoff_coordinator_reuses_existing_materialized_task_for_duplicate_message(self):
    coordinator = coordinator_module.HandoffCoordinator(bus, task_store=store)

    first = coordinator.consume_for("backend-1")
    bus.messages = [valid_handoff_message()]
    second = coordinator.consume_for("backend-1")

    self.assertEqual(first["materialized_task_id"], second["materialized_task_id"])
    self.assertEqual(len(store.list_events(first["materialized_task_id"])), 0)
```

```python
def test_handoff_coordinator_records_workflow_and_backend_metadata(self):
    result = coordinator.consume_for("backend-1")
    self.assertEqual(result["workflow_id"], "wf-1")
    self.assertEqual(result["source_backend"], "hermes")
    self.assertEqual(result["target_backend"], "openclaw")
    self.assertEqual(result["selected_backend"], "openclaw")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator`
Expected: FAIL because `HandoffRecord` does not yet persist workflow/backend/materialization metadata or dedupe.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class HandoffRecord:
    message_id: str
    task_id: str
    workflow_id: Optional[str]
    source_agent: Optional[str]
    target_agent: Optional[str]
    source_step: Optional[str]
    target_step: Optional[str]
    source_backend: Optional[str] = None
    target_backend: Optional[str] = None
    selected_backend: Optional[str] = None
    materialized_task_id: Optional[str] = None
    materialized_at: Optional[float] = None
```

```python
def find_record(self, message_id=None, task_id=None):
    for record in self.records:
        if message_id and record.message_id == message_id:
            return record
        if task_id and record.task_id == task_id:
            return record
    return None
```

```python
existing = self.find_record(message_id=getattr(message, "id", None), task_id=str(payload.get("task_id", "")))
if existing and existing.materialized_task_id:
    return existing.to_dict()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py
git commit -m "feat: add handoff materialization metadata"
```

### Task 3: 新增 HandoffRunStore 持久查询层

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py`
- Create: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
def test_handoff_run_store_records_and_filters_records(self):
    store = runtime_module.HandoffRunStore(Path(self.temp_dir.name))
    store.record_handoff({"message_id": "msg-1", "workflow_id": "wf-1", "target_agent": "backend-1", "status": "materialized"})
    store.record_handoff({"message_id": "msg-2", "workflow_id": "wf-1", "target_agent": "qa", "status": "failed"})

    self.assertEqual(store.read_record("msg-1")["status"], "materialized")
    self.assertEqual(len(store.list_records(workflow_id="wf-1")), 2)
    self.assertEqual(len(store.list_records(target_agent="backend-1")), 1)
    self.assertEqual(len(store.list_records(status="failed")), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_handoff_runtime.HandoffRunStoreTests.test_handoff_run_store_records_and_filters_records`
Expected: FAIL because `handoff_runtime.py` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class HandoffRunStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.records_dir = self.base_dir / "records"
        self.records_dir.mkdir(parents=True, exist_ok=True)

    def record_handoff(self, record):
        message_id = record["message_id"]
        path = self.records_dir / f"{message_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def read_record(self, message_id):
        path = self.records_dir / f"{message_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_records(self, workflow_id=None, target_agent=None, status=None):
        records = [json.loads(path.read_text(encoding="utf-8")) for path in self.records_dir.glob("*.json")]
        if workflow_id is not None:
            records = [r for r in records if r.get("workflow_id") == workflow_id]
        if target_agent is not None:
            records = [r for r in records if r.get("target_agent") == target_agent]
        if status is not None:
            records = [r for r in records if r.get("status") == status]
        return sorted(records, key=lambda item: item["message_id"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_handoff_runtime.HandoffRunStoreTests.test_handoff_run_store_records_and_filters_records`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_runtime.py
git commit -m "feat: add handoff runtime store"
```

### Task 4: 将 HandoffCoordinator 接到持久存储与 runtime 事件

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
def test_handoff_coordinator_persists_materialized_record_and_runtime_event(self):
    handoff_store = runtime_module.HandoffRunStore(Path(self.temp_dir.name) / "handoffs")
    workflow_store = workflow_runtime_module.WorkflowRunStore(Path(self.temp_dir.name) / "workflows")
    coordinator = coordinator_module.HandoffCoordinator(bus, task_store=task_store, handoff_store=handoff_store, runtime_store=workflow_store)

    result = coordinator.consume_for("backend-1")
    persisted = handoff_store.read_record("msg-1")
    events = workflow_store.list_step_events("wf-1")

    self.assertEqual(persisted["materialized_task_id"], result["materialized_task_id"])
    self.assertTrue(any(event["event"] == "handoff_materialized" for event in events))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator.HandoffCoordinatorTests.test_handoff_coordinator_persists_materialized_record_and_runtime_event`
Expected: FAIL because the coordinator does not yet write to `handoff_store` or `runtime_store`.

- [ ] **Step 3: Write minimal implementation**

```python
class HandoffCoordinator:
    def __init__(self, bus, task_store=None, handoff_store=None, runtime_store=None, audit_logger=None):
        self.handoff_store = handoff_store
```

```python
if self.handoff_store:
    self.handoff_store.record_handoff(record.to_dict())
if self.runtime_store and record.workflow_id:
    self.runtime_store.record_step_event(
        record.workflow_id,
        record.target_step or "handoff",
        "handoff_materialized",
        {"message_id": record.message_id, "materialized_task_id": record.materialized_task_id},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator.HandoffCoordinatorTests.test_handoff_coordinator_persists_materialized_record_and_runtime_event`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\workflow_runtime.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py
git commit -m "feat: persist handoff materialization events"
```

### Task 5: 扩展 RBAC 与 unified CLI 的 query 子命令

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\rbac.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_governance.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_query_handoff_returns_filtered_records(self):
    result = cli_module.main(["query", "handoff", "--workflow-id", "wf-1", "--actor", "viewer"])
    self.assertEqual(result["records"][0]["workflow_id"], "wf-1")
```

```python
def test_query_handoff_rejects_unauthorized_actor(self):
    with self.assertRaises(PermissionError):
        cli_module.main(["query", "handoff", "--workflow-id", "wf-1", "--actor", "guest"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_unified_cli.UnifiedCliTests.test_query_handoff_returns_filtered_records tests.control_plane.test_unified_cli.UnifiedCliTests.test_query_handoff_rejects_unauthorized_actor`
Expected: FAIL because `query` subcommand and query RBAC do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# cli.py build_parser()
query = subparsers.add_parser("query", help="查询 workflow / handoff / audit")
query.add_argument("resource", choices=["workflow", "handoff", "audit"])
query.add_argument("--id")
query.add_argument("--workflow-id")
query.add_argument("--message-id")
query.add_argument("--target-agent")
query.add_argument("--action")
query.add_argument("--actor", default="viewer")
```

```python
# rbac.py
"admin": {"control_plane.run", "control_plane.dispatch", "provider.execute_sensitive", "monitor.export", "query.workflow", "query.handoff", "query.audit.read"},
"operator": {"control_plane.run", "control_plane.dispatch", "monitor.export", "query.workflow", "query.handoff", "query.audit.read"},
"viewer": {"monitor.read", "query.workflow", "query.handoff", "query.audit.read"},
```

```python
# cli.py main()
if args.command == "query":
    action = f"query.{args.resource}" if args.resource != "audit" else "query.audit.read"
    if not policy.is_allowed(args.actor, action):
        raise PermissionError("actor is not allowed to query")
    if args.resource == "handoff":
        store = HandoffRunStore(Path(config.directories["state_dir"]) / "handoffs")
        records = store.list_records(workflow_id=args.workflow_id, target_agent=args.target_agent)
        payload = {"records": records}
    elif args.resource == "workflow":
        store = WorkflowRunStore(Path(config.directories["workflow_runtime_dir"]))
        payload = {"snapshot": store.read_snapshot(args.id), "events": store.list_step_events(args.id)}
    else:
        payload = {"records": [event for event in audit.read_all() if not args.action or event.get("action") == args.action]}
    audit.log("query", {"actor": args.actor, "resource": args.resource})
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_unified_cli tests.control_plane.test_governance`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\rbac.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_governance.py
git commit -m "feat: add governed query commands"
```

### Task 6: 补 query 审计与持久 handoff 查询回归

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_governance.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_query_command_writes_audit_entry(self):
    cli_module.main(["query", "audit", "--actor", "viewer"])
    events = AuditLogger(Path(self.audit_path)).read_all()
    self.assertTrue(any(event["action"] == "query" for event in events))
```

```python
def test_query_handoff_supports_message_id_filter(self):
    result = cli_module.main(["query", "handoff", "--message-id", "msg-1", "--actor", "viewer"])
    self.assertEqual([record["message_id"] for record in result["records"]], ["msg-1"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_unified_cli tests.control_plane.test_handoff_runtime`
Expected: FAIL because `query handoff` does not yet support all filters or audit assertions.

- [ ] **Step 3: Write minimal implementation**

```python
records = store.list_records(
    workflow_id=args.workflow_id,
    target_agent=args.target_agent,
)
if args.message_id:
    records = [record for record in records if record.get("message_id") == args.message_id]
```

```python
audit.log(
    "query",
    {"actor": args.actor, "resource": args.resource, "workflow_id": args.workflow_id, "message_id": args.message_id},
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_unified_cli tests.control_plane.test_handoff_runtime tests.control_plane.test_governance`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_runtime.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_governance.py
git commit -m "test: cover governed handoff queries"
```

### Task 7: 总回归与诊断收尾

**Files:**
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\rbac.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_runtime.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_governance.py`

- [ ] **Step 1: Run focused regression**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator tests.control_plane.test_handoff_runtime tests.control_plane.test_unified_cli tests.control_plane.test_governance`
Expected: PASS

- [ ] **Step 2: Run broader related regression**

Run: `python -m unittest tests.control_plane.test_workflow_runtime tests.control_plane.test_handoff tests.control_plane.test_persistent_bus tests.control_plane.test_task_router tests.control_plane.test_framework_workflow tests.control_plane.test_provider_registry tests.control_plane.test_executor tests.control_plane.test_adapters`
Expected: PASS

- [ ] **Step 3: Run diagnostics**

Run diagnostics for:
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py`
- `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py`
- `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\rbac.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_runtime.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_governance.py`

Expected: no new diagnostics

- [ ] **Step 4: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\handoff_runtime.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\rbac.py d:\KIMIK2.5\AIAgent\tests\control_plane
git commit -m "feat: complete governed handoff workflow"
```

---

## Self-Review Checklist

- **Spec coverage:** Task 1-2 覆盖 handoff 物化与幂等；Task 3-4 覆盖持久查询与 runtime 关联；Task 5-6 覆盖 CLI 查询、RBAC、审计；Task 7 覆盖总回归与诊断。
- **Placeholder scan:** 无 `TBD/TODO`；每一步包含具体测试、命令或代码片段。
- **Type consistency:** `materialized_task_id`、`workflow_id`、`selected_backend`、`query.handoff` 等名称在各任务中保持一致；`HandoffCoordinator` 的新增依赖统一使用 `task_store / handoff_store / runtime_store / audit_logger`。
