# Role Workflow Mainline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在控制平面主线新增 `cli role-workflow --workflow-id [--feature --stack --context-file]` 入口，补齐 role workflow 的 models/resolver/executor、knowledge loop 集成、权限辅助与焦点测试，同时保持团队 workflow 现有入口与定义不变。

**Architecture:** 保持 `.hermes/team/调度框架/core/workflow_engine.py` 作为团队 workflow 兼容实现不变，在 `.hermes/team/control_plane/` 新增一条独立的 role workflow 主线。CLI 通过 `workflow-id` 加载 role workflow 定义，resolver 负责把步骤解析为稳定执行计划，executor 负责组装知识包、执行 role tools、回写 knowledge loop，并通过 governance helper 统一做权限与审批检查。

**Tech Stack:** Python 3、`unittest`、现有 `tools`/`knowledge_loop`/`governance` 模块、控制平面统一 CLI

---

### Task 1: 建立 Role Workflow 契约与失败测试

**Files:**
- Create: `.hermes/team/control_plane/role_workflow_models.py`
- Create: `.hermes/team/control_plane/role_workflow_resolver.py`
- Create: `tests/control_plane/test_role_workflow_models.py`
- Test: `tests/control_plane/test_role_workflow_models.py`

- [ ] **Step 1: 先写失败测试，锁定 workflow-id、feature、stack、context 合并和步骤解析行为**

```python
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import role_workflow_models as models  # noqa: E402
import role_workflow_resolver as resolver  # noqa: E402


class RoleWorkflowResolverTests(unittest.TestCase):
    def test_resolver_builds_execution_plan_from_definition_and_overrides(self):
        definition = {
            "workflow_id": "backend_feature_delivery",
            "name": "Backend Feature Delivery",
            "roles": ["backend-dev"],
            "steps": [
                {
                    "id": "impl",
                    "role": "backend-dev",
                    "tool": "generate_service",
                    "inputs": {"class_name": "{feature}Service", "stack": "{stack}"},
                }
            ],
            "context": {"language": "java"},
        }

        request = models.RoleWorkflowRequest(
            workflow_id="backend_feature_delivery",
            feature="User",
            stack="java-spring",
            context={"module": "account"},
        )

        plan = resolver.RoleWorkflowResolver().resolve(definition, request)

        self.assertEqual(plan.workflow_id, "backend_feature_delivery")
        self.assertEqual(plan.steps[0].tool_name, "generate_service")
        self.assertEqual(plan.steps[0].payload["class_name"], "UserService")
        self.assertEqual(plan.context["language"], "java")
        self.assertEqual(plan.context["module"], "account")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行单测并确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_models -v`
Expected: FAIL，提示缺少 `role_workflow_models` / `role_workflow_resolver` 或缺少 `RoleWorkflowRequest`

- [ ] **Step 3: 写最小实现，定义请求、步骤计划和 resolver**

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RoleWorkflowRequest:
    workflow_id: str
    feature: str = ""
    stack: str = ""
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleWorkflowPlanStep:
    step_id: str
    role: str
    tool_name: str
    payload: Dict[str, Any]


@dataclass
class RoleWorkflowPlan:
    workflow_id: str
    name: str
    context: Dict[str, Any]
    steps: List[RoleWorkflowPlanStep]
```

```python
class RoleWorkflowResolver:
    def resolve(self, definition, request):
        merged_context = dict(definition.get("context") or {})
        merged_context.update(request.context)
        tokens = {
            "feature": request.feature,
            "stack": request.stack,
            **merged_context,
        }
        steps = []
        for step in definition.get("steps") or []:
            payload = {
                key: value.format(**tokens) if isinstance(value, str) else value
                for key, value in (step.get("inputs") or {}).items()
            }
            steps.append(
                RoleWorkflowPlanStep(
                    step_id=step["id"],
                    role=step["role"],
                    tool_name=step["tool"],
                    payload=payload,
                )
            )
        return RoleWorkflowPlan(
            workflow_id=request.workflow_id,
            name=str(definition.get("name") or request.workflow_id),
            context=merged_context,
            steps=steps,
        )
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_workflow_models -v`
Expected: PASS

- [ ] **Step 5: 提交这一小步**

```bash
git add .hermes/team/control_plane/role_workflow_models.py .hermes/team/control_plane/role_workflow_resolver.py tests/control_plane/test_role_workflow_models.py
git commit -m "feat: add role workflow resolver contracts"
```

### Task 2: 接入执行器、权限辅助与 knowledge loop

**Files:**
- Create: `.hermes/team/control_plane/role_workflow_executor.py`
- Create: `.hermes/team/control_plane/governance/role_workflow_permissions.py`
- Update: `.hermes/team/control_plane/knowledge_loop/__init__.py`
- Create: `tests/control_plane/test_role_workflow_executor.py`
- Update: `tests/control_plane/test_governance.py`
- Test: `tests/control_plane/test_role_workflow_executor.py`
- Test: `tests/control_plane/test_governance.py`

- [ ] **Step 1: 先写失败测试，覆盖执行顺序、权限拒绝和 knowledge loop 回写**

```python
import unittest
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import role_workflow_models as models  # noqa: E402
import role_workflow_executor as executor_module  # noqa: E402


