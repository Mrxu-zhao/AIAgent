# Agent Personal Workflow Mainline Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有团队级工作流语义的前提下，把 9 个角色 Agent 的个人工作流、交付契约、多栈模板、质量门禁和知识闭环接入当前 `control_plane` 主线并跑通验证。

**Architecture:** 保留现有 `workflow` / `control-plane-run` 继续服务团队级流程；新增一条独立的“个人工作流主线”，专门执行 `.hermes/team/control_plane/workflows/` 下的 `tool` 型角色工作流。通过 `RoleWorkflowLoader + RoleWorkflowExecutor + QualityGateChecker + StackRegistry + ToolExecutor` 完成个人角色从读取知识、生成产物、质量检查到知识回写的完整链路。

**Tech Stack:** Python 3.11, unittest, pathlib, dataclasses, json, argparse, existing control_plane tool runtime

---

## 文件结构总览

```text
.hermes/team/control_plane/
├── cli.py
├── delivery/
│   ├── contracts/
│   ├── quality_gates/
│   └── quality_gate.py
├── knowledge_loop/
│   ├── __init__.py
│   ├── extractor.py
│   └── updater.py
├── stacks/
│   ├── __init__.py
│   └── registry.py
├── tools/
│   ├── builtin.py
│   ├── common_tools.py
│   ├── executor.py
│   └── role_tools/
├── workflows/
│   ├── __init__.py
│   ├── loader.py
│   ├── executor.py
│   ├── models.py
│   ├── resolver.py
│   ├── backend-api-development.yaml
│   ├── frontend-page-development.yaml
│   ├── architect-design-review.yaml
│   ├── dba-table-design.yaml
│   ├── qa-test-case-design.yaml
│   ├── devops-deployment.yaml
│   ├── ucd-interaction-design.yaml
│   ├── requirements-analysis.yaml
│   ├── web/
│   ├── platform/
│   ├── mobile/
│   └── harmony/
└── governance/
    └── tool_permissions.py

tests/control_plane/
├── test_common_tools.py
├── test_role_tools.py
├── test_stack_plugins.py
├── test_workflows.py
├── test_quality_gates.py
├── test_knowledge_loop.py
└── test_role_workflow_executor.py
```

---

### Task 1: 固化个人工作流边界

**Files:**
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\README.md`
- Modify: `d:\workspace\AIAgent\docs\superpowers\plans\2026-05-15-agent-productivity-enhancement.md`
- Modify: `d:\workspace\AIAgent\docs\superpowers\plans\2026-05-15-agent-delivery-capability.md`

- [ ] **Step 1: 明确双轨语义**

在 `README.md` 增加一段说明：

```md
## 个人工作流主线

- 团队级工作流继续使用 `workflow` / `control-plane-run`
- 角色个人工作流使用新的 `role-workflow` 入口
- `.hermes/team/control_plane/workflows/` 下的 `tool` 型 YAML 不替代团队级工作流
```

- [ ] **Step 2: 更新计划文档口径**

把两份已有计划中的“修改现有 workflow 命令”统一改成“新增 `role-workflow` 主线，不改变团队 workflow”。

- [ ] **Step 3: 验证文本一致性**

Run: `python -m unittest tests.control_plane.test_documentation_contracts -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .hermes/team/control_plane/README.md docs/superpowers/plans/2026-05-15-agent-*.md
git commit -m "docs: define personal workflow mainline boundary"
```

---

### Task 2: 让工作流加载器稳定可用

**Files:**
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\loader.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_workflows.py`

- [ ] **Step 1: 写失败测试，覆盖递归加载和嵌套 YAML**

```python
def test_list_workflows_in_nested_directories(self):
    loader = WorkflowLoader()
    workflows = loader.list_workflows()
    self.assertIn("web-backend-api", workflows)
    self.assertIn("platform-service-development", workflows)

def test_load_nested_workflow_with_steps_tool_field(self):
    loader = WorkflowLoader()
    workflow = loader.load("web/backend-api")
    self.assertEqual(workflow["steps"][0]["tool"], "read_knowledge")
```

- [ ] **Step 2: 运行测试确认当前失败**

Run: `python -m unittest tests.control_plane.test_workflows -v`
Expected: FAIL with `KeyError: 'tool'` or nested workflow not found

- [ ] **Step 3: 实现稳定 YAML 解析和递归索引**

