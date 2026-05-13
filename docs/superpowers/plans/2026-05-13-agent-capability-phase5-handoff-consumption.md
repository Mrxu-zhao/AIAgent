# Agent Capability Phase 5 Handoff Consumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通 handoff 的最小消费闭环，让 `WorkflowEngine` 发布的 handoff 能以稳定消息结构进入 `MessageBus`，并被 `HandoffCoordinator` 接收、校验、签收或失败记录。

**Architecture:** 保持现有 `HandoffPayload` 协议不变，只增强 handoff 的发布结构与消费闭环。发布侧由 `WorkflowEngine` 优先发送标准 `MessageType.HANDOFF` 消息；消费侧新增 `HandoffCoordinator`，使用 `MessageBus.receive/ack/nack` 建立 `sent -> received -> acked/failed` 的最小状态流转，并保留对轻量 FakeBus 的兼容。

**Tech Stack:** Python 3.13, `unittest`, dataclasses, existing `message_bus` / `handoff` / `workflow_engine`, control_plane persistent bus compatibility

---

### Task 1: 锁定标准 Handoff 消息发布结构

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\message_bus.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workflow_publishes_standard_handoff_message_when_bus_supports_factory(self):
    published = {}

    class FakeBus:
        def create_handoff_message(self, from_agent, to_agent, task_id, context, priority=None):
            published["factory"] = {
                "from_agent": from_agent,
                "to_agent": to_agent,
                "task_id": task_id,
                "context": context,
            }
            return {"kind": "handoff-message", "task_id": task_id, "context": context}

        def send(self, message):
            published["message"] = message
            return True

    engine = workflow_module.WorkflowEngine(task_router=None, message_bus=FakeBus(), runtime_store=None)
    workflow = engine.create_workflow(
        "wf-standard-handoff",
        "standard-handoff",
        "demo",
        [
            {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
            {"id": "implement", "name": "实现", "type": "sequential", "agent": "backend-1", "task": "实现代码", "dependencies": ["design"]},
        ],
    )
    engine._execute_agent_task = lambda step, task_content: {"success": True, "output": "ok", "agent": step.agent}

    engine.execute_workflow(workflow.id)

    self.assertEqual(published["factory"]["from_agent"], "architect")
    self.assertEqual(published["factory"]["to_agent"], "backend-1")
    self.assertEqual(published["message"]["kind"], "handoff-message")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_publishes_standard_handoff_message_when_bus_supports_factory`
Expected: FAIL because `WorkflowEngine` still sends a raw dict and never calls `create_handoff_message(...)`.

- [ ] **Step 3: Write minimal implementation**

```python
def _publish_handoff_message(self, handoff_payload: Dict[str, Any]) -> None:
    if not self.message_bus:
        return
    if hasattr(self.message_bus, "create_handoff_message"):
        message = self.message_bus.create_handoff_message(
            handoff_payload.get("source_agent"),
            handoff_payload.get("target_agent"),
            handoff_payload.get("task_id"),
            handoff_payload,
        )
        self.message_bus.send(message)
        return
    self.message_bus.send({"type": "handoff", "payload": handoff_payload})
```

```python
# in _record_followup_handoffs()
handoff_payload = payload.to_dict()
workflow.handoffs.append(handoff_payload)
self._publish_handoff_message(handoff_payload)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_workflow_runtime.WorkflowRuntimeTests.test_workflow_publishes_standard_handoff_message_when_bus_supports_factory`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py
git commit -m "feat: publish handoffs as standard bus messages"
```

### Task 2: 新增 HandoffCoordinator 基础消费器

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- Test: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`

- [ ] **Step 1: Write the failing test**

```python
def test_handoff_coordinator_consumes_and_acks_valid_handoff(self):
    received = []

    class FakeBus:
        def __init__(self):
            self.messages = [
                type(
                    "Msg",
                    (),
                    {
                        "id": "msg-1",
                        "type": message_bus_module.MessageType.HANDOFF,
                        "from_agent": "architect",
                        "to_agent": "backend-1",
                        "content": {
                            "task_id": "wf-1:design->implement",
                            "context": {
                                "source_agent": "architect",
                                "target_agent": "backend-1",
                                "source_step": "design",
                                "target_step": "implement",
                                "summary": "handoff",
                                "task_id": "wf-1:design->implement",
                                "source_backend": "hermes",
                                "target_backend": "openclaw",
                            },
                        },
                    },
                )()
            ]

        def receive(self, agent_id, timeout=0.1):
            return self.messages.pop(0) if self.messages else None

        def ack(self, agent_id, message_id):
            received.append((agent_id, message_id))
            return True

    coordinator = coordinator_module.HandoffCoordinator(FakeBus())
    result = coordinator.consume_for("backend-1")

    self.assertEqual(result["status"], "acked")
    self.assertEqual(received, [("backend-1", "msg-1")])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator.HandoffCoordinatorTests.test_handoff_coordinator_consumes_and_acks_valid_handoff`
Expected: FAIL because `handoff_coordinator.py` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class HandoffRecord:
    message_id: str
    task_id: str
    source_agent: Optional[str]
    target_agent: Optional[str]
    source_step: Optional[str]
    target_step: Optional[str]
    status: str
    created_at: float
    received_at: Optional[float] = None
    acked_at: Optional[float] = None
    error: Optional[str] = None
```

```python
class HandoffCoordinator:
    def __init__(self, bus):
        self.bus = bus
        self.records = []

    def consume_for(self, agent_id: str):
        message = self.bus.receive(agent_id)
        if not message:
            return None
        return self.handle_message(agent_id, message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator.HandoffCoordinatorTests.test_handoff_coordinator_consumes_and_acks_valid_handoff`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py
git commit -m "feat: add minimal handoff coordinator"
```

### Task 3: 锁定 Handoff 状态流转与失败处理

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_handoff_coordinator_marks_failed_for_invalid_payload(self):
    class FakeBus:
        def receive(self, agent_id, timeout=0.1):
            return type(
                "Msg",
                (),
                {
                    "id": "msg-2",
                    "type": message_bus_module.MessageType.HANDOFF,
                    "from_agent": "architect",
                    "to_agent": "backend-1",
                    "content": {"task_id": "wf-1:design->implement", "context": {"broken": True}},
                },
            )()

        def ack(self, agent_id, message_id):
            raise AssertionError("ack should not be called for invalid payload")

        def nack(self, agent_id, message_id):
            return True

    coordinator = coordinator_module.HandoffCoordinator(FakeBus())
    result = coordinator.consume_for("backend-1")

    self.assertEqual(result["status"], "failed")
    self.assertIn("invalid handoff payload", result["error"])
```

```python
def test_handoff_coordinator_returns_none_when_no_message(self):
    class FakeBus:
        def receive(self, agent_id, timeout=0.1):
            return None

    coordinator = coordinator_module.HandoffCoordinator(FakeBus())
    self.assertIsNone(coordinator.consume_for("backend-1"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator`
Expected: FAIL because invalid payload handling and no-message behavior are not fully implemented.

- [ ] **Step 3: Write minimal implementation**

```python
def handle_message(self, agent_id: str, message):
    payload = message.content.get("context", {})
    if not validate_handoff_payload(payload):
        record = self._record_failed(message, payload, "invalid handoff payload")
        if hasattr(self.bus, "nack"):
            self.bus.nack(agent_id, message.id)
        return record
    record = self._record_received(message, payload)
    if hasattr(self.bus, "ack"):
        self.bus.ack(agent_id, message.id)
    record["status"] = "acked"
    record["acked_at"] = time.time()
    return record
```

```python
def get_records(self, task_id: Optional[str] = None):
    if task_id is None:
        return list(self.records)
    return [record for record in self.records if record["task_id"] == task_id]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.control_plane.test_handoff_coordinator`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py
git commit -m "feat: add handoff status transitions"
```

### Task 4: 回归 MessageBus 与 Workflow Handoff 闭环

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_persistent_bus.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_message_bus_create_handoff_message_round_trips_through_receive(self):
    bus = message_bus_module.MessageBus()
    bus.register_agent("architect")
    bus.register_agent("backend-1")

    msg = bus.create_handoff_message(
        "architect",
        "backend-1",
        "wf-1:design->implement",
        {"task_id": "wf-1:design->implement", "summary": "handoff"},
    )
    bus.send(msg)
    received = bus.receive("backend-1")

    self.assertEqual(received.type, message_bus_module.MessageType.HANDOFF)
    self.assertEqual(received.content["task_id"], "wf-1:design->implement")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.control_plane.test_persistent_bus.PersistentBusTests.test_message_bus_create_handoff_message_round_trips_through_receive`
Expected: FAIL if current handoff message factory or receive path cannot preserve the expected structure.

- [ ] **Step 3: Write minimal implementation**

```python
def create_handoff_message(self, from_agent, to_agent, task_id, context, priority=MessagePriority.HIGH):
    return Message.create(
        MessageType.HANDOFF,
        from_agent,
        to_agent,
        {"task_id": task_id, "context": context},
        priority,
    )
```

```python
# keep send/receive path unchanged; only ensure tests use Message objects consistently
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.control_plane.test_persistent_bus.PersistentBusTests.test_message_bus_create_handoff_message_round_trips_through_receive`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\message_bus.py d:\KIMIK2.5\AIAgent\tests\control_plane\test_persistent_bus.py
git commit -m "test: cover handoff bus round trip"
```

### Task 5: 回归与诊断收尾

**Files:**
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- Verify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\message_bus.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_persistent_bus.py`
- Verify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_unified_cli.py`

- [ ] **Step 1: Run focused regression**

Run: `python -m unittest tests.control_plane.test_workflow_runtime tests.control_plane.test_handoff tests.control_plane.test_persistent_bus tests.control_plane.test_handoff_coordinator tests.control_plane.test_unified_cli`
Expected: PASS

- [ ] **Step 2: Run broader related regression**

Run: `python -m unittest tests.control_plane.test_task_router tests.control_plane.test_framework_workflow tests.control_plane.test_provider_registry`
Expected: PASS

- [ ] **Step 3: Run diagnostics checks**

Run diagnostics for:
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py`
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\message_bus.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff_coordinator.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_persistent_bus.py`

Expected: no new diagnostics

- [ ] **Step 4: Commit**

```bash
git add d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\handoff_coordinator.py d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\message_bus.py d:\KIMIK2.5\AIAgent\tests\control_plane
git commit -m "feat: add minimal handoff consumption loop"
```

---

## Self-Review Checklist

- **Spec coverage:** Task 1 覆盖稳定发布结构；Task 2 覆盖 coordinator 最小消费器；Task 3 覆盖状态流转和失败处理；Task 4 覆盖 message bus round-trip；Task 5 覆盖回归与诊断。
- **Placeholder scan:** 无 `TODO/TBD`；每一步包含具体测试、命令或代码片段。
- **Type consistency:** 发布侧统一以 `HANDOFF` 消息结构承载完整 payload；消费侧 `HandoffRecord` 只描述消费态，不替代 `HandoffPayload`；`ack/nack` 仅由 `HandoffCoordinator` 触发。

---

Plan complete and saved to `docs/superpowers/plans/2026-05-13-agent-capability-phase5-handoff-consumption.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration  
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