class RoleWorkflowExecutorTests(unittest.TestCase):
    def test_executor_runs_plan_steps_and_collects_results(self):
        plan = models.RoleWorkflowPlan(
            workflow_id="backend_feature_delivery",
            name="Backend Feature Delivery",
            context={"feature": "User"},
            steps=[
                models.RoleWorkflowPlanStep(
                    step_id="impl",
                    role="backend-dev",
                    tool_name="generate_service",
                    payload={"class_name": "UserService", "package": "com.demo"},
                )
            ],
        )

        with patch.object(executor_module, "build_default_tool_registry") as registry_mock:
            with patch.object(executor_module, "ToolExecutor") as tool_executor_mock:
                registry_mock.return_value.get.return_value = object()
                tool_executor_mock.return_value.execute_many.return_value = [
                    executor_module.ToolResult.ok_result(
                        content="ok",
                        structured_data={"file": "UserService.java"},
                    )
                ]
                result = executor_module.RoleWorkflowExecutor().execute(plan, actor="admin")

        self.assertTrue(result["ok"])
        self.assertEqual(result["steps"][0]["step_id"], "impl")
        self.assertEqual(result["steps"][0]["tool"], "generate_service")
```

```python
def test_rbac_allows_role_workflow_run_for_operator_and_admin():
    policy = rbac_module.build_default_rbac_policy()
    assert policy.is_allowed("admin", "control_plane.role_workflow.run")
    assert policy.is_allowed("operator", "control_plane.role_workflow.run")
    assert not policy.is_allowed("viewer", "control_plane.role_workflow.run")
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor tests.control_plane.test_governance -v`
Expected: FAIL，提示缺少执行器或缺少 `control_plane.role_workflow.run` 权限

- [ ] **Step 3: 写最小执行器和权限辅助**

```python
def resolve_role_workflow_action(_workflow_id: str) -> str:
    return "control_plane.role_workflow.run"


def check_role_workflow_permission(policy, actor: str, workflow_id: str) -> tuple[bool, str]:
    action = resolve_role_workflow_action(workflow_id)
    return policy.is_allowed(actor, action), action
```

```python
class RoleWorkflowExecutor:
    def __init__(self, tool_executor=None, registry=None, extractor=None, updater=None):
        self.registry = registry or build_default_tool_registry()
        self.tool_executor = tool_executor or ToolExecutor()
        self.extractor = extractor or ExperienceExtractor()
        self.updater = updater or KnowledgeUpdater()

    def execute(self, plan, actor="admin"):
        results = []
        for step in plan.steps:
            tool = self.registry.get(step.tool_name)
            context = ToolExecutionContext(
                task_id=f"{plan.workflow_id}:{step.step_id}",
                agent_id=step.role,
                backend="hermes",
                intent={"workflow_id": plan.workflow_id, "role_workflow": True},
                actor=actor,
            )
            tool_result = self.tool_executor.execute_many(context, [(tool, step.payload)])[0]
            results.append(
                {
                    "step_id": step.step_id,
                    "role": step.role,
                    "tool": step.tool_name,
                    "ok": tool_result.ok,
                    "content": tool_result.content,
                    "structured_data": tool_result.structured_data,
                }
            )
        return {"ok": all(item["ok"] for item in results), "workflow_id": plan.workflow_id, "steps": results}
```

- [ ] **Step 4: 把 knowledge loop 以最小集成方式暴露成执行后回写 helper**

```python
def update_from_role_workflow(self, role: str, workflow_id: str, step_results: list[dict]) -> dict:
    records = []
    for step_result in step_results:
        content = str(step_result.get("content", ""))
        records.extend(self.extract_from_code(role, workflow_id, content, step_result.get("tool", "")))
    unique = self.deduplicate(records)
    return KnowledgeUpdater().update_role_knowledge(role, unique)
