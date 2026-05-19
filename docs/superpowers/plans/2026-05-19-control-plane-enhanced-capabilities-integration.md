# Control Plane 增强能力融合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `aiagent_enhanced/` 中可复用的代码智能、上下文压缩、安全会话、协作与预留 OAuth 能力并入 `.hermes/team/control_plane/` 主线，在保留现有 runtime/governance/handoff 骨架的前提下真正接入可运行能力。

**Architecture:** 以 `.hermes/team/control_plane/` 为唯一主线，新增 `intelligence/`、`integrations/`、`collaboration/` 子目录，并将压缩能力挂到 `runtime/`、安全会话叠加到 `governance/`。对 `handoff/approval/audit/rbac/session` 只做增量增强，不替换现有实现；`MemoryTree` 仅接运行时压缩，不深接 `session_store` 持久化；`OAuth` 暂不接真实外部闭环，但保留稳定模块与 CLI 入口。

**Tech Stack:** Python 3, dataclasses, pathlib, sqlite3, json, unittest, unittest.mock, optional LSP/tree-sitter executables

---

## 文件结构总览

```text
.hermes/team/control_plane/
├── intelligence/
│   ├── __init__.py
│   └── code_intelligence.py              # 新增：LSP/结构化编辑/代码审查
├── integrations/
│   ├── __init__.py
│   └── oauth.py                          # 新增：OAuth 预留集成，默认本地骨架
├── collaboration/
│   ├── __init__.py
│   ├── kanban.py                         # 新增：Kanban 任务板
│   └── skill_curator.py                  # 新增：技能生命周期管理
├── runtime/
│   ├── __init__.py
│   ├── context.py                        # 修改：挂接压缩与上下文增强元数据
│   └── token_compressor.py               # 新增：Token 压缩与 MemoryTree
├── governance/
│   ├── __init__.py
│   ├── audit.py                          # 修改：支持结构化安全审计事件
│   ├── tool_permissions.py               # 修改：结合 session security 做二次判定
│   └── session_security.py               # 新增：会话安全策略与配对
├── handoff_runtime.py                    # 修改：吸收增强 handoff 字段
├── cli.py                                # 修改：新增 code-review/code-diagnostics/kanban/oauth 命令
└── tools/
    ├── builtin.py                        # 修改：注册 agent 可直接调用的增强工具
    ├── executor.py                       # 修改：接入 session security 与 transcript 压缩
    └── role_tools/                       # 如有必要补轻量包装，供角色工具面统一引用

tests/control_plane/
├── test_code_intelligence.py             # 新增
├── test_token_compressor.py              # 新增
├── test_session_security.py              # 新增
├── test_collaboration.py                 # 新增
├── test_cli_enhanced.py                  # 新增
└── 现有主线测试                           # 回归执行

仓库根目录/
└── aiagent_enhanced/                     # 最终删除，避免双轨实现
```

---

### Task 1: 建立主线目录并迁移增强模块

**Files:**
- Create: `.hermes/team/control_plane/intelligence/__init__.py`
- Create: `.hermes/team/control_plane/intelligence/code_intelligence.py`
- Create: `.hermes/team/control_plane/runtime/token_compressor.py`
- Create: `.hermes/team/control_plane/governance/session_security.py`
- Create: `.hermes/team/control_plane/integrations/__init__.py`
- Create: `.hermes/team/control_plane/integrations/oauth.py`
- Create: `.hermes/team/control_plane/collaboration/__init__.py`
- Create: `.hermes/team/control_plane/collaboration/kanban.py`
- Create: `.hermes/team/control_plane/collaboration/skill_curator.py`
- Modify: `.hermes/team/control_plane/__init__.py`
- Delete later: `aiagent_enhanced/__init__.py`, `aiagent_enhanced/code_intelligence.py`, `aiagent_enhanced/token_compressor.py`, `aiagent_enhanced/security_model.py`, `aiagent_enhanced/oauth_integrations.py`, `aiagent_enhanced/collaboration.py`
- Test: `tests/control_plane/test_code_intelligence.py`
- Test: `tests/control_plane/test_token_compressor.py`
- Test: `tests/control_plane/test_session_security.py`
- Test: `tests/control_plane/test_collaboration.py`

