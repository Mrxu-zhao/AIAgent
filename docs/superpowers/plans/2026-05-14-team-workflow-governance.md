# Team Workflow Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将团队流程规范收敛为 `.hermes/团队流程规范.md`，新增独立 workflow 目录，并让统一入口按显式流程定义执行且强制准入与阻塞审批。

**Architecture:** 文档层只定义团队基线规范，流程实例落在独立 workflow 文件中。执行层由 `workflow_engine.py` 读取流程定义并在每个步骤上执行准入校验、阻塞审批和交付物约束，CLI 的 `control-plane-run` 与 `workflow` 统一走同一条 workflow 入口。

**Tech Stack:** Python 3、现有 control plane CLI、现有 workflow engine、unittest/pytest 测试

---

### Task 1: 统一团队流程规范文档

**Files:**
- Create: `.hermes/团队流程规范.md`
- Delete: `.hermes/projects/team/团队流程规范.md`
- Delete: `团队流程规范.md`

- [ ] **Step 1: 新文档整合团队规范**

```markdown
# StudyHelper 团队流程规范 v3.0

## 一、定位
- 本文档定义团队级基线规范，不与具体项目流程实例耦合。

## 二、强制阶段
- 需求确认
- 需求分析
- 需求评审
- UCD设计
- UCD评审
- 架构设计
- 架构评审
- 数据库设计
- 数据库评审
- 前后端开发
- 单元测试
- 功能测试
- 缺陷修复
- 回归测试
- 闭环确认
- 发布审批
- 部署上线

## 三、准入字段
- required_deliverables
- coverage_threshold
- test_pass_rate
- defect_closure_rate
- approval_required
- approval_role
```

- [ ] **Step 2: 删除旧的重复规范文件**

Run: `python - <<'PY'\nfrom pathlib import Path\nfor path in [Path('/workspace/.hermes/projects/team/团队流程规范.md'), Path('/workspace/团队流程规范.md')]:\n    if path.exists():\n        path.unlink()\nPY`
Expected: 命令成功退出，两个旧文件不存在

- [ ] **Step 3: 自检文档路径**

Run: `python - <<'PY'\nfrom pathlib import Path\nprint(Path('/workspace/.hermes/团队流程规范.md').exists())\nprint(Path('/workspace/.hermes/projects/team/团队流程规范.md').exists())\nprint(Path('/workspace/团队流程规范.md').exists())\nPY`
Expected: 输出依次为 `True`、`False`、`False`

- [ ] **Step 4: Commit**

```bash
git add /workspace/.hermes/团队流程规范.md /workspace/.hermes/projects/team/团队流程规范.md /workspace/团队流程规范.md
git commit -m "docs: unify team workflow spec"
```

### Task 2: 增加独立 workflow 目录和流程定义文件

**Files:**
- Create: `.hermes/workflows/project_delivery.yaml`
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Test: `tests/control_plane/test_workflow_runtime.py`

- [ ] **Step 1: 写出流程定义文件**

```yaml
workflow_id: project_delivery
name: 项目开发流程
description: 按团队规范执行的项目交付流程
variables:
  review_policy: blocking
steps:
  - id: requirement_confirmation
    name: 需求确认
    type: human
    agent: project-manager
    task: 确认需求范围、优先级和里程碑
    entry_checks:
      required_deliverables: ["需求确认单.md"]
      approval_required: true
      approval_role: project-manager
```

- [ ] **Step 2: 实现流程文件加载函数的失败测试**

```python
def test_workflow_engine_can_load_workflow_definition_from_file():
    workflow = workflow_module.load_workflow_definition(Path(tmp) / "project_delivery.yaml")
    assert workflow["workflow_id"] == "project_delivery"
```

- [ ] **Step 3: 在 `workflow_engine.py` 中实现文件加载与默认流程定位**

```python
def load_workflow_definition(path: Path) -> Dict[str, Any]:
    import yaml
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
```

- [ ] **Step 4: 运行新增测试**

Run: `pytest tests/control_plane/test_workflow_runtime.py -k workflow_definition -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /workspace/.hermes/workflows/project_delivery.yaml /workspace/.hermes/team/调度框架/core/workflow_engine.py /workspace/tests/control_plane/test_workflow_runtime.py
git commit -m "feat: add workflow definition loading"
```

### Task 3: 给步骤和任务卡增加准入字段

**Files:**
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Modify: `.hermes/team/control_plane/models.py`
- Test: `tests/control_plane/test_workflow_runtime.py`

- [ ] **Step 1: 先写失败测试覆盖准入字段映射**

```python
def test_workflow_builds_task_card_with_entry_checks():
    card = engine._build_task_card_for_step(workflow, step, "实现代码", "backend-1", "hermes")
    assert card.entry_checks["coverage_threshold"]["backend"] == 70
    assert "单元测试报告.md" in card.required_deliverables
```

- [ ] **Step 2: 扩展 `TaskCard` 和 `WorkflowStep` 字段**

```python
entry_checks: Dict[str, object] = field(default_factory=dict)
required_deliverables: List[str] = field(default_factory=list)
approval_required: bool = False
approval_role: Optional[str] = None
```

