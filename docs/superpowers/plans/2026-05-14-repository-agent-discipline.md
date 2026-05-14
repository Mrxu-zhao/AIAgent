# Repository Agent Discipline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为仓库新增一份根目录 `AGENTS.md`，强制外部大模型在分析和修改本 AI Agent 项目时先读代码、按证据输出并遵守主线边界。

**Architecture:** 保持实现尽量轻量：用一份根目录 `AGENTS.md` 承载硬规则、输出契约和仓库锚点，再用一条文档契约测试保证文件存在且关键内容不丢失。这样既能兼容多数代码模型，又不会引入运行时代码复杂度。

**Tech Stack:** Markdown、Python 3、unittest

---

### Task 1: 写入设计与计划文档

**Files:**
- Create: `/workspace/docs/superpowers/specs/2026-05-14-repository-agent-discipline-design.md`
- Create: `/workspace/docs/superpowers/plans/2026-05-14-repository-agent-discipline.md`

- [ ] **Step 1: 写设计文档，固定目标、边界和 `AGENTS.md` 结构**

```markdown
## 目标
- 在仓库根目录提供 `AGENTS.md`
- 要求模型先读仓库事实再输出方案
- 用最小测试保证关键锚点不漂移
```

- [ ] **Step 2: 写实施计划，明确后续文件改动和验证命令**

```markdown
### Task 2: 文档契约测试先行
### Task 3: 新增根目录 AGENTS.md
### Task 4: 跑测试并提交
```

### Task 2: 先写失败的文档契约测试

**Files:**
- Modify: `/workspace/tests/control_plane/test_documentation_contracts.py`
- Test: `/workspace/tests/control_plane/test_documentation_contracts.py`

- [ ] **Step 1: 增加根目录 `AGENTS.md` 契约测试**

```python
def test_repository_agents_guardrail_doc_exists_with_required_anchors(self):
    agents_doc = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    self.assertIn("README.md", agents_doc)
    self.assertIn("CODE_WIKI.md", agents_doc)
    self.assertIn(".hermes/team/control_plane/", agents_doc)
    self.assertIn(".hermes/team/调度框架/", agents_doc)
    self.assertIn("已读文件", agents_doc)
    self.assertIn("确认事实", agents_doc)
    self.assertIn("验证", agents_doc)
```

- [ ] **Step 2: 运行测试，确认因为缺少 `AGENTS.md` 而失败**

Run: `python -m unittest tests.control_plane.test_documentation_contracts -v`
Expected: FAIL，提示根目录 `AGENTS.md` 不存在

- [ ] **Step 3: 提交测试改动**

```bash
git add tests/control_plane/test_documentation_contracts.py
git commit -m "test: add AGENTS documentation contract"
```

### Task 3: 写根目录 `AGENTS.md`

**Files:**
- Create: `/workspace/AGENTS.md`
- Test: `/workspace/tests/control_plane/test_documentation_contracts.py`

- [ ] **Step 1: 写文件使命和必须先读的仓库入口**

```markdown
# AGENTS.md

本文件约束所有进入本仓库工作的模型或 agent。

开始任何分析、设计、修改或评审前，必须先读：
- `README.md`
- `CODE_WIKI.md`
```

- [ ] **Step 2: 写强制流程、输出契约和禁止事项**

```markdown
## 强制流程
1. 先读仓库入口和相关代码。
2. 再确认主线与兼容层边界。
3. 再输出方案或实施步骤。
4. 修改后执行验证。

## 输出契约
- 已读文件
- 确认事实
- 计划改动
- 验证方式
- 未确认项
```

- [ ] **Step 3: 写仓库锚点和 AI Agent 项目专项检查**

```markdown
- 当前推荐主入口：`.hermes/team/control_plane/`
- 历史兼容入口：`.hermes/team/调度框架/`
- 涉及 agent 行为时必须检查 `.hermes/SOUL.md`、角色 `SOUL.md`、`config.yaml`、`SKILL.md`、`.hermes/team/knowledge/`
```

- [ ] **Step 4: 运行同一条文档契约测试，确认转绿**

Run: `python -m unittest tests.control_plane.test_documentation_contracts -v`
Expected: PASS

- [ ] **Step 5: 提交文档改动**

```bash
git add AGENTS.md tests/control_plane/test_documentation_contracts.py
git commit -m "docs: add repository agent guardrails"
```

### Task 4: 完整验证与收尾

**Files:**
- Verify: `/workspace/AGENTS.md`
- Verify: `/workspace/docs/superpowers/specs/2026-05-14-repository-agent-discipline-design.md`
- Verify: `/workspace/docs/superpowers/plans/2026-05-14-repository-agent-discipline.md`

- [ ] **Step 1: 自检 `AGENTS.md` 是否短而硬、无空话和无占位符**

```text
检查项：
- 是否包含主线目录
- 是否包含输出契约
- 是否包含禁止事项
- 是否避免 “TODO/TBD”
```

- [ ] **Step 2: 运行仓库文档契约测试作为最终回归**

Run: `python -m unittest tests.control_plane.test_documentation_contracts -v`
Expected: PASS

- [ ] **Step 3: 查看工作树并提交**

```bash
git status --short
git add AGENTS.md docs/superpowers/specs/2026-05-14-repository-agent-discipline-design.md docs/superpowers/plans/2026-05-14-repository-agent-discipline.md tests/control_plane/test_documentation_contracts.py
git commit -m "docs: add repository AGENTS guardrails"
```