- [ ] **Step 1: 先写失败测试，锁定新模块导入面**

```python
import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from collaboration.kanban import KanbanBoard, TaskStatus
from collaboration.skill_curator import SkillCurator
from governance.session_security import SessionSecurityManager
from intelligence.code_intelligence import CodeReviewer
from integrations.oauth import OAuthManager
from runtime.token_compressor import MemoryTreeManager, TokenCompressor


class EnhancedModulesImportTests(unittest.TestCase):
    def test_code_reviewer_returns_security_findings(self):
        reviewer = CodeReviewer()
        result = reviewer.review("password = 'secret'\neval(user_input)")
        self.assertGreaterEqual(len(result.security_concerns), 1)

    def test_token_compressor_reduces_tool_output(self):
        compressor = TokenCompressor()
        text = "\n".join(f"line {i}" for i in range(120))
        result = compressor.compress(text, "tool")
        self.assertLess(result.comp_tokens, result.orig_tokens)

    def test_session_security_pairing_roundtrip(self):
        manager = SessionSecurityManager()
        manager.create_policy("s1", "main")
        code = manager.generate_pairing_code("s1")
        self.assertTrue(manager.verify_pairing("s1", code))

    def test_kanban_board_summary(self):
        board = KanbanBoard(":memory:")
        task = board.create_task("Integrate module")
        board.move_task(task.id, TaskStatus.IN_PROGRESS, actor="architect")
        self.assertEqual(board.get_board_summary()["in_progress"], 1)

    def test_skill_curator_register_and_use(self):
        curator = SkillCurator(storage_backend="memory")
        curator.register_skill("demo", "desc", "return True")
        used = curator.use_skill("demo")
        self.assertEqual(used["name"], "demo")

    def test_oauth_manager_has_services_but_no_live_exchange(self):
        manager = OAuthManager()
        self.assertIn("github", manager.list_services())
        self.assertEqual(manager.exchange_mode, "deferred")

    def test_memory_tree_keeps_long_term_summary(self):
        tree = MemoryTreeManager(short_term=20, medium_term=40, long_term=40)
        for index in range(10):
            tree.add({"role": "user", "content": f"message {index} " * 5})
        context = tree.get_context()
        self.assertTrue(any(item["content"].startswith("[长期记忆]") for item in context))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_code_intelligence tests.control_plane.test_token_compressor tests.control_plane.test_session_security tests.control_plane.test_collaboration -v`
Expected: FAIL，提示 `ModuleNotFoundError` 或找不到对应类。

- [ ] **Step 3: 写最小迁移实现**

```python
# .hermes/team/control_plane/integrations/oauth.py
from dataclasses import dataclass
from typing import Dict, List, Optional


OAUTH_SERVICES: Dict[str, Dict[str, object]] = {
    "github": {"name": "GitHub", "scopes": ["repo", "read:user"]},
    "slack": {"name": "Slack", "scopes": ["chat:write"]},
    "notion": {"name": "Notion", "scopes": []},
}


@dataclass
class OAuthToken:
    access_token: str
    refresh_token: Optional[str] = None


class OAuthManager:
    def __init__(self):
        self.exchange_mode = "deferred"

    def list_services(self) -> List[str]:
        return sorted(OAUTH_SERVICES.keys())
```

```python
# .hermes/team/control_plane/collaboration/kanban.py
from aiagent_enhanced.collaboration import KanbanBoard, TaskPriority, TaskStatus

__all__ = ["KanbanBoard", "TaskPriority", "TaskStatus"]
```

```python
# .hermes/team/control_plane/__init__.py
__all__ = [
    "collaboration",
    "governance",
    "intelligence",
    "integrations",
    "runtime",
]
```

- [ ] **Step 4: 再把临时桥接实现替换为主线版本**

```python
# .hermes/team/control_plane/collaboration/skill_curator.py
from dataclasses import dataclass, field
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class SkillCurator:
    def __init__(self, skills_dir: str = ".hermes/skills", storage_backend: str = "file"):
        self.storage_backend = storage_backend
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: Dict[str, Dict[str, Any]] = {}
```

