# Control Plane Session、Tools 与最小权限模型 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为控制平面工具运行时补齐单 session 恢复、4 个高频工具以及 tool 级最小权限模型。

**Architecture:** 在上一轮 `tool runtime MVP` 之上新增 `SessionStore` 和 compact session snapshot；扩展 builtin tools；把 tool action、RBAC 与审批检查接到 `ToolExecutor` 执行前。CLI 继续以 `tool-run` 为主入口，并新增 `tool-session` 查询入口。

**Tech Stack:** Python 3、argparse、dataclasses、pathlib、json、unittest

---

### Task 1: Session Store 红绿闭环

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_tool_session_store.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\session_store.py`

- [ ] **Step 1: 写失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.session_store import SessionStore


class ToolSessionStoreTests(unittest.TestCase):
    def test_create_and_resume_session_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "sessions")
            snapshot = store.create_session(
                task="请 architect review",
                agent_id="architect",
                backend="hermes",
                knowledge_bundle={"paths": [".hermes/team/knowledge/status.md"]},
                intent={"task_type": "architecture"},
            )
            updated = store.update_session(
                snapshot["session_id"],
                last_tool_name="read_knowledge",
                last_tool_result={"ok": True, "content_preview": "knowledge:1"},
                history_entry={"tool_name": "read_knowledge", "ok": True},
            )
            resumed = store.read_session(snapshot["session_id"])
            self.assertEqual(resumed["last_tool_name"], "read_knowledge")
            self.assertEqual(updated["history"][0]["tool_name"], "read_knowledge")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_session_store -v`
Expected: FAIL，提示 `tools.session_store` 或 `SessionStore` 不存在。

- [ ] **Step 3: 写最小实现**

```python
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path


class SessionStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, task, agent_id, backend, knowledge_bundle, intent):
        session_id = str(uuid.uuid4())
        snapshot = {
            "session_id": session_id,
            "task": task,
            "agent_id": agent_id,
            "backend": backend,
            "status": "ready",
            "created_at": time.time(),
            "updated_at": time.time(),
            "last_tool_name": None,
            "last_tool_result": None,
            "knowledge_bundle": knowledge_bundle,
            "intent": intent,
            "history": [],
        }
        self._write(session_id, snapshot)
        return snapshot
```

```python
    def read_session(self, session_id):
        return json.loads(self._path(session_id).read_text(encoding="utf-8"))

    def update_session(self, session_id, **updates):
        snapshot = self.read_session(session_id)
        history_entry = updates.pop("history_entry", None)
        snapshot.update(updates)
        snapshot["updated_at"] = time.time()
        if history_entry is not None:
            snapshot.setdefault("history", []).append(history_entry)
        self._write(session_id, snapshot)
        return snapshot
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_session_store -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_tool_session_store.py .hermes/team/control_plane/tools/session_store.py
git commit -m "feat: add tool session store"
```

### Task 2: 扩展 ToolSpec、权限检查与 transcript

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_tool_executor.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_tool_transcript.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\spec.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\executor.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\transcript.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\tool_permissions.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\governance\rbac.py`

- [ ] **Step 1: 写失败测试**

```python
def test_execute_many_denies_write_tool_for_viewer(self):
    tool = ToolSpec(
        name="route_task",
        description="route task",
        input_schema={},
        is_read_only=False,
        is_concurrency_safe=False,
        handler=lambda *_: ToolResult.ok_result(content="should-not-run"),
        action="tool.route",
        requires_approval=False,
        is_sensitive=False,
    )
    context = ToolExecutionContext(
        task_id="tool-task-9",
        agent_id="architect",
        backend="hermes",
        intent={},
        knowledge_bundle={},
        actor="viewer",
        session_id="session-1",
    )
    result = ToolExecutor().execute_many(context, [(tool, {"task": "review"})])[0]
    self.assertFalse(result.ok)
    self.assertEqual(result.error, "PERMISSION_DENIED")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_executor tests.control_plane.test_tool_transcript -v`
Expected: FAIL，提示 `ToolSpec` 不接受权限字段，或执行器未做权限校验。

- [ ] **Step 3: 写最小实现**

```python
@dataclass
class ToolExecutionContext:
    task_id: str
    agent_id: str
    backend: str
    cwd: Optional[str] = None
    intent: Dict[str, Any] = field(default_factory=dict)
    knowledge_bundle: Dict[str, Any] = field(default_factory=dict)
    actor: str = "admin"
    session_id: Optional[str] = None


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    is_read_only: bool
    is_concurrency_safe: bool
    handler: ToolHandler
    action: str = ""
    requires_approval: bool = False
    is_sensitive: bool = False
```

```python
def check_tool_permission(policy, actor, tool):
    action = tool.action or "tool.read.generic"
    return policy.is_allowed(actor, action)
```

```python
if not check_tool_permission(self.policy, context.actor, tool):
    result = ToolResult.error_result(error="PERMISSION_DENIED", content="")
    self._write_transcript(context, tool, payload, result, permission_outcome="denied")
    return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_executor tests.control_plane.test_tool_transcript -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_tool_executor.py tests/control_plane/test_tool_transcript.py .hermes/team/control_plane/tools/spec.py .hermes/team/control_plane/tools/executor.py .hermes/team/control_plane/tools/transcript.py .hermes/team/control_plane/governance/tool_permissions.py .hermes/team/control_plane/governance/rbac.py
git commit -m "feat: add tool permission checks"
```

### Task 3: 扩展 4 个高频工具

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\builtin.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_tool_cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_tool_executor.py`