```python
class WorkflowLoader:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path(__file__).resolve().parent

    def _all_workflow_files(self):
        return sorted(self.base_dir.rglob("*.yaml"))

    def load(self, workflow_id: str) -> Dict[str, Any]:
        path = self._resolve_workflow_path(workflow_id)
        text = path.read_text(encoding="utf-8")
        import yaml
        data = yaml.safe_load(text)
        if not isinstance(data, dict) or "steps" not in data:
            raise ValueError(f"invalid workflow definition: {workflow_id}")
        return data
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_workflows -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/workflows/loader.py tests/control_plane/test_workflows.py
git commit -m "fix: make role workflow loader support nested yaml definitions"
```

---

### Task 3: 引入个人工作流数据模型

**Files:**
- Create: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\models.py`
- Create: `d:\workspace\AIAgent\tests\control_plane\test_role_workflow_executor.py`

- [ ] **Step 1: 写失败测试，覆盖模型装载**

```python
def test_role_workflow_model_from_definition(self):
    definition = {
        "workflow_id": "backend-api-development",
        "role": "backend-dev",
        "steps": [{"step_id": "read_requirement", "tool": "read_knowledge", "input": {}}],
    }
    workflow = RoleWorkflow.from_dict(definition)
    self.assertEqual(workflow.workflow_id, "backend-api-development")
    self.assertEqual(workflow.steps[0].tool, "read_knowledge")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowModelTests -v`
Expected: FAIL with import error

- [ ] **Step 3: 写最小实现**

```python
@dataclass
class RoleWorkflowStep:
    step_id: str
    name: str
    tool: str
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RoleWorkflow:
    workflow_id: str
    name: str
    role: str
    scene: str | None
    stack_selection: Dict[str, Any]
    steps: List[RoleWorkflowStep]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowModelTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/workflows/models.py tests/control_plane/test_role_workflow_executor.py
git commit -m "feat: add role workflow data models"
```

---

### Task 4: 实现变量解析与步骤输出引用

**Files:**
- Create: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\resolver.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_role_workflow_executor.py`

- [ ] **Step 1: 写失败测试**

```python
def test_resolve_feature_placeholder(self):
    resolver = WorkflowValueResolver({"feature": "user", "Feature": "User"})
    self.assertEqual(resolver.resolve_value("/api/{feature}"), "/api/user")

def test_resolve_step_output_reference(self):
    resolver = WorkflowValueResolver({"step_outputs": {"generate_controller": {"output": "class UserController {}"}}})
    self.assertEqual(resolver.resolve_value("${generate_controller.output}"), "class UserController {}")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.WorkflowValueResolverTests -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
class WorkflowValueResolver:
    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def resolve_value(self, value: Any) -> Any:
        if isinstance(value, str):
            value = value.format(**{k: v for k, v in self.context.items() if isinstance(v, (str, int, float))})
            return self._resolve_step_expression(value)
        if isinstance(value, list):
            return [self.resolve_value(item) for item in value]
        if isinstance(value, dict):
            return {k: self.resolve_value(v) for k, v in value.items()}
        return value
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.WorkflowValueResolverTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/workflows/resolver.py tests/control_plane/test_role_workflow_executor.py
git commit -m "feat: add role workflow value resolver"
```

---

### Task 5: 实现个人工作流执行器骨架

**Files:**
- Create: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\executor.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_role_workflow_executor.py`

- [ ] **Step 1: 写失败测试，覆盖步骤顺序执行**

```python
def test_execute_role_workflow_runs_tools_in_order(self):
    workflow = RoleWorkflow.from_dict({
        "workflow_id": "demo",
        "name": "demo",
        "role": "backend-dev",
        "steps": [
            {"step_id": "s1", "name": "read", "tool": "read_file", "input": {"path": "README.md"}},
            {"step_id": "s2", "name": "handoff", "tool": "dispatch_task", "input": {"agent_id": "qa-functional", "task": "done"}},
        ],
    })
    result = executor.execute(workflow, {"feature": "user"})
    self.assertTrue(result["ok"])
    self.assertEqual(result["steps"][0]["step_id"], "s1")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowExecutorTests.test_execute_role_workflow_runs_tools_in_order -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