```python
# .hermes/team/control_plane/governance/session_security.py
class SessionSecurityManager:
    def create_policy(self, session_id: str, session_type: str = "main"):
        ...

    def generate_pairing_code(self, session_id: str) -> str:
        ...

    def verify_pairing(self, session_id: str, code: str) -> bool:
        ...

    def check_permission(self, session_id: str, tool_name: str, payload: dict, toolset: str = "generic"):
        ...
```

- [ ] **Step 5: 运行聚焦测试确认通过**

Run: `python -m unittest tests.control_plane.test_code_intelligence tests.control_plane.test_token_compressor tests.control_plane.test_session_security tests.control_plane.test_collaboration -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add .hermes/team/control_plane/__init__.py .hermes/team/control_plane/intelligence .hermes/team/control_plane/runtime/token_compressor.py .hermes/team/control_plane/governance/session_security.py .hermes/team/control_plane/integrations .hermes/team/control_plane/collaboration tests/control_plane/test_code_intelligence.py tests/control_plane/test_token_compressor.py tests/control_plane/test_session_security.py tests/control_plane/test_collaboration.py
git commit -m "feat: migrate enhanced capabilities into control plane"
```

---

### Task 2: 把上下文压缩和会话安全接入主线执行路径

**Files:**
- Modify: `.hermes/team/control_plane/tools/spec.py`
- Modify: `.hermes/team/control_plane/runtime/context.py`
- Modify: `.hermes/team/control_plane/tools/executor.py`
- Modify: `.hermes/team/control_plane/governance/tool_permissions.py`
- Modify: `.hermes/team/control_plane/governance/audit.py`
- Test: `tests/control_plane/test_tool_executor.py`
- Test: `tests/control_plane/test_session_security.py`
- Test: `tests/control_plane/test_token_compressor.py`

- [ ] **Step 1: 写失败测试，锁定执行器接线行为**

```python
import unittest
from unittest.mock import Mock

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from governance.session_security import SessionSecurityManager
from tools.executor import ToolExecutor
from tools.spec import ToolExecutionContext, ToolResult, ToolSpec


class ToolExecutorEnhancedTests(unittest.TestCase):
    def test_denies_unpaired_sensitive_tool(self):
        tool = ToolSpec(
            name="write_file",
            description="write",
            input_schema={},
            is_read_only=False,
            is_concurrency_safe=False,
            handler=lambda _ctx, _payload: ToolResult.ok_result("ok"),
            action="tool.write.generic",
            requires_approval=True,
        )
        context = ToolExecutionContext(
            task_id="t1",
            agent_id="backend-dev",
            backend="hermes",
            actor="admin",
            session_id="s1",
        )
        executor = ToolExecutor()
        result = executor.execute_many(context, [(tool, {"file_path": "demo.txt"})])[0]
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "SESSION_SECURITY_DENIED")

    def test_compresses_transcript_preview_for_large_tool_output(self):
        transcript = Mock()
        tool = ToolSpec(
            name="search_code",
            description="search",
            input_schema={},
            is_read_only=True,
            is_concurrency_safe=True,
            handler=lambda _ctx, _payload: ToolResult.ok_result("\n".join(f"line {i}" for i in range(300))),
        )
        context = ToolExecutionContext(task_id="t2", agent_id="architect", backend="hermes", actor="admin", session_id="s2")
        executor = ToolExecutor(transcript_store=transcript)
        executor.execute_many(context, [(tool, {})])
        payload = transcript.append_record.call_args.args[0]
        self.assertIn("compressed", payload)
        self.assertLess(len(payload["content_preview"]), 200)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_executor tests.control_plane.test_session_security tests.control_plane.test_token_compressor -v`
Expected: FAIL，提示 `SESSION_SECURITY_DENIED` 不存在或 transcript 未包含压缩元数据。

- [ ] **Step 3: 扩展执行上下文与工具权限接口**

```python
# .hermes/team/control_plane/tools/spec.py
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
    compression_meta: Dict[str, Any] = field(default_factory=dict)
    security_session_type: str = "main"
```

```python
# .hermes/team/control_plane/governance/tool_permissions.py
def check_tool_permission(...):
    action = resolve_tool_action(tool, payload, context)
    is_allowed = policy.is_allowed(actor, action)
    return is_allowed, action
```

- [ ] **Step 4: 在 `runtime/context.py` 初始化压缩器与安全会话元数据**

