# Control Plane Tool Runtime MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为仓库级控制平面新增最小工具运行时、transcript 与可运行 CLI 闭环。

**Architecture:** 在现有 `control_plane` 之上新增独立 `tools/` 与 `runtime/` 模块，保留现有 batch executor 与 backend adapter，不替换既有入口。CLI 新增 `tool-run` 子命令，通过 `TaskRouter` 装配上下文、调用 `ToolExecutor` 执行默认工具并写 transcript。

**Tech Stack:** Python 3、argparse、dataclasses、pathlib、json、threading、unittest

---

### Task 1: 建立 ToolExecutor 的红绿闭环

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_tool_executor.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\spec.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\executor.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\__init__.py`

- [ ] **Step 1: 写失败测试**

```python
import threading
import time
import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.executor import ToolExecutor
from tools.spec import ToolExecutionContext, ToolResult, ToolSpec


class ToolExecutorTests(unittest.TestCase):
    def test_execute_many_keeps_request_order(self):
        order = []

        def slow(_context, payload):
            time.sleep(payload["delay"])
            order.append(payload["name"])
            return ToolResult.ok_result(content=payload["name"])

        executor = ToolExecutor()
        context = ToolExecutionContext(task_id="task-1", agent_id="architect", backend="hermes")
        tools = {
            "alpha": ToolSpec("alpha", "alpha", {}, True, True, slow),
            "beta": ToolSpec("beta", "beta", {}, True, True, slow),
        }

        results = executor.execute_many(
            context,
            [
                (tools["alpha"], {"name": "alpha", "delay": 0.02}),
                (tools["beta"], {"name": "beta", "delay": 0.0}),
            ],
        )

        self.assertEqual([item.content for item in results], ["alpha", "beta"])
        self.assertEqual(sorted(order), ["alpha", "beta"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_executor -v`
Expected: FAIL，提示 `tools.executor` 或 `ToolExecutor` 不存在。

- [ ] **Step 3: 写最小实现**

```python
from dataclasses import dataclass, field


@dataclass
class ToolExecutionContext:
    task_id: str
    agent_id: str
    backend: str
    cwd: str | None = None
    intent: dict = field(default_factory=dict)
    knowledge_bundle: dict = field(default_factory=dict)


@dataclass
class ToolResult:
    ok: bool
    content: str = ""
    structured_data: dict | None = None
    error: str | None = None
    artifacts: list | None = None

    @classmethod
    def ok_result(cls, content="", structured_data=None, artifacts=None):
        return cls(True, content, structured_data, None, artifacts or [])
```

```python
from concurrent.futures import ThreadPoolExecutor


class ToolExecutor:
    def execute_many(self, context, requests):
        results = [None] * len(requests)
        parallel = []
        serial = []
        for index, (tool, payload) in enumerate(requests):
            if tool.is_read_only and tool.is_concurrency_safe:
                parallel.append((index, tool, payload))
            else:
                serial.append((index, tool, payload))
        with ThreadPoolExecutor(max_workers=max(1, len(parallel))) as pool:
            futures = {
                pool.submit(tool.handler, context, payload): index
                for index, tool, payload in parallel
            }
            for future, index in futures.items():
                results[index] = future.result()
        for index, tool, payload in serial:
            results[index] = tool.handler(context, payload)
        return results
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_executor -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_tool_executor.py .hermes/team/control_plane/tools/spec.py .hermes/team/control_plane/tools/executor.py .hermes/team/control_plane/tools/__init__.py
git commit -m "feat: add tool executor mvp"
```

### Task 2: 增加 transcript 落盘

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_tool_transcript.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\transcript.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\executor.py`

- [ ] **Step 1: 写失败测试**

```python
import json
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.executor import ToolExecutor
from tools.spec import ToolExecutionContext, ToolResult, ToolSpec
from tools.transcript import ToolTranscriptStore


class ToolTranscriptTests(unittest.TestCase):
    def test_execute_many_writes_transcript_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcript = ToolTranscriptStore(Path(tmp) / "tool.jsonl")

            def handler(_context, payload):
                return ToolResult.ok_result(content=payload["task"])

            tool = ToolSpec("dispatch_task", "dispatch", {}, False, False, handler)
            executor = ToolExecutor(transcript_store=transcript)
            context = ToolExecutionContext(task_id="task-1", agent_id="architect", backend="hermes")

            executor.execute_many(context, [(tool, {"task": "demo"})])

            rows = [json.loads(line) for line in transcript.path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["tool_name"], "dispatch_task")
            self.assertEqual(rows[0]["task_id"], "task-1")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_transcript -v`
Expected: FAIL，提示 transcript store 不存在或未写日志。

- [ ] **Step 3: 写最小实现**

```python
import json
import time
from pathlib import Path


class ToolTranscriptStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_record(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
```

```python
record = {
    "task_id": context.task_id,
    "tool_name": tool.name,
    "agent_id": context.agent_id,
    "backend": context.backend,
    "input": payload,
    "ok": result.ok,
    "error": result.error,
    "content_preview": result.content[:200],
    "artifacts": result.artifacts or [],
    "knowledge_paths": context.knowledge_bundle.get("paths", []),
    "timestamp": time.time(),
}
self.transcript_store.append_record(record)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_transcript -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_tool_transcript.py .hermes/team/control_plane/tools/transcript.py .hermes/team/control_plane/tools/executor.py
git commit -m "feat: add tool transcript store"
```

### Task 3: 增加 registry、runtime context 与最小工具集

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\registry.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\tools\builtin.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\runtime\context.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\runtime\rules.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\runtime\__init__.py`

- [ ] **Step 1: 写失败测试**

```python
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.control_plane.test_support import ensure_control_plane_path, load_framework_module

ensure_control_plane_path()
from runtime.context import build_tool_execution_context

task_router_module = load_framework_module("task_router")


class RuntimeContextTests(unittest.TestCase):
    def test_build_context_uses_router_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            router = task_router_module.TaskRouter()
            router.config.directories = {"state_dir": str(Path(tmp) / "state")}
            context = build_tool_execution_context(router, "请 architect review 接口设计")
            self.assertEqual(context.agent_id, "architect")
            self.assertIn("paths", context.knowledge_bundle)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_executor tests.control_plane.test_tool_transcript -v`
Expected: FAIL，提示 runtime context 或 registry 缺失。

- [ ] **Step 3: 写最小实现**

```python
from pathlib import Path

from tools.spec import ToolExecutionContext


def build_knowledge_bundle(recommendation):
    ordered = []
    for group in ("team", "role", "instance"):
        for item in recommendation.get(group, []):
            if Path(item).exists():
                ordered.append(item)
    return {"paths": ordered}
```

```python
def build_tool_execution_context(router, task, requested_agent=None, backend_override=None):
    intent = router.analyze_task_intent(task)
    agent_id, routing_reason = router.select_best_agent(intent, task_router_module.TaskPriority.NORMAL)
    knowledge = router._build_knowledge_recommendation(intent, requested_agent or agent_id)
    backend = backend_override or router._build_backend_recommendation(intent)["selected_backend"]
    return ToolExecutionContext(
        task_id=f"tool-{abs(hash(task))}",
        agent_id=requested_agent or agent_id,
        backend=backend,
        intent={"task_type": intent.task_type.value, "collaboration_mode": intent.collaboration_mode},
        knowledge_bundle=build_knowledge_bundle(knowledge),
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_executor tests.control_plane.test_tool_transcript -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/tools/registry.py .hermes/team/control_plane/tools/builtin.py .hermes/team/control_plane/runtime/context.py .hermes/team/control_plane/runtime/rules.py .hermes/team/control_plane/runtime/__init__.py
git commit -m "feat: add tool registry and runtime context"
```

### Task 4: 新增 CLI `tool-run` 入口

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_tool_cli.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\cli.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import cli as unified_cli_module


class ToolCLITests(unittest.TestCase):
    def test_tool_run_executes_registered_tool(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl", "state_dir": "state"},
        )
        fake_audit = SimpleNamespace(log=lambda *args: None)
        fake_result = {"ok": True, "content": "done"}

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=SimpleNamespace(is_allowed=lambda *_: True)):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(unified_cli_module, "run_tool_command", return_value=fake_result):
                            result = unified_cli_module.main(["tool-run", "read_knowledge", "查看知识包"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["content"], "done")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_tool_cli -v`
Expected: FAIL，提示 `tool-run` 或 `run_tool_command` 不存在。

- [ ] **Step 3: 写最小实现**

```python
tool_run = subparsers.add_parser("tool-run", help="运行最小工具运行时")
tool_run.add_argument("tool")
tool_run.add_argument("task")
tool_run.add_argument("--agent")
tool_run.add_argument("--backend")
tool_run.add_argument("--actor", default="admin")
```

```python
if args.command == "tool-run":
    result = run_tool_command(
        tool_name=args.tool,
        task=args.task,
        requested_agent=args.agent,
        backend_override=args.backend,
        config=config,
    )
    audit.log("tool-run", {"tool": args.tool, "actor": args.actor})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_tool_cli -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_tool_cli.py .hermes/team/control_plane/cli.py
git commit -m "feat: add tool runtime cli entry"
```

### Task 5: 运行回归与整理交付

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\docs\superpowers\specs\2026-05-14-control-plane-tool-runtime-mvp-design.md`
- Modify: `d:\KIMIK2.5\AIAgent\docs\superpowers\plans\2026-05-14-control-plane-tool-runtime-mvp.md`

- [ ] **Step 1: 运行新增测试**

Run: `python -m unittest tests.control_plane.test_tool_executor tests.control_plane.test_tool_transcript tests.control_plane.test_tool_cli -v`
Expected: PASS

- [ ] **Step 2: 运行关键既有测试**

Run: `python -m unittest tests.control_plane.test_executor tests.control_plane.test_adapters tests.control_plane.test_unified_cli -v`
Expected: PASS

- [ ] **Step 3: 运行诊断**

Run: 使用编辑器诊断检查新增与修改文件
Expected: 无新增语法或导入错误

- [ ] **Step 4: 自检文档**

```markdown
- spec 与实现一致
- plan 无 TBD/TODO
- 文件路径与命名已落地
```

- [ ] **Step 5: 提交**

```bash
git add docs/superpowers/specs/2026-05-14-control-plane-tool-runtime-mvp-design.md docs/superpowers/plans/2026-05-14-control-plane-tool-runtime-mvp.md
git commit -m "docs: add tool runtime mvp spec and plan"
```


## 当前实现状态（2026-05-14）

- `ToolExecutor`、`ToolExecutionContext`、builtin tools、runtime context 与 transcript 已全部落地。
- 在 MVP 基础上，tool runtime 进一步接入了 knowledge bundle 预加载：执行前会把已解析的知识文件内容装入 `context.knowledge_bundle['items']`。
- `read_knowledge` 已支持优先消费预加载结果，避免重复读盘。
- 统一 CLI 不仅支持 `tool-run`，也已经把知识包展示与 query 侧摘要能力接入 `dispatch`、`workflow`、`query workflow`、`query handoff`。
- workflow runtime snapshot 现已记录 `knowledge_recommendations`、`knowledge_bundles` 与 `knowledge_feedback`，使 tool runtime MVP 与 workflow 主线对齐。
- 本计划原始目标已完成，且实现范围已自然延伸到知识链路消费与摘要视图，后续变化以 session/permissions 文档和知识库 enrichment 文档为主同步。