class RoleWorkflowExecutor:
    def __init__(self, registry: ToolRegistry, tool_executor: ToolExecutor):
        self.registry = registry
        self.tool_executor = tool_executor

    def execute(self, workflow: RoleWorkflow, context_values: Dict[str, Any]) -> Dict[str, Any]:
        resolver = WorkflowValueResolver(dict(context_values))
        step_results = []
        for step in workflow.steps:
            tool = self.registry.get(step.tool)
            payload = resolver.resolve_value(step.input)
            result = self.tool_executor.execute_many(self._build_context(workflow), [(tool, payload)])[0]
            step_results.append({"step_id": step.step_id, "tool": step.tool, "ok": result.ok, "content": result.content})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowExecutorTests.test_execute_role_workflow_runs_tools_in_order -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/workflows/executor.py tests/control_plane/test_role_workflow_executor.py
git commit -m "feat: add role workflow executor skeleton"
```

---

### Task 6: 接入栈选择与多栈模板

**Files:**
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\stacks\registry.py`
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\executor.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_stack_plugins.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_role_workflow_executor.py`

- [ ] **Step 1: 写失败测试**

```python
def test_executor_uses_default_stack_selection(self):
    workflow = loader.load("web/backend-api")
    result = executor.execute_from_definition(workflow, {"feature": "user"})
    self.assertEqual(result["stack"]["stack_id"], "java-spring")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_stack_plugins tests.control_plane.test_role_workflow_executor -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
def resolve_stack(self, workflow: RoleWorkflow, context_values: Dict[str, Any]) -> Dict[str, Any]:
    selection = workflow.stack_selection or {}
    stack_id = context_values.get("stack") or selection.get("default")
    if not stack_id:
        return {}
    category = self._infer_stack_category(workflow.role, workflow.scene)
    config = get_stack_config(category, stack_id)
    return {"category": category, "stack_id": stack_id, "commands": config.commands, "templates_dir": config.templates_dir}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_stack_plugins tests.control_plane.test_role_workflow_executor -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/stacks/registry.py .hermes/team/control_plane/workflows/executor.py tests/control_plane/test_stack_plugins.py tests/control_plane/test_role_workflow_executor.py
git commit -m "feat: integrate stack selection into role workflow execution"
```

---

### Task 7: 让质量门禁脱离环境依赖

**Files:**
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\delivery\quality_gate.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_quality_gates.py`

- [ ] **Step 1: 写失败测试，覆盖无 PyYAML 环境下的契约读取**

```python
def test_backend_contract_loads_without_external_yaml_dependency(self):
    report = self.checker.check("backend", {"coverage": 90, "code": "def ok():\n    return 1"})
    self.assertEqual(report.role, "backend")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_quality_gates -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yaml'`

- [ ] **Step 3: 写最小实现**

```python
def _load_yaml_file(path: str) -> Dict[str, Any]:
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ModuleNotFoundError:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(json.dumps(_parse_yaml_simple(text)))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_quality_gates -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/delivery/quality_gate.py tests/control_plane/test_quality_gates.py
git commit -m "fix: make quality gate checker work without optional yaml dependency"
```

---

### Task 8: 把质量门禁挂到个人工作流执行器

