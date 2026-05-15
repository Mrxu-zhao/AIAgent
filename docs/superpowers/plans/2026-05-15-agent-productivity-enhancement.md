# Agent 实际干活能力增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 9 个角色 Agent 新增专用工具（~30 个）和标准工作流（~27 个），让 Agent 能实际执行代码生成、文件写入、测试运行等操作。

**Architecture:** 在现有 control_plane tool runtime 基础上，新增 `common_tools.py`（通用工具）、`role_tools/`（角色专用工具包）、`workflows/`（标准工作流定义），通过 `ToolRegistry` 统一注册，CLI 直接消费。

**Tech Stack:** Python 3, dataclasses, pathlib, json, yaml, unittest

---

## 文件结构总览

```
.hermes/team/control_plane/
├── tools/
│   ├── builtin.py                 # 现有 8 个工具（不变）
│   ├── common_tools.py            # 新增：通用工具
│   ├── role_tools/                # 新增：角色专用工具包
│   │   ├── __init__.py
│   │   ├── backend_tools.py       # backend-dev 4 个工具
│   │   ├── frontend_tools.py      # frontend-dev 3 个工具
│   │   ├── architect_tools.py     # architect 2 个工具
│   │   ├── dba_tools.py           # dba 2 个工具
│   │   ├── qa_tools.py            # qa 2 个工具
│   │   ├── devops_tools.py        # devops 2 个工具
│   │   ├── ucd_tools.py           # ucd 1 个工具
│   │   └── requirements_tools.py  # requirements 1 个工具
│   └── registry.py                # 修改：注册所有新工具
├── workflows/                     # 新增：标准工作流定义
│   ├── __init__.py
│   ├── loader.py                  # 工作流加载器
│   ├── backend-api-development.yaml
│   ├── frontend-page-development.yaml
│   ├── architect-design-review.yaml
│   ├── dba-table-design.yaml
│   ├── qa-test-case-design.yaml
│   ├── devops-deployment.yaml
│   ├── ucd-interaction-design.yaml
│   └── requirements-analysis.yaml
├── governance/
│   └── tool_permissions.py        # 修改：新增角色工具权限
└── cli.py                         # 修改：注册新工具和工作流命令

tests/control_plane/
├── test_common_tools.py           # 新增：通用工具测试
├── test_role_tools/               # 新增：角色工具测试
│   ├── __init__.py
│   ├── test_backend_tools.py
│   ├── test_frontend_tools.py
│   ├── test_architect_tools.py
│   ├── test_dba_tools.py
│   ├── test_qa_tools.py
│   ├── test_devops_tools.py
│   ├── test_ucd_tools.py
│   └── test_requirements_tools.py
└── test_workflows.py              # 新增：工作流测试
```

---

## Task 1: 通用工具 — write_file

**Files:**
- Create: `.hermes/team/control_plane/tools/common_tools.py`
- Create: `tests/control_plane/test_common_tools.py`

- [ ] **Step 1: 写失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.common_tools import write_file_handler, search_code_handler
from tools.spec import ToolExecutionContext


class CommonToolsTests(unittest.TestCase):
    def test_write_file_creates_file_with_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = ToolExecutionContext(
                task_id="test-1", agent_id="backend-dev", backend="hermes", cwd=str(root)
            )
            result = write_file_handler(
                context,
                {
                    "path": "src/main/java/com/example/Test.java",
                    "content": "public class Test {}",
                },
            )
            self.assertTrue(result.ok)
            written = root / "src" / "main" / "java" / "com" / "example" / "Test.java"
            self.assertTrue(written.exists())
            self.assertEqual(written.read_text(encoding="utf-8"), "public class Test {}")

    def test_write_file_rejects_path_outside_repo(self):
        context = ToolExecutionContext(task_id="test-2", agent_id="backend-dev", backend="hermes")
        result = write_file_handler(
            context,
            {"path": "../../../etc/passwd", "content": "hack"},
        )
        self.assertFalse(result.ok)
        self.assertIn("outside", result.error.lower())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_common_tools -v`
Expected: FAIL，提示 `tools.common_tools` 不存在。

- [ ] **Step 3: 写最小实现**

```python
from __future__ import annotations