```python
# .hermes/team/control_plane/runtime/context.py
from governance.session_security import SessionSecurityManager
from runtime.token_compressor import TokenCompressor, build_context_summary

_SESSION_SECURITY = SessionSecurityManager()


def build_tool_execution_context(...):
    ...
    session_id = f"tool-session-{int(time.time() * 1000)}"
    _SESSION_SECURITY.create_policy(session_id, "main")
    compression_meta = build_context_summary(knowledge_bundle)
    return ToolExecutionContext(
        ...,
        session_id=session_id,
        compression_meta=compression_meta,
        security_session_type="main",
    )
```

- [ ] **Step 5: 在 `tools/executor.py` 接入 session security、压缩 preview 和审计**

```python
# .hermes/team/control_plane/tools/executor.py
from governance.audit import AuditLogger
from governance.session_security import SessionSecurityManager
from runtime.token_compressor import TokenCompressor


class ToolExecutor:
    def __init__(...):
        ...
        self.session_security = SessionSecurityManager()
        self.output_compressor = TokenCompressor()
        self.audit_logger = AuditLogger(load_control_plane_config().audit_log_path)

    def _execute_one(...):
        ...
        secure_ok, secure_reason = self.session_security.check_permission(
            context.session_id or context.task_id,
            tool.name,
            payload,
            "read" if tool.is_read_only else "write",
        )
        if not secure_ok:
            result = ToolResult.error_result(error="SESSION_SECURITY_DENIED", content=secure_reason)
            self._write_transcript(context, tool, payload, result, action, "session_security_denied")
            self.audit_logger.log("tool_execution_denied", {"tool_name": tool.name, "reason": secure_reason})
            return result
        ...

    def _write_transcript(...):
        compressed = self.output_compressor.compress(result.content, "tool")
        preview = compressed.compressed[:200]
        self.transcript_store.append_record({
            ...,
            "content_preview": preview,
            "compressed": compressed.ratio > 0,
            "compression_ratio": round(compressed.ratio, 2),
        })
```

- [ ] **Step 6: 运行聚焦测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_executor tests.control_plane.test_session_security tests.control_plane.test_token_compressor -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add .hermes/team/control_plane/tools/spec.py .hermes/team/control_plane/runtime/context.py .hermes/team/control_plane/tools/executor.py .hermes/team/control_plane/governance/tool_permissions.py .hermes/team/control_plane/governance/audit.py .hermes/team/control_plane/governance/session_security.py .hermes/team/control_plane/runtime/token_compressor.py tests/control_plane/test_tool_executor.py tests/control_plane/test_session_security.py tests/control_plane/test_token_compressor.py
git commit -m "feat: wire session security and compression into tool runtime"
```

---

### Task 3: 吸收增强 handoff 字段并接入协作能力

**Files:**
- Modify: `.hermes/team/control_plane/protocols/handoff.py`
- Modify: `.hermes/team/control_plane/handoff_runtime.py`
- Create: `.hermes/team/control_plane/collaboration/kanban.py`
- Create: `.hermes/team/control_plane/collaboration/skill_curator.py`
- Test: `tests/control_plane/test_handoff.py`
- Test: `tests/control_plane/test_collaboration.py`

- [ ] **Step 1: 写失败测试，覆盖 handoff 新字段与 Kanban 能力**

```python
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from handoff_runtime import HandoffRunStore


