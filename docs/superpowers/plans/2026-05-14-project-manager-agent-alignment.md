# Project Manager Agent Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Hermes agent 显式建模为 `project-manager` 虚拟角色，并让项目经理审批节点与团队规范、默认 workflow 和测试保持一致。

**Architecture:** 在 control plane 默认 agent 配置中新增 `project-manager` 虚拟 agent，由 Hermes 承担项目经理职责。默认 workflow 中所有项目经理审批节点显式指向该 agent，同时在团队规范和测试中补充“责任角色”和“执行主体”的一致性说明。

**Tech Stack:** Python 3、control plane 配置、workflow JSON、pytest/unittest

---

### Task 1: 对齐 agent 与 workflow

**Files:**
- Modify: `/workspace/.hermes/team/control_plane/config.py`
- Modify: `/workspace/.hermes/workflows/project_delivery.json`
- Modify: `/workspace/.hermes/团队流程规范.md`

- [ ] **Step 1: 新增 `project-manager` 虚拟 agent**

```python
("project-manager", "Hermes", "项目经理", 4, ["governance", "approval"], ["项目经理", "PM", "Hermes", "hermes"])
```

- [ ] **Step 2: 将默认 workflow 的项目经理审批节点显式指向 `project-manager`**

```json
{
  "id": "release_approval",
  "type": "human",
  "agent": "project-manager",
  "entry_checks": {
    "approval_required": true,
    "approval_role": "项目经理"
  }
}
```

- [ ] **Step 3: 在团队规范中补充 Hermes 承担项目经理角色的说明**

```markdown
在 Hermes 执行模式下，项目经理角色由 Hermes agent 以虚拟治理角色 `project-manager` 承担。
```

### Task 2: 补充回归测试

**Files:**
- Modify: `/workspace/tests/control_plane/test_workflow_runtime.py`

- [ ] **Step 1: 增加默认 agent 配置断言**

```python
config = config_module.load_control_plane_config()
assert config.agents["project-manager"].name == "Hermes"
```

- [ ] **Step 2: 增加默认 workflow 审批节点断言**

```python
manager_steps = [step for step in steps if step.get("approval_role") == "项目经理"]
assert all(step["agent"] == "project-manager" for step in manager_steps)
```

- [ ] **Step 3: 运行目标测试**

Run: `PYTHONPATH=/workspace pytest tests/control_plane/test_workflow_runtime.py -q`
Expected: PASS