```

- [ ] **Step 5: 再跑测试确认通过**

Run: `python -m unittest tests.control_plane.test_role_workflow_executor tests.control_plane.test_governance -v`
Expected: PASS

- [ ] **Step 6: 提交这一小步**

```bash
git add .hermes/team/control_plane/role_workflow_executor.py .hermes/team/control_plane/governance/role_workflow_permissions.py .hermes/team/control_plane/knowledge_loop/__init__.py tests/control_plane/test_role_workflow_executor.py tests/control_plane/test_governance.py
git commit -m "feat: add role workflow executor and permissions"
```

### Task 3: 接入统一 CLI 并补主线回归

**Files:**
- Update: `.hermes/team/control_plane/cli.py`
- Create: `tests/control_plane/test_role_workflow_cli.py`
- Update: `tests/control_plane/test_unified_cli.py`
- Test: `tests/control_plane/test_role_workflow_cli.py`
- Test: `tests/control_plane/test_unified_cli.py`

- [ ] **Step 1: 先写失败测试，锁定 `role-workflow --workflow-id [--feature --stack --context-file]`**

```python
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import cli as unified_cli_module  # noqa: E402


class RoleWorkflowCLITests(unittest.TestCase):
    def test_parser_exposes_role_workflow_command(self):
        parser = unified_cli_module.build_parser()
        self.assertIn("role-workflow", parser.format_help())

    def test_role_workflow_command_executes_new_mainline_without_touching_team_workflow(self):
        fake_config = SimpleNamespace(sensitive_actions=[], directories={"audit_log": "audit-log.jsonl"})
        fake_audit = SimpleNamespace(log=lambda *args: None)

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=SimpleNamespace(is_allowed=lambda *_: True)):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(unified_cli_module, "load_role_workflow_definition", return_value={"workflow_id": "backend_feature_delivery", "steps": []}):
                            with patch.object(unified_cli_module, "RoleWorkflowResolver") as resolver_mock:
                                with patch.object(unified_cli_module, "RoleWorkflowExecutor") as executor_mock:
                                    resolver_mock.return_value.resolve.return_value = SimpleNamespace(workflow_id="backend_feature_delivery", name="wf", context={}, steps=[])
                                    executor_mock.return_value.execute.return_value = {"ok": True, "workflow_id": "backend_feature_delivery", "steps": []}
                                    result = unified_cli_module.main(["role-workflow", "--workflow-id", "backend_feature_delivery", "--feature", "User", "--stack", "java-spring"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["workflow_id"], "backend_feature_delivery")
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.control_plane.test_role_workflow_cli tests.control_plane.test_unified_cli -v`
Expected: FAIL，提示 parser 未暴露 `role-workflow` 或 CLI 未接上 resolver/executor

- [ ] **Step 3: 在 CLI 中新增子命令与执行分支**

```python
role_workflow = subparsers.add_parser("role-workflow", help="执行 role workflow 主线")
role_workflow.add_argument("--workflow-id", required=True)
role_workflow.add_argument("--feature")
role_workflow.add_argument("--stack")
role_workflow.add_argument("--context-file")
role_workflow.add_argument("--actor", default="admin")
```

```python
if args.command == "role-workflow":
    is_allowed = policy.is_allowed(args.actor, "control_plane.role_workflow.run")
    if not is_allowed:
        raise PermissionError("actor is not allowed to run role workflow")
    definition = load_role_workflow_definition(args.workflow_id)
    context = _load_workflow_context(getattr(args, "context_file", None))
    request = RoleWorkflowRequest(
        workflow_id=args.workflow_id,
        feature=args.feature or "",
        stack=args.stack or "",
        context=context,
    )
    plan = RoleWorkflowResolver().resolve(definition, request)
    result = RoleWorkflowExecutor().execute(plan, actor=args.actor)
    audit.log("role-workflow", {"workflow_id": args.workflow_id, "actor": args.actor, "ok": result.get("ok", False)})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result
```

- [ ] **Step 4: 跑焦点测试与诊断检查**

Run: `python -m unittest tests.control_plane.test_role_workflow_models tests.control_plane.test_role_workflow_executor tests.control_plane.test_role_workflow_cli tests.control_plane.test_unified_cli tests.control_plane.test_knowledge_loop tests.control_plane.test_governance -v`
Expected: PASS

Run: `python -m unittest tests.control_plane.test_framework_workflow tests.control_plane.test_framework_compat -v`
Expected: PASS，证明团队 workflow 兼容链路未回归

- [ ] **Step 5: 提交最终实现**

```bash
git add .hermes/team/control_plane/cli.py tests/control_plane/test_role_workflow_cli.py tests/control_plane/test_unified_cli.py
git commit -m "feat: add role workflow cli mainline"
```