class EnhancedHandoffTests(unittest.TestCase):
    def test_record_handoff_preserves_summary_and_risks(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = HandoffRunStore(base_dir=Path(tmp))
            saved = store.record_handoff(
                {
                    "message_id": "m1",
                    "workflow_id": "wf1",
                    "target_agent": "backend-dev",
                    "status": "pending",
                    "knowledge_summary": "summary",
                    "decisions": ["use control plane"],
                    "risks": ["missing tests"],
                    "next_steps": ["add cli"],
                }
            )
            loaded = store.read_record("m1")
        self.assertEqual(saved["knowledge_summary"], "summary")
        self.assertEqual(loaded["risks"], ["missing tests"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_handoff tests.control_plane.test_collaboration -v`
Expected: FAIL，提示新字段未保留或协作模块缺失。

- [ ] **Step 3: 扩展 handoff 协议和运行时**

```python
# .hermes/team/control_plane/protocols/handoff.py
HANDOFF_OPTIONAL_FIELDS = {
    "knowledge_summary": str,
    "deliverables": list,
    "decisions": list,
    "risks": list,
    "next_steps": list,
}
```

```python
# .hermes/team/control_plane/handoff_runtime.py
def record_handoff(self, record: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(record)
    normalized.setdefault("knowledge_summary", "")
    normalized.setdefault("deliverables", [])
    normalized.setdefault("decisions", [])
    normalized.setdefault("risks", [])
    normalized.setdefault("next_steps", [])
    message_id = normalized["message_id"]
    self._record_path(message_id).write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return normalized
```

- [ ] **Step 4: 完成主线协作模块**

```python
# .hermes/team/control_plane/collaboration/__init__.py
from collaboration.kanban import KanbanBoard, TaskPriority, TaskStatus
from collaboration.skill_curator import SkillCurator

__all__ = ["KanbanBoard", "TaskPriority", "TaskStatus", "SkillCurator"]
```

```python
# .hermes/team/control_plane/collaboration/kanban.py
class KanbanBoard:
    def create_task(self, title: str, description: str = "", assignee: str = "", ...):
        ...

    def move_task(self, task_id: str, new_status: TaskStatus, actor: str = "system") -> bool:
        ...
```

- [ ] **Step 5: 运行聚焦测试确认通过**

Run: `python -m unittest tests.control_plane.test_handoff tests.control_plane.test_collaboration -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add .hermes/team/control_plane/protocols/handoff.py .hermes/team/control_plane/handoff_runtime.py .hermes/team/control_plane/collaboration tests/control_plane/test_handoff.py tests/control_plane/test_collaboration.py
git commit -m "feat: enhance handoff payload and collaboration modules"
```

---

### Task 4: 把增强能力注册为 agent 可直接调用的工具

**Files:**
- Modify: `.hermes/team/control_plane/tools/builtin.py`
- Modify: `.hermes/team/control_plane/governance/tool_permissions.py`
- Modify: `.hermes/team/control_plane/tools/__init__.py`
- Test: `tests/control_plane/test_tool_registry.py`
- Test: `tests/control_plane/test_tool_executor.py`

- [ ] **Step 1: 写失败测试，锁定 registry 中的新工具与角色权限**

```python
import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from governance.tool_permissions import is_role_tool_allowed
from tools.builtin import build_default_tool_registry


class EnhancedToolRegistryTests(unittest.TestCase):
    def test_registry_exposes_enhanced_tools(self):
        registry = build_default_tool_registry()
        names = registry.names()
        self.assertIn("code_review", names)
        self.assertIn("code_diagnostics", names)
        self.assertIn("kanban_summary", names)
        self.assertIn("kanban_create_task", names)
        self.assertIn("list_oauth_services", names)

    def test_architect_and_backend_roles_can_use_reviewer(self):
        self.assertTrue(is_role_tool_allowed("architect", "code_review"))
        self.assertTrue(is_role_tool_allowed("backend-dev", "code_review"))

    def test_architect_can_query_kanban_summary(self):
        self.assertTrue(is_role_tool_allowed("architect", "kanban_summary"))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_registry tests.control_plane.test_tool_executor -v`
Expected: FAIL，提示 registry 中不存在增强工具或角色权限表未放通。

- [ ] **Step 3: 在 `tools/builtin.py` 注册增强工具**

```python
# .hermes/team/control_plane/tools/builtin.py
from collaboration.kanban import KanbanBoard
from governance.session_security import SessionSecurityManager
from intelligence.code_intelligence import CodeReviewer, LSPClient
from integrations.oauth import OAuthManager


def code_review_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    reviewer = CodeReviewer()
    source = str(payload.get("source") or "")
    result = reviewer.review(source)
    return ToolResult.ok_result(
        content=f"score:{result.score}",
        structured_data={
            "score": result.score,
            "issues": result.issues,
            "security_concerns": result.security_concerns,
            "suggestions": result.suggestions,
        },
    )


def list_oauth_services_handler(_context: ToolExecutionContext, _payload: Dict[str, object]) -> ToolResult:
    manager = OAuthManager()
    return ToolResult.ok_result(
        content="oauth-services",
        structured_data={"services": manager.list_services(), "exchange_mode": manager.exchange_mode},
    )
```

```python
# .hermes/team/control_plane/tools/builtin.py
ToolSpec(
    name="code_review",
    description="review code and report security/style/performance findings",
    input_schema={"source": "str"},
    is_read_only=True,
    is_concurrency_safe=True,
    handler=code_review_handler,
    action="tool.read.code_review",
),
ToolSpec(
    name="kanban_summary",
    description="read collaboration board summary",
    input_schema={},
    is_read_only=True,
    is_concurrency_safe=True,
    handler=kanban_summary_handler,
    action="tool.read.kanban",
),
```

- [ ] **Step 4: 把增强工具加入角色权限**

```python
# .hermes/team/control_plane/governance/tool_permissions.py
ROLE_TOOL_PERMISSIONS["architect"].update({"code_review", "code_diagnostics", "kanban_summary", "kanban_create_task"})
ROLE_TOOL_PERMISSIONS["backend-dev"].update({"code_review", "code_diagnostics", "kanban_summary"})
ROLE_TOOL_PERMISSIONS["requirements-analyst"].update({"kanban_summary"})
ROLE_TOOL_PERMISSIONS["qa-functional"].update({"kanban_summary", "code_review"})
```

- [ ] **Step 5: 运行聚焦测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_registry tests.control_plane.test_tool_executor -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add .hermes/team/control_plane/tools/builtin.py .hermes/team/control_plane/tools/__init__.py .hermes/team/control_plane/governance/tool_permissions.py tests/control_plane/test_tool_registry.py tests/control_plane/test_tool_executor.py
git commit -m "feat: expose enhanced capabilities as agent tools"
```

---

### Task 5: 给 CLI 增加可直接使用的增强命令

**Files:**
- Modify: `.hermes/team/control_plane/cli.py`
- Modify: `.hermes/team/control_plane/README.md`
- Test: `tests/control_plane/test_cli_enhanced.py`

- [ ] **Step 1: 写失败测试，锁定 CLI 子命令**

```python
import unittest
from io import StringIO
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

import cli


class EnhancedCliTests(unittest.TestCase):
    def test_code_review_command_prints_score(self):
        output = StringIO()
        with patch("sys.stdout", output):
            cli.main(["code-review", "--inline-code", "eval(user_input)"])
        self.assertIn("score", output.getvalue().lower())

    def test_kanban_summary_command_prints_total(self):
        output = StringIO()
        with patch("sys.stdout", output):
            cli.main(["kanban", "summary"])
        self.assertIn("total", output.getvalue().lower())

    def test_oauth_list_command_marks_deferred(self):
        output = StringIO()
        with patch("sys.stdout", output):
            cli.main(["oauth", "list"])
        self.assertIn("deferred", output.getvalue().lower())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_cli_enhanced -v`
Expected: FAIL，提示子命令不存在。

- [ ] **Step 3: 在 CLI 中注册增强命令**

```python
# .hermes/team/control_plane/cli.py
code_review_parser = subparsers.add_parser("code-review", help="审查代码片段或文件")
code_review_parser.add_argument("--file", dest="file_path")
code_review_parser.add_argument("--inline-code")

code_diag_parser = subparsers.add_parser("code-diagnostics", help="查看代码智能诊断")
code_diag_parser.add_argument("--file", required=True)
code_diag_parser.add_argument("--language", required=True)

kanban_parser = subparsers.add_parser("kanban", help="Kanban 任务板")
kanban_sub = kanban_parser.add_subparsers(dest="kanban_command", required=True)
kanban_sub.add_parser("summary", help="查看任务板摘要")

oauth_parser = subparsers.add_parser("oauth", help="OAuth 集成状态")
oauth_sub = oauth_parser.add_subparsers(dest="oauth_command", required=True)
oauth_sub.add_parser("list", help="列出可用服务")
```

```python
# .hermes/team/control_plane/cli.py
if args.command == "code-review":
    reviewer = CodeReviewer()
    source = Path(args.file_path).read_text(encoding="utf-8") if args.file_path else args.inline_code
    result = reviewer.review(source or "")
    print(json.dumps({"score": result.score, "security": result.security_concerns}, ensure_ascii=False))
    return 0
```

- [ ] **Step 4: 更新 README 的命令说明**

```markdown
- `python .hermes/team/control_plane/cli.py code-review --file path/to/file.py`：运行代码审查
- `python .hermes/team/control_plane/cli.py code-diagnostics --file path/to/file.py --language python`：查看代码诊断
- `python .hermes/team/control_plane/cli.py kanban summary`：查看协作任务摘要
- `python .hermes/team/control_plane/cli.py oauth list`：列出预留 OAuth 服务（当前为 deferred 模式）
```

- [ ] **Step 5: 运行聚焦测试确认通过**

Run: `python -m unittest tests.control_plane.test_cli_enhanced -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add .hermes/team/control_plane/cli.py .hermes/team/control_plane/README.md tests/control_plane/test_cli_enhanced.py
git commit -m "feat: expose enhanced capabilities via control plane cli"
```

---

### Task 6: 清理旧目录并完成主线回归

**Files:**
- Delete: `aiagent_enhanced/__init__.py`
- Delete: `aiagent_enhanced/code_intelligence.py`
- Delete: `aiagent_enhanced/token_compressor.py`
- Delete: `aiagent_enhanced/security_model.py`
- Delete: `aiagent_enhanced/oauth_integrations.py`
- Delete: `aiagent_enhanced/collaboration.py`
- Delete: `aiagent_enhanced/tests/test_all.py`
- Modify if needed: `AIAgent_ENHANCED_REPORT.md`
- Test: `tests/control_plane/`

- [ ] **Step 1: 写失败测试，确保主线不再依赖旧目录**

```python
import unittest
from pathlib import Path


class LegacyEnhancedPackageRemovalTests(unittest.TestCase):
    def test_legacy_package_removed_after_migration(self):
        self.assertFalse(Path("aiagent_enhanced/code_intelligence.py").exists())
        self.assertFalse(Path("aiagent_enhanced/security_model.py").exists())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_cli_enhanced tests.control_plane.test_collaboration -v`
Expected: 当前仍会通过功能测试，但 `LegacyEnhancedPackageRemovalTests` FAIL，提示旧目录仍存在。

- [ ] **Step 3: 删除旧目录并补最小文档说明**

```bash
Remove-Item -Recurse -Force aiagent_enhanced
```

```markdown
## 融合说明

- `aiagent_enhanced/` 已并入 `.hermes/team/control_plane/`
- 代码智能：`intelligence/`
- 上下文压缩：`runtime/token_compressor.py`
- 会话安全：`governance/session_security.py`
- 协作能力：`collaboration/`
- OAuth：`integrations/oauth.py`，当前为 deferred 预留态
```

- [ ] **Step 4: 跑主线回归与静态检查**

Run: `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`
Expected: PASS

Run: `python -m ruff check .hermes/team/control_plane tests/control_plane`
Expected: `All checks passed!`

- [ ] **Step 5: 用诊断检查刚改过的关键文件**

Run diagnostics for:
- `.hermes/team/control_plane/cli.py`
- `.hermes/team/control_plane/tools/executor.py`
- `.hermes/team/control_plane/runtime/token_compressor.py`
- `.hermes/team/control_plane/governance/session_security.py`

Expected: 无新增错误；若有 warning，只保留可接受的可选依赖提示。

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "refactor: fold enhanced package into control plane mainline"
```

---

## 自检结果

- 覆盖需求：
  - 目录融合：Task 1, Task 5
  - 主链接线：Task 2, Task 3, Task 4, Task 5
  - agent 可直接使用增强能力：Task 4
  - OAuth 暂不接真实闭环但保留：Task 1, Task 4, Task 5, Task 6
  - MemoryTree 不深接 `session_store`：Task 2 的 `runtime/context.py` 只接运行时压缩元数据
  - 可运行与回归：Task 6
- 占位符扫描：未使用 `TODO/TBD/implement later`
- 类型一致性：
  - `SessionSecurityManager`
  - `TokenCompressor`
  - `MemoryTreeManager`
  - `KanbanBoard`
  - `SkillCurator`
  - `OAuthManager`
  - `CodeReviewer`