- [ ] **Step 1: 写失败测试**

```python
def test_route_task_tool_returns_routing_reason(self):
    result = unified_cli_module.run_tool_command(
        tool_name="route_task",
        task="请 architect review 接口设计",
        actor="operator",
        config=fake_config,
    )
    self.assertTrue(result["ok"])
    self.assertEqual(result["structured_data"]["agent_id"], "architect")
    self.assertIn("routing_reason", result["structured_data"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_cli -v`
Expected: FAIL，提示 `route_task` 或其他新工具未注册。

- [ ] **Step 3: 写最小实现**

```python
def route_task_handler(_context, payload):
    router = TaskRouter()
    agent_id, task = router.route_task(str(payload["task"]), TaskPriority.NORMAL)
    return ToolResult.ok_result(
        content=f"route:{agent_id}",
        structured_data={
            "agent_id": agent_id,
            "task_id": task.id,
            "intent": task.intent,
            "routing_reason": task.routing_reason,
        },
    )
```

```python
def find_knowledge_files_handler(context, _payload):
    return ToolResult.ok_result(
        content=f"knowledge-files:{len(context.knowledge_bundle.get('paths', []))}",
        structured_data={
            "paths": context.knowledge_bundle.get("paths", []),
            "resolved_paths": context.knowledge_bundle.get("resolved_paths", []),
        },
    )
```

```python
def read_file_handler(context, payload):
    candidate = resolve_workspace_path(str(payload["path"]))
    return ToolResult.ok_result(
        content=candidate.read_text(encoding="utf-8"),
        structured_data={"path": str(payload["path"])},
        artifacts=[str(payload["path"])],
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_cli tests.control_plane.test_tool_executor -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_tool_cli.py tests/control_plane/test_tool_executor.py .hermes/team/control_plane/tools/builtin.py
git commit -m "feat: add high frequency builtin tools"
```

### Task 4: 接入 session/resume 与 CLI 查询入口

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_tool_cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\executor.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\transcript.py`

- [ ] **Step 1: 写失败测试**

```python
def test_tool_run_resume_reuses_previous_session(self):
    first = unified_cli_module.run_tool_command(
        tool_name="read_knowledge",
        task="请 architect review 接口设计",
        actor="operator",
        config=fake_config,
    )
    resumed = unified_cli_module.run_tool_command(
        tool_name="find_knowledge_files",
        task="ignored when resumed",
        actor="operator",
        config=fake_config,
        session_id=first["session_id"],
        resume=True,
    )
    self.assertEqual(resumed["session_id"], first["session_id"])
    self.assertEqual(resumed["structured_data"]["paths"][0], ".hermes/team/knowledge/status.md")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_cli -v`
Expected: FAIL，提示 `run_tool_command` 不支持 `session_id/resume` 或未持久化 session。

- [ ] **Step 3: 写最小实现**

```python
tool_run.add_argument("--session-id")
tool_run.add_argument("--resume", action="store_true")

tool_session = subparsers.add_parser("tool-session", help="查询 tool runtime session")
tool_session_sub = tool_session.add_subparsers(dest="tool_session_command")
tool_session_sub.add_parser("list", help="列出 session")
tool_get = tool_session_sub.add_parser("get", help="读取指定 session")
tool_get.add_argument("--session-id", required=True)
```

```python
if resume:
    snapshot = session_store.read_session(session_id)
    context = ToolExecutionContext(
        task_id=f"{snapshot['session_id']}-resume",
        agent_id=snapshot["agent_id"],
        backend=snapshot["backend"],
        intent=snapshot["intent"],
        knowledge_bundle=snapshot["knowledge_bundle"],
        actor=actor,
        session_id=snapshot["session_id"],
    )
else:
    context = build_tool_execution_context(...)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_cli tests.control_plane.test_tool_session_store -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_tool_cli.py .hermes/team/control_plane/cli.py .hermes/team/control_plane/tools/executor.py .hermes/team/control_plane/tools/transcript.py
git commit -m "feat: add tool session resume flow"
```

### Task 5: 回归与交付整理

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\docs\superpowers\specs\2026-05-14-control-plane-session-tools-permissions-design.md`
- Modify: `d:\KIMIK2.5\AIAgent\docs\superpowers\plans\2026-05-14-control-plane-session-tools-permissions.md`

- [ ] **Step 1: 运行新增测试**

Run: `python -m unittest tests.control_plane.test_tool_session_store tests.control_plane.test_tool_executor tests.control_plane.test_tool_transcript tests.control_plane.test_tool_cli -v`
Expected: PASS

- [ ] **Step 2: 运行关键既有测试**

Run: `python -m unittest tests.control_plane.test_executor tests.control_plane.test_adapters tests.control_plane.test_unified_cli tests.control_plane.test_persistent_bus -v`
Expected: PASS

- [ ] **Step 3: 运行诊断**

Run: 使用编辑器诊断检查新增与修改文件
Expected: 无新增导入或语法错误

- [ ] **Step 4: 自检文档**

```markdown
- spec 已覆盖 session、工具扩展、权限模型
- plan 无 TODO/TBD
- CLI 参数与测试用例一致
```

- [ ] **Step 5: 提交**

```bash
git add docs/superpowers/specs/2026-05-14-control-plane-session-tools-permissions-design.md docs/superpowers/plans/2026-05-14-control-plane-session-tools-permissions.md
git commit -m "docs: add session tools permissions plan"
```