- [ ] **Step 3: 在 task card 构建逻辑中映射流程定义字段**

```python
entry_checks = getattr(step, "entry_checks", {}) or {}
required_deliverables = list(entry_checks.get("required_deliverables", []))
```

- [ ] **Step 4: 运行定向测试**

Run: `pytest tests/control_plane/test_workflow_runtime.py -k entry_checks -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /workspace/.hermes/team/调度框架/core/workflow_engine.py /workspace/.hermes/team/control_plane/models.py /workspace/tests/control_plane/test_workflow_runtime.py
git commit -m "feat: add workflow entry check metadata"
```

### Task 4: 实现准入校验和阻塞审批

**Files:**
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Test: `tests/control_plane/test_workflow_runtime.py`

- [ ] **Step 1: 写失败测试覆盖阻塞审批与指标校验**

```python
def test_human_review_blocks_without_approval():
    result = engine.execute_workflow(workflow.id, {"approvals": {}})
    assert not result["success"]
    assert "approval" in result["error"]
```

```python
def test_entry_checks_block_on_missing_metrics():
    result = engine.execute_workflow(workflow.id, {"quality_gates": {"coverage": {"backend": 60}}})
    assert not result["success"]
    assert "coverage" in result["error"]
```

- [ ] **Step 2: 增加统一校验函数**

```python
def _validate_entry_checks(self, workflow: Workflow, step: WorkflowStep, variables: Dict[str, Any]) -> Optional[str]:
    quality_gates = variables.get("quality_gates", {})
    deliverables = set(variables.get("deliverables", []))
    ...
    return None
```

- [ ] **Step 3: 把 `human` 步骤改成真正阻塞**

```python
def _execute_human_review(self, step: WorkflowStep, task_content: str, workflow: Workflow) -> Dict:
    approvals = workflow.variables.get("approvals", {})
    approval = approvals.get(step.id)
    if not approval or not approval.get("approved"):
        return {"success": False, "error": f"approval required for {step.id}", "blocked": True}
    return {"success": True, "output": approval.get("comment", task_content), "agent": step.agent}
```

- [ ] **Step 4: 在步骤执行前接入准入校验**

```python
gate_error = self._validate_entry_checks(workflow, step, workflow.variables)
if gate_error:
    step.status = StepStatus.FAILED
    step.error = gate_error
    ...
```

- [ ] **Step 5: 运行 workflow 测试**

Run: `pytest tests/control_plane/test_workflow_runtime.py -k "approval or coverage or deliverable" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add /workspace/.hermes/team/调度框架/core/workflow_engine.py /workspace/tests/control_plane/test_workflow_runtime.py
git commit -m "feat: enforce workflow approvals and entry gates"
```

### Task 5: 统一 CLI 入口到 workflow

**Files:**
- Modify: `.hermes/team/control_plane/cli.py`
- Modify: `.hermes/team/control_plane/runner.py`
- Test: `tests/control_plane/test_unified_cli.py`

- [ ] **Step 1: 写失败测试保证 `control-plane-run` 不再直接依赖静态 `TASKS`**

```python
def test_control_plane_run_uses_workflow_definition():
    result = unified_cli_module.main(["control-plane-run"])
    assert result["workflow_id"] == "project_delivery"
```

- [ ] **Step 2: 在 CLI 中增加 workflow 目录默认值和加载逻辑**

```python
WORKFLOW_DIR = Path(__file__).resolve().parents[2] / "workflows"
DEFAULT_WORKFLOW_FILE = WORKFLOW_DIR / "project_delivery.yaml"
```

- [ ] **Step 3: 让 `control-plane-run` 与 `workflow` 共享同一执行函数**

```python
def run_workflow_command(workflow_path: Path, name: str | None = None):
    definition = load_workflow_definition(workflow_path)
    ...
```

- [ ] **Step 4: 保留旧 `TASKS` 仅用于兼容测试，不作为默认入口**

```python
def run_task_batch(...):
    raise RuntimeError("static TASKS entry is deprecated; use workflow definitions")
```

- [ ] **Step 5: 运行 CLI 测试**

Run: `pytest tests/control_plane/test_unified_cli.py -k "workflow or control_plane_run" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add /workspace/.hermes/team/control_plane/cli.py /workspace/.hermes/team/control_plane/runner.py /workspace/tests/control_plane/test_unified_cli.py
git commit -m "feat: route control-plane entry through workflows"
```

### Task 6: 全量验证和清理

**Files:**
- Modify: `tests/control_plane/test_workflow_runtime.py`
- Modify: `tests/control_plane/test_unified_cli.py`

- [ ] **Step 1: 运行目标测试集**

Run: `pytest tests/control_plane/test_workflow_runtime.py tests/control_plane/test_unified_cli.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 检查最近改动文件诊断**

Run: `python -m pytest tests/control_plane/test_workflow_runtime.py tests/control_plane/test_unified_cli.py -q`
Expected: 退出码 0

- [ ] **Step 3: Commit**

```bash
git add /workspace/tests/control_plane/test_workflow_runtime.py /workspace/tests/control_plane/test_unified_cli.py
git commit -m "test: cover workflow governance flow"
```