**Files:**
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\executor.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_role_workflow_executor.py`

- [ ] **Step 1: 写失败测试**

```python
def test_role_workflow_runs_quality_gate_after_steps(self):
    result = executor.execute_from_definition(loader.load("backend-api-development"), {"feature": "user"})
    self.assertIn("quality_report", result)
    self.assertIn("overall_status", result["quality_report"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowExecutorTests.test_role_workflow_runs_quality_gate_after_steps -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
checker = QualityGateChecker()
deliverables = self._collect_deliverables(workflow, step_results)
quality_report = checker.check(self._normalize_role_contract_name(workflow.role), deliverables).to_dict()
return {"ok": all(item["ok"] for item in step_results), "steps": step_results, "quality_report": quality_report}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowExecutorTests.test_role_workflow_runs_quality_gate_after_steps -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/workflows/executor.py tests/control_plane/test_role_workflow_executor.py
git commit -m "feat: attach quality gates to role workflow execution"
```

---

### Task 9: 固化知识闭环模块

**Files:**
- Create: `d:\workspace\AIAgent\.hermes\team\control_plane\knowledge_loop\__init__.py`
- Create: `d:\workspace\AIAgent\.hermes\team\control_plane\knowledge_loop\extractor.py`
- Create: `d:\workspace\AIAgent\.hermes\team\control_plane\knowledge_loop\updater.py`
- Create: `d:\workspace\AIAgent\tests\control_plane\test_knowledge_loop.py`

- [ ] **Step 1: 写失败测试**

```python
def test_extract_lessons_from_successful_workflow(self):
    extractor = ExperienceExtractor()
    lessons = extractor.extract_lessons({"success": True, "workflow_id": "backend-api-development"})
    self.assertTrue(lessons)

def test_append_lessons_writes_recent_lessons(self):
    updater = KnowledgeUpdater(tmp_dir)
    updater.append_lessons("backend-dev", ["lesson 1"])
    self.assertTrue((Path(tmp_dir) / "agents" / "backend-dev" / "knowledge" / "recent-lessons.md").exists())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_knowledge_loop -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
class ExperienceExtractor:
    def extract_lessons(self, workflow_result: Dict[str, Any]) -> List[str]:
        lessons = []
        if workflow_result.get("success"):
            lessons.append(f"成功完成工作流: {workflow_result.get('workflow_id')}")
        for step in workflow_result.get("steps", []):
            if step.get("ok"):
                lessons.append(f"稳定步骤: {step.get('step_id')}")
        return lessons
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_knowledge_loop -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/knowledge_loop tests/control_plane/test_knowledge_loop.py
git commit -m "feat: add knowledge loop extractor and updater"
```

---

### Task 10: 把知识闭环挂到个人工作流执行结果

**Files:**
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\executor.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_role_workflow_executor.py`

- [ ] **Step 1: 写失败测试**

```python
def test_role_workflow_updates_recent_lessons_on_success(self):
    result = executor.execute_from_definition(loader.load("requirements-analysis"), {"feature": "user"})
    self.assertIn("knowledge_feedback", result)
    self.assertIn("lessons", result["knowledge_feedback"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowExecutorTests.test_role_workflow_updates_recent_lessons_on_success -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
extractor = ExperienceExtractor()
updater = KnowledgeUpdater(str(repository_root() / ".hermes"))
lessons = extractor.extract_lessons({"success": ok, "workflow_id": workflow.workflow_id, "steps": step_results})
updater.append_lessons(workflow.role, lessons)
result["knowledge_feedback"] = {"lessons": lessons}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowExecutorTests.test_role_workflow_updates_recent_lessons_on_success -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/workflows/executor.py tests/control_plane/test_role_workflow_executor.py
git commit -m "feat: add knowledge feedback to role workflow execution"
```

---

### Task 11: 完成 CLI 集成

**Files:**
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\cli.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_role_workflow_executor.py`

- [ ] **Step 1: 写失败测试**

```python
def test_cli_role_workflow_command_returns_workflow_result(self):
    result = cli.main(["role-workflow", "--workflow-id", "requirements-analysis", "--feature", "user"])
    self.assertEqual(result["workflow_id"], "requirements-analysis")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowCliTests -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
role_workflow = subparsers.add_parser("role-workflow", help="执行角色个人工作流")
role_workflow.add_argument("--workflow-id", required=True)
role_workflow.add_argument("--feature")
role_workflow.add_argument("--stack")
role_workflow.add_argument("--context-file")
```

并在 `main()` 中增加：

```python
if args.command == "role-workflow":
    loader = WorkflowLoader()
    definition = loader.load(args.workflow_id)
    executor = build_role_workflow_executor(config)
    payload = executor.execute_from_definition(definition, _build_role_workflow_context(args))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowCliTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/cli.py tests/control_plane/test_role_workflow_executor.py
git commit -m "feat: add role-workflow cli command"
```

---

### Task 12: 校准工具权限与角色映射

**Files:**
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\governance\tool_permissions.py`
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_role_workflow_executor.py`

- [ ] **Step 1: 写失败测试**

```python
def test_backend_role_workflow_can_use_backend_tools(self):
    allowed = is_role_tool_allowed("backend-dev", "generate_controller")
    self.assertTrue(allowed)

def test_backend_role_workflow_cannot_use_frontend_tool(self):
    allowed = is_role_tool_allowed("backend-dev", "generate_vue_component")
    self.assertFalse(allowed)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowPermissionTests -v`
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
ROLE_TOOL_PERMISSIONS = {
    "backend-dev": {"generate_controller", "generate_service", "generate_mapper", "run_unit_tests", "write_file", "search_code", "read_knowledge"},
    "frontend-dev": {"generate_vue_component", "generate_api_client", "run_linter", "write_file", "search_code", "read_knowledge"},
}

def is_role_tool_allowed(role: str, tool_name: str) -> bool:
    return tool_name in ROLE_TOOL_PERMISSIONS.get(role, set())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor.RoleWorkflowPermissionTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/governance/tool_permissions.py tests/control_plane/test_role_workflow_executor.py
git commit -m "feat: align role workflow tool permissions"
```

---

### Task 13: 补齐个人工作流 YAML 与交付契约的一致性

**Files:**
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\*.yaml`
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\web\*.yaml`
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\platform\*.yaml`
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\mobile\*.yaml`
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\workflows\harmony\*.yaml`
- Modify: `d:\workspace\AIAgent\.hermes\team\control_plane\delivery\contracts\*.yaml`

- [ ] **Step 1: 对齐角色名、handoff 目标和 gate 名称**

确保：

```yaml
role: backend-dev
quality_gates:
  - gate: 单测覆盖
  - gate: 代码评审
handoff:
  - target: qa-functional
```

- [ ] **Step 2: 对齐个人工作流步骤结构**

确保每个工作流步骤至少包含：

```yaml
- step_id: generate_output
  name: 生成产物
  tool: generate_prd
  input:
    feature: "{Feature}"
```

- [ ] **Step 3: 运行加载与质量门禁测试**

Run: `python -m unittest tests.control_plane.test_workflows tests.control_plane.test_quality_gates -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .hermes/team/control_plane/workflows .hermes/team/control_plane/delivery/contracts
git commit -m "fix: align role workflows and delivery contracts"
```

---

### Task 14: 跑通新增能力全量测试

**Files:**
- Modify: `d:\workspace\AIAgent\tests\control_plane\test_role_workflow_executor.py`
- Verify: `d:\workspace\AIAgent\tests\control_plane\test_common_tools.py`
- Verify: `d:\workspace\AIAgent\tests\control_plane\test_role_tools.py`
- Verify: `d:\workspace\AIAgent\tests\control_plane\test_stack_plugins.py`
- Verify: `d:\workspace\AIAgent\tests\control_plane\test_workflows.py`
- Verify: `d:\workspace\AIAgent\tests\control_plane\test_quality_gates.py`
- Verify: `d:\workspace\AIAgent\tests\control_plane\test_knowledge_loop.py`

- [ ] **Step 1: 跑新增能力测试集**

Run: `python -m unittest tests.control_plane.test_common_tools tests.control_plane.test_role_tools tests.control_plane.test_stack_plugins tests.control_plane.test_workflows tests.control_plane.test_quality_gates tests.control_plane.test_knowledge_loop tests.control_plane.test_role_workflow_executor -v`
Expected: PASS

- [ ] **Step 2: 修正失败用例直到通过**

优先修正：
- `KeyError: 'tool'`
- `ModuleNotFoundError: yaml`
- CLI `role-workflow` 入口缺失
- 执行器变量替换失败

- [ ] **Step 3: Commit**

```bash
git add .hermes/team/control_plane tests/control_plane
git commit -m "test: pass all personal workflow integration tests"
```

---

### Task 15: 跑全量回归并复核 AGENTS.md 的实际作用

**Files:**
- Verify: `d:\workspace\AIAgent\AGENTS.md`
- Verify: `d:\workspace\AIAgent\tests\control_plane\test_documentation_contracts.py`
- Verify: `d:\workspace\AIAgent\.hermes\team\control_plane\cli.py`

- [ ] **Step 1: 运行控制平面全量测试**

Run: `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`
Expected: PASS

- [ ] **Step 2: 运行 Ruff**

Run: `python -m ruff check .hermes/team/control_plane .hermes/team/调度框架/core .hermes/team/调度框架/cli/team-cli.py tests/control_plane`
Expected: All checks passed

- [ ] **Step 3: 复核 AGENTS.md 实际效果**

检查点：
- `AGENTS.md` 是否仍要求先读 `README.md` / `CODE_WIKI.md`
- `test_documentation_contracts.py` 是否仍能验证关键锚点存在
- 个人工作流新增后是否没有绕开主线/兼容层区分规则

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md tests/control_plane/test_documentation_contracts.py .hermes/team/control_plane
git commit -m "test: verify full regression and agents guardrail effectiveness"
```

---

## 完成定义

- [ ] 团队级工作流命令与语义保持不变
- [ ] 新增 `role-workflow` 个人工作流主线
- [ ] 9 个角色个人工作流可通过 CLI 执行
- [ ] `delivery` / `stacks` / `quality_gate` / `knowledge_loop` 均接入个人工作流执行链
- [ ] 新增工作流 YAML 可稳定加载，支持子目录与嵌套 step 结构
- [ ] 质量门禁不依赖可选外部环境即可运行
- [ ] 知识闭环能回写角色 `recent-lessons`
- [ ] 新增测试全部通过
- [ ] 原有团队主线测试不降级