from pathlib import Path
from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def _resolve_safe_path(context: ToolExecutionContext, raw_path: str) -> Path:
    root = Path(context.cwd).resolve() if context.cwd else Path.cwd().resolve()
    target = (root / raw_path).resolve()
    if root not in target.parents and target != root:
        raise ValueError(f"path must stay within repository root: {raw_path}")
    forbidden = {".git", "node_modules", ".venv", "__pycache__", ".hermes-sandbox"}
    for part in target.relative_to(root).parts:
        if part in forbidden:
            raise ValueError(f"writing to forbidden directory: {part}")
    return target


def write_file_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    try:
        target = _resolve_safe_path(context, str(payload["path"]))
        content = str(payload["content"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult.ok_result(
            content=f"written:{target}",
            structured_data={"path": str(payload["path"]), "bytes": len(content.encode("utf-8"))},
            artifacts=[str(payload["path"])],
        )
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_common_tools.CommonToolsTests.test_write_file_creates_file_with_content tests.control_plane.test_common_tools.CommonToolsTests.test_write_file_rejects_path_outside_repo -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_common_tools.py .hermes/team/control_plane/tools/common_tools.py
git commit -m "feat: add write_file common tool"
```

---

## Task 2: 通用工具 — search_code

**Files:**
- Modify: `.hermes/team/control_plane/tools/common_tools.py`
- Modify: `tests/control_plane/test_common_tools.py`

- [ ] **Step 1: 写失败测试**

```python
    def test_search_code_finds_matching_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "UserService.java").write_text("public class UserService {}", encoding="utf-8")
            (root / "src" / "OrderService.java").write_text("public class OrderService {}", encoding="utf-8")
            context = ToolExecutionContext(
                task_id="test-3", agent_id="backend-dev", backend="hermes", cwd=str(root)
            )
            result = search_code_handler(context, {"pattern": "UserService", "glob": "*.java"})
            self.assertTrue(result.ok)
            self.assertEqual(len(result.structured_data["matches"]), 1)
            self.assertIn("UserService.java", result.structured_data["matches"][0]["path"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_common_tools.CommonToolsTests.test_search_code_finds_matching_files -v`
Expected: FAIL，提示 `search_code_handler` 不存在。

- [ ] **Step 3: 写最小实现**

```python
import fnmatch


def search_code_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    try:
        root = Path(context.cwd).resolve() if context.cwd else Path.cwd().resolve()
        pattern = str(payload.get("pattern", ""))
        glob = str(payload.get("glob", "*"))
        max_results = int(payload.get("max_results", 50))
        matches = []
        for path in root.rglob(glob):
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue
            lines = content.splitlines()
            for lineno, line in enumerate(lines, start=1):
                if pattern in line:
                    matches.append({
                        "path": str(path.relative_to(root)),
                        "lineno": lineno,
                        "line": line.strip(),
                    })
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break
        return ToolResult.ok_result(
            content=f"found:{len(matches)}",
            structured_data={"matches": matches, "total": len(matches)},
            artifacts=[m["path"] for m in matches],
        )
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_common_tools.CommonToolsTests.test_search_code_finds_matching_files -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_common_tools.py .hermes/team/control_plane/tools/common_tools.py
git commit -m "feat: add search_code common tool"
```

---

## Task 3: 通用工具 — run_command（安全白名单）

**Files:**
- Modify: `.hermes/team/control_plane/tools/common_tools.py`
- Modify: `tests/control_plane/test_common_tools.py`

- [ ] **Step 1: 写失败测试**

```python
    def test_run_command_allows_whitelisted_command(self):
        context = ToolExecutionContext(task_id="test-4", agent_id="backend-dev", backend="hermes")
        result = run_command_handler(context, {"command": "echo hello"})
        self.assertTrue(result.ok)
        self.assertIn("hello", result.content)

    def test_run_command_rejects_dangerous_command(self):
        context = ToolExecutionContext(task_id="test-5", agent_id="backend-dev", backend="hermes")
        result = run_command_handler(context, {"command": "rm -rf /"})
        self.assertFalse(result.ok)
        self.assertIn("not allowed", result.error.lower())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_common_tools.CommonToolsTests.test_run_command_allows_whitelisted_command tests.control_plane.test_common_tools.CommonToolsTests.test_run_command_rejects_dangerous_command -v`
Expected: FAIL，提示 `run_command_handler` 不存在。

- [ ] **Step 3: 写最小实现**

```python
import subprocess

ALLOWED_COMMAND_PATTERNS = {
    "echo", "python", "python3", "pytest", "mvn", "npm", "node",
    "git status", "git diff", "git log", "java", "javac",
}
FORBIDDEN_PATTERNS = {"rm -rf /", "> /dev/null", "curl .*\\|", "wget .*\\|", "sudo"}


def _is_command_allowed(command: str) -> bool:
    cmd_lower = command.lower().strip()
    for forbidden in FORBIDDEN_PATTERNS:
        import re
        if re.search(forbidden, cmd_lower):
            return False
    first_word = cmd_lower.split()[0] if cmd_lower else ""
    return first_word in ALLOWED_COMMAND_PATTERNS


def run_command_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    command = str(payload.get("command", "")).strip()
    if not command:
        return ToolResult.error_result(error="empty command")
    if not _is_command_allowed(command):
        return ToolResult.error_result(error=f"command not allowed: {command}")
    try:
        cwd = context.cwd if context.cwd else None
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=int(payload.get("timeout", 60)),
        )
        return ToolResult.ok_result(
            content=result.stdout or "(no output)",
            structured_data={
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            artifacts=[],
        )
    except subprocess.TimeoutExpired:
        return ToolResult.error_result(error="command timeout")
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_common_tools.CommonToolsTests.test_run_command_allows_whitelisted_command tests.control_plane.test_common_tools.CommonToolsTests.test_run_command_rejects_dangerous_command -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_common_tools.py .hermes/team/control_plane/tools/common_tools.py
git commit -m "feat: add run_command common tool with whitelist"
```

---

## Task 4: 通用工具 — generate_code（模板引擎）

**Files:**
- Modify: `.hermes/team/control_plane/tools/common_tools.py`
- Modify: `tests/control_plane/test_common_tools.py`

- [ ] **Step 1: 写失败测试**

```python
    def test_generate_code_from_template(self):
        context = ToolExecutionContext(task_id="test-6", agent_id="backend-dev", backend="hermes")
        result = generate_code_handler(
            context,
            {
                "template": "spring_controller",
                "variables": {
                    "class_name": "UserController",
                    "package": "com.example.controller",
                    "endpoint": "/api/users",
                },
            },
        )
        self.assertTrue(result.ok)
        self.assertIn("UserController", result.content)
        self.assertIn("@RestController", result.content)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_common_tools.CommonToolsTests.test_generate_code_from_template -v`
Expected: FAIL，提示 `generate_code_handler` 不存在。

- [ ] **Step 3: 写最小实现**

```python
from string import Template

CODE_TEMPLATES = {
    "spring_controller": '''package ${package};

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("${endpoint}")
public class ${class_name} {

    @GetMapping
    public List<${entity_name}> list() {
        // TODO: implement
        return null;
    }

    @PostMapping
    public ${entity_name} create(@RequestBody ${entity_name} entity) {
        // TODO: implement
        return null;
    }
}
''',
    "vue_component": '''<template>
  <div class="${component_name}-container">
    <!-- TODO: implement -->
  </div>
</template>

<script setup lang="ts">
// TODO: implement
</script>

<style scoped>
.${component_name}-container {
  /* TODO: implement */
}
</style>
''',
}


def generate_code_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    template_name = str(payload.get("template", ""))
    variables = dict(payload.get("variables") or {})
    template_str = CODE_TEMPLATES.get(template_name)
    if not template_str:
        available = ", ".join(CODE_TEMPLATES.keys())
        return ToolResult.error_result(error=f"unknown template '{template_name}'. Available: {available}")
    try:
        t = Template(template_str)
        code = t.safe_substitute(variables)
        return ToolResult.ok_result(
            content=code,
            structured_data={"template": template_name, "variables": variables},
            artifacts=[],
        )
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_common_tools.CommonToolsTests.test_generate_code_from_template -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_common_tools.py .hermes/team/control_plane/tools/common_tools.py
git commit -m "feat: add generate_code template engine"
```

---

## Task 5: 注册通用工具到 Registry

**Files:**
- Modify: `.hermes/team/control_plane/tools/registry.py`
- Modify: `tests/control_plane/test_tool_executor.py`（验证通用工具执行）

- [ ] **Step 1: 读取现有 registry.py**

Read: `.hermes/team/control_plane/tools/registry.py`

- [ ] **Step 2: 修改 registry 注册通用工具**

```python
from tools.common_tools import (
    generate_code_handler,
    run_command_handler,
    search_code_handler,
    write_file_handler,
)

# 在 build_default_tool_registry 或类似函数中添加：
ToolSpec(
    name="write_file",
    description="write or update a file within the repository",
    input_schema={"path": "str", "content": "str"},
    is_read_only=False,
    is_concurrency_safe=False,
    handler=write_file_handler,
    action="tool.write.file",
),
ToolSpec(
    name="search_code",
    description="search code in the repository",
    input_schema={"pattern": "str", "glob": "str"},
    is_read_only=True,
    is_concurrency_safe=True,
    handler=search_code_handler,
    action="tool.read.search",
),
ToolSpec(
    name="run_command",
    description="run a whitelisted shell command",
    input_schema={"command": "str", "timeout": "int"},
    is_read_only=False,
    is_concurrency_safe=False,
    handler=run_command_handler,
    action="tool.execute.command",
),
ToolSpec(
    name="generate_code",
    description="generate code from a template",
    input_schema={"template": "str", "variables": "dict"},
    is_read_only=False,
    is_concurrency_safe=False,
    handler=generate_code_handler,
    action="tool.generate.code",
),
```

- [ ] **Step 3: 运行既有测试确认无回归**

Run: `python -m unittest tests.control_plane.test_tool_executor -v`
Expected: PASS（原有测试不受影响）

- [ ] **Step 4: 提交**

```bash
git add .hermes/team/control_plane/tools/registry.py
git commit -m "feat: register common tools in registry"
```

---

## Task 6: backend-dev 专用工具

**Files:**
- Create: `.hermes/team/control_plane/tools/role_tools/__init__.py`
- Create: `.hermes/team/control_plane/tools/role_tools/backend_tools.py`
- Create: `tests/control_plane/test_role_tools/__init__.py`
- Create: `tests/control_plane/test_role_tools/test_backend_tools.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest
from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.role_tools.backend_tools import generate_controller_handler
from tools.spec import ToolExecutionContext


class BackendToolsTests(unittest.TestCase):
    def test_generate_controller_creates_spring_controller(self):
        context = ToolExecutionContext(task_id="bt-1", agent_id="backend-dev", backend="hermes")
        result = generate_controller_handler(
            context,
            {
                "class_name": "UserController",
                "package": "com.example.controller",
                "endpoint": "/api/users",
                "entity_name": "User",
            },
        )
        self.assertTrue(result.ok)
        self.assertIn("@RestController", result.content)
        self.assertIn("UserController", result.content)
        self.assertIn("/api/users", result.content)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_role_tools.test_backend_tools -v`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 写最小实现**

```python
from __future__ import annotations

from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def generate_controller_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    class_name = str(payload.get("class_name", "ExampleController"))
    package = str(payload.get("package", "com.example.controller"))
    endpoint = str(payload.get("endpoint", "/api/example"))
    entity_name = str(payload.get("entity_name", "Example"))
    code = f'''package {package};

import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("{endpoint}")
public class {class_name} {{

    @GetMapping
    public List<{entity_name}> list() {{
        // TODO: implement list
        return null;
    }}

    @GetMapping("/{{id}}")
    public {entity_name} getById(@PathVariable Long id) {{
        // TODO: implement getById
        return null;
    }}

    @PostMapping
    public {entity_name} create(@RequestBody {entity_name} entity) {{
        // TODO: implement create
        return null;
    }}

    @PutMapping("/{{id}}")
    public {entity_name} update(@PathVariable Long id, @RequestBody {entity_name} entity) {{
        // TODO: implement update
        return null;
    }}

    @DeleteMapping("/{{id}}")
    public void delete(@PathVariable Long id) {{
        // TODO: implement delete
    }}
}}
'''
    return ToolResult.ok_result(
        content=code,
        structured_data={"class_name": class_name, "package": package, "endpoint": endpoint},
        artifacts=[],
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_tools.test_backend_tools.BackendToolsTests.test_generate_controller_creates_spring_controller -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/control_plane/test_role_tools/ .hermes/team/control_plane/tools/role_tools/backend_tools.py
git commit -m "feat: add backend-dev role tools"
```

---

## Task 7: frontend-dev 专用工具

**Files:**
- Create: `.hermes/team/control_plane/tools/role_tools/frontend_tools.py`
- Create: `tests/control_plane/test_role_tools/test_frontend_tools.py`

参照 Task 6 模式，实现：
- `generate_vue_component_handler`
- `generate_api_client_handler`
- `run_linter_handler`

- [ ] **Step 1-5:** 参照 Task 6 的红绿闭环流程

```bash
git add tests/control_plane/test_role_tools/test_frontend_tools.py .hermes/team/control_plane/tools/role_tools/frontend_tools.py
git commit -m "feat: add frontend-dev role tools"
```

---

## Task 8: 其他角色专用工具

**Files:**
- Create: `.hermes/team/control_plane/tools/role_tools/{architect,dba,qa,devops,ucd,requirements}_tools.py`
- Create: `tests/control_plane/test_role_tools/test_{architect,dba,qa,devops,ucd,requirements}_tools.py`

每个角色实现 1-2 个核心工具：

| 角色 | 工具 1 | 工具 2 |
|---|---|---|
| architect | generate_architecture_doc | review_api_design |
| dba | generate_ddl | analyze_slow_query |
| qa-functional | generate_test_cases | run_api_tests |
| qa-performance | generate_jmeter_script | analyze_performance_report |
| devops | generate_dockerfile | generate_k8s_manifests |
| ucd | generate_design_spec | — |
| requirements | generate_prd | — |

- [ ] **Step 1-5:** 每个角色参照 Task 6 的红绿闭环流程

```bash
git add tests/control_plane/test_role_tools/ .hermes/team/control_plane/tools/role_tools/
git commit -m "feat: add all remaining role-specific tools"
```

---

## Task 9: 注册所有角色工具到 Registry

**Files:**
- Modify: `.hermes/team/control_plane/tools/registry.py`

- [ ] **Step 1: 修改 registry 导入并注册所有角色工具**

```python
from tools.role_tools.backend_tools import generate_controller_handler
from tools.role_tools.frontend_tools import generate_vue_component_handler
# ... 其他导入

# 在 build_default_tool_registry 中添加所有角色 ToolSpec
```

- [ ] **Step 2: 运行既有测试确认无回归**

Run: `python -m unittest tests.control_plane.test_tool_executor -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add .hermes/team/control_plane/tools/registry.py
git commit -m "feat: register all role-specific tools"
```

---

## Task 10: 工作流定义与加载器

**Files:**
- Create: `.hermes/team/control_plane/workflows/__init__.py`
- Create: `.hermes/team/control_plane/workflows/loader.py`
- Create: `.hermes/team/control_plane/workflows/backend-api-development.yaml`
- Create: `tests/control_plane/test_workflows.py`

- [ ] **Step 1: 写失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from workflows.loader import WorkflowLoader


class WorkflowLoaderTests(unittest.TestCase):
    def test_load_backend_api_workflow(self):
        loader = WorkflowLoader()
        workflow = loader.load("backend-api-development")
        self.assertEqual(workflow["role"], "backend-dev")
        self.assertTrue(len(workflow["steps"]) > 0)
        self.assertEqual(workflow["steps"][0]["step_id"], "read_requirement")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_workflows -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def _workflows_dir() -> Path:
    return Path(__file__).resolve().parent


class WorkflowLoader:
    def load(self, workflow_id: str) -> Dict[str, Any]:
        path = _workflows_dir() / f"{workflow_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"workflow not found: {workflow_id}")
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def list_workflows(self) -> Dict[str, str]:
        result = {}
        for path in sorted(_workflows_dir().glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            result[data["workflow_id"]] = data.get("name", path.stem)
        return result
```

- [ ] **Step 4: 创建第一个工作流定义**

```yaml
# .hermes/team/control_plane/workflows/backend-api-development.yaml
workflow_id: backend-api-development
name: 后端 API 开发工作流
description: 从接口设计到测试通过的完整流程
role: backend-dev
steps:
  - step_id: read_requirement
    name: 读取需求
    tool: read_knowledge
    input:
      paths: ["requirements/{feature}.md"]

  - step_id: generate_controller
    name: 生成 Controller
    tool: generate_controller
    input:
      class_name: "{Feature}Controller"
      package: "com.example.controller"
      endpoint: "/api/{feature}"
      entity_name: "{Feature}"

  - step_id: write_controller
    name: 写入 Controller 文件
    tool: write_file
    input:
      path: "src/main/java/com/example/controller/{Feature}Controller.java"
      content: "${generate_controller.output}"

  - step_id: handoff
    name: 交接给测试
    tool: dispatch_task
    input:
      agent_id: "qa-functional"
      task: "请测试 {feature} 接口"
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_workflows.WorkflowLoaderTests.test_load_backend_api_workflow -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add tests/control_plane/test_workflows.py .hermes/team/control_plane/workflows/
git commit -m "feat: add workflow loader and backend-api-development workflow"
```

---

## Task 11: 定义所有角色工作流

**Files:**
- Create: `.hermes/team/control_plane/workflows/{frontend-page,architect-design,dba-table,qa-test-case,devops-deployment,ucd-interaction,requirements-analysis}.yaml`

- [ ] **Step 1: 为每个角色创建 1 个核心工作流**

参照 `backend-api-development.yaml` 格式，为以下角色创建工作流：
- `frontend-page-development.yaml` — 前端页面开发
- `architect-design-review.yaml` — 架构设计评审
- `dba-table-design.yaml` — 数据库表设计
- `qa-test-case-design.yaml` — 测试用例设计
- `devops-deployment.yaml` — 部署配置
- `ucd-interaction-design.yaml` — 交互设计
- `requirements-analysis.yaml` — 需求分析

- [ ] **Step 2: 运行工作流加载测试**

Run: `python -m unittest tests.control_plane.test_workflows -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add .hermes/team/control_plane/workflows/
git commit -m "feat: add all role standard workflows"
```

---

## Task 12: CLI 集成

**Files:**
- Modify: `.hermes/team/control_plane/cli.py`

- [ ] **Step 1: 在 CLI 中新增工作流命令**

```python
# 在 cli.py 的 subparsers 中添加
workflow_parser = subparsers.add_parser("workflow-run", help="run a standard workflow")
workflow_parser.add_argument("--workflow-id", required=True)
workflow_parser.add_argument("--context", help="JSON context file")
workflow_parser.add_argument("--agent-id", help="override agent id")
```

- [ ] **Step 2: 实现工作流执行入口**

```python
def _run_workflow_command(args):
    from workflows.loader import WorkflowLoader
    loader = WorkflowLoader()
    workflow = loader.load(args.workflow_id)
    # 解析并执行工作流步骤
    print(f"Workflow: {workflow['name']}")
    for step in workflow["steps"]:
        print(f"  Step: {step['name']} ({step['tool']})")
    return {"ok": True, "workflow_id": args.workflow_id}
```

- [ ] **Step 3: 运行 CLI 测试**

Run: `python -m unittest tests.control_plane.test_framework_cli -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add .hermes/team/control_plane/cli.py
git commit -m "feat: add workflow-run CLI command"
```

---

## Task 13: 权限配置

**Files:**
- Modify: `.hermes/team/control_plane/governance/tool_permissions.py`

- [ ] **Step 1: 新增角色工具权限映射**

```python
ROLE_TOOL_PERMISSIONS = {
    "backend-dev": [
        "generate_controller", "generate_service", "generate_mapper",
        "run_unit_tests", "write_file", "search_code", "run_command", "generate_code",
    ],
    "frontend-dev": [
        "generate_vue_component", "generate_api_client", "run_linter",
        "write_file", "search_code", "run_command", "generate_code",
    ],
    "architect": [
        "generate_architecture_doc", "review_api_design",
        "write_file", "search_code", "generate_code",
    ],
    "dba": [
        "generate_ddl", "analyze_slow_query",
        "write_file", "search_code", "run_command",
    ],
    "qa-functional": [
        "generate_test_cases", "run_api_tests",
        "write_file", "search_code", "run_command",
    ],
    "qa-performance": [
        "generate_jmeter_script", "analyze_performance_report",
        "write_file", "search_code", "run_command",
    ],
    "devops": [
        "generate_dockerfile", "generate_k8s_manifests",
        "write_file", "search_code", "run_command",
    ],
    "ucd": [
        "generate_design_spec",
        "write_file", "search_code", "generate_code",
    ],
    "requirements-analyst": [
        "generate_prd",
        "write_file", "search_code", "generate_code",
    ],
}
```

- [ ] **Step 2: 修改权限检查逻辑**

```python
def check_tool_permission(policy, actor, tool, payload, context):
    # 现有逻辑 ...
    # 新增：按角色检查工具权限
    agent_id = getattr(context, "agent_id", "")
    role = agent_id.split("-")[0] if "-" in agent_id else agent_id
    allowed_tools = ROLE_TOOL_PERMISSIONS.get(role, [])
    if tool.name not in allowed_tools:
        return False, action
    return True, action
```

- [ ] **Step 3: 运行权限测试**

Run: `python -m unittest tests.control_plane.test_tool_executor tests.control_plane.test_tool_cli -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add .hermes/team/control_plane/governance/tool_permissions.py
git commit -m "feat: add role-based tool permissions"
```

---

## Task 14: 全量回归验证

**Files:**
- 所有已修改文件

- [ ] **Step 1: 运行全量测试**

Run: `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`
Expected: 全部通过（原有 210 + 新增测试）

- [ ] **Step 2: 运行 Ruff 检查**

Run: `python -m ruff check .hermes/team/control_plane .hermes/team/调度框架/core .hermes/team/调度框架/cli/team-cli.py tests/control_plane`
Expected: All checks passed

- [ ] **Step 3: 运行覆盖率检查**

Run: `python -m coverage run -m unittest discover -s tests/control_plane -p "test_*.py"`
Run: `python -m coverage report --include=".hermes/team/control_plane/tools/*,.hermes/team/control_plane/workflows/*" --fail-under=80`
Expected: 新增模块覆盖率 >= 80%

- [ ] **Step 4: 提交**

```bash
git commit -m "test: full regression pass for agent productivity enhancement"
```

---

## Task 15: 文档更新

**Files:**
- Modify: `.hermes/team/control_plane/README.md`

- [ ] **Step 1: 更新控制平面 README**

在 README 中新增：
- 新工具列表（通用工具 + 角色专用工具）
- 工作流使用示例
- 角色权限说明

- [ ] **Step 2: 提交**

```bash
git add .hermes/team/control_plane/README.md
git commit -m "docs: update control plane README with new tools and workflows"
```

---

## 完成定义

- [ ] 9 个角色各新增 3-5 个工具（共 ~30 个）
- [ ] 9 个角色各新增 1 个标准工作流（共 9 个）
- [ ] 新增 4 个通用工具（write_file, search_code, run_command, generate_code）
- [ ] 新增工具测试全部通过
- [ ] 工作流加载测试全部通过
- [ ] 原有 210 个测试全部通过
- [ ] Ruff 检查通过
- [ ] 新增模块覆盖率 >= 80%
- [ ] CLI 支持 `tool-run` 调用所有新工具
- [ ] CLI 支持 `workflow-run` 执行标准工作流
- [ ] 文档更新完成
