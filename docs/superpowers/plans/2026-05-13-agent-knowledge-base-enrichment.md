# Agent Knowledge Base Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Hermes 团队结构上落地团队公共知识、角色知识和实例知识三层目录与首批内容，并补齐索引与兼容入口。

**Architecture:** 采用“保留旧知识文件 + 新增标准入口”的兼容策略。团队层新增真实 `team/knowledge` 目录与共享文档，角色层新增统一的 `overview/playbooks/checklists/templates` 等标准文件，实例层为 13 个团队成员建立最小画像知识目录。

**Tech Stack:** Markdown, Python 3, PowerShell, Trae file editing tools

---

### Task 1: 创建计划与生成脚本骨架

**Files:**
- Create: `docs/superpowers/plans/2026-05-13-agent-knowledge-base-enrichment.md`
- Create: `d:/KIMIK2.5/AIAgent/.tmp_generate_agent_kb.py`

- [ ] **Step 1: 写生成脚本骨架**

```python
from pathlib import Path

ROOT = Path(r"d:\KIMIK2.5\AIAgent")

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
```

- [ ] **Step 2: 运行脚本验证可写入临时文件**

Run: `python .tmp_generate_agent_kb.py`
Expected: 脚本正常退出，无 traceback

### Task 2: 落地团队公共知识层

**Files:**
- Create: `.hermes/team/knowledge/README.md`
- Create: `.hermes/team/knowledge/status.md`
- Create: `.hermes/team/knowledge/project-overview.md`
- Create: `.hermes/team/knowledge/domain-glossary.md`
- Create: `.hermes/team/knowledge/architecture-map.md`
- Create: `.hermes/team/knowledge/repo-map.md`
- Create: `.hermes/team/knowledge/workflow-playbook.md`
- Create: `.hermes/team/knowledge/handoff-templates.md`
- Create: `.hermes/team/knowledge/risk-register.md`
- Create: `.hermes/team/knowledge/decision-log.md`
- Create: `.hermes/team/knowledge/templates/README.md`
- Create: `.hermes/team/knowledge/patterns/README.md`
- Create: `.hermes/team/knowledge/lessons/README.md`
- Create: `.hermes/team/knowledge/glossaries/README.md`

- [ ] **Step 1: 在脚本中写入团队公共知识模板**

```python
team_docs = {
    ".hermes/team/knowledge/status.md": "# 团队知识库状态\n\n- 状态：已初始化\n- 目标：...",
    ".hermes/team/knowledge/project-overview.md": "# 项目概览\n\n## 目标\n- ...",
}

for relative_path, content in team_docs.items():
    write_text(ROOT / relative_path, content)
```

- [ ] **Step 2: 运行脚本生成团队知识文件**

Run: `python .tmp_generate_agent_kb.py`
Expected: 生成 `.hermes/team/knowledge/` 及其子文件，无错误

### Task 3: 标准化角色知识入口

**Files:**
- Modify/Create: `.hermes/agents/*/knowledge/README.md`
- Create: `.hermes/agents/*/knowledge/overview.md`
- Create: `.hermes/agents/*/knowledge/playbooks/common-tasks.md`
- Create: `.hermes/agents/*/knowledge/playbooks/troubleshooting.md`
- Create: `.hermes/agents/*/knowledge/patterns/preferred-patterns.md`
- Create: `.hermes/agents/*/knowledge/patterns/anti-patterns.md`
- Create: `.hermes/agents/*/knowledge/checklists/design-checklist.md`
- Create: `.hermes/agents/*/knowledge/checklists/delivery-checklist.md`
- Create: `.hermes/agents/*/knowledge/pitfalls/common-mistakes.md`
- Create: `.hermes/agents/*/knowledge/templates/output-templates.md`
- Create: `.hermes/agents/*/knowledge/examples/good-examples.md`

- [ ] **Step 1: 在脚本中声明 9 个角色的知识模板**

```python
roles = {
    "architect": {"title": "系统架构师", "focus": ["系统边界", "技术选型", "非功能需求"]},
    "backend-dev": {"title": "后端开发", "focus": ["接口设计", "事务一致性", "可维护性"]},
}
```

- [ ] **Step 2: 生成标准入口文件并保留已有旧文件**

```python
for role, meta in roles.items():
    base = ROOT / ".hermes" / "agents" / role / "knowledge"
    write_text(base / "overview.md", f"# {meta['title']} 知识总览\n")
    write_text(base / "playbooks" / "common-tasks.md", "# 高频任务打法\n")
```

- [ ] **Step 3: 运行脚本并检查角色目录**

Run: `python .tmp_generate_agent_kb.py`
Expected: 每个角色目录新增标准入口文件，旧文件仍保留

### Task 4: 补齐 13 个实例知识目录

**Files:**
- Create: `.hermes/team/agents/<agent>/knowledge/README.md`
- Create: `.hermes/team/agents/<agent>/knowledge/expertise.md`
- Create: `.hermes/team/agents/<agent>/knowledge/owned-modules.md`
- Create: `.hermes/team/agents/<agent>/knowledge/collaboration-preferences.md`
- Create: `.hermes/team/agents/<agent>/knowledge/delivery-style.md`
- Create: `.hermes/team/agents/<agent>/knowledge/recent-lessons.md`

- [ ] **Step 1: 在脚本中声明 13 个团队成员画像**

```python
agents = {
    "backend-1": {"name": "陈启明", "role": "后端开发", "strengths": ["Spring Boot", "MyBatis-Plus"]},
    "frontend-1": {"name": "李思雨", "role": "前端开发", "strengths": ["Vue 3", "TypeScript"]},
}
```

- [ ] **Step 2: 生成实例画像文件**

```python
for agent_id, meta in agents.items():
    base = ROOT / ".hermes" / "team" / "agents" / agent_id / "knowledge"
    write_text(base / "expertise.md", f"# {meta['name']} 专长画像\n")
    write_text(base / "delivery-style.md", "# 默认交付风格\n")
```

- [ ] **Step 3: 运行脚本检查实例目录**

Run: `python .tmp_generate_agent_kb.py`
Expected: 13 个实例目录全部生成 `knowledge/` 子目录与 6 个 Markdown 文件

### Task 5: 更新索引文档与兼容入口

**Files:**
- Modify: `.hermes/team/README.md`
- Modify: `.hermes/team/AGENTS.md`
- Modify: `.hermes/agents/README.md`

- [ ] **Step 1: 更新团队目录说明**

```markdown
## 目录结构
- `knowledge/` - 团队公共知识库
```

- [ ] **Step 2: 更新团队知识共享说明**

```markdown
所有 Agent 共享团队知识库：
- `knowledge/status.md`
- `knowledge/project-overview.md`
- `knowledge/patterns/`
```

- [ ] **Step 3: 更新角色知识目录说明**

```markdown
每个 Agent 的 `knowledge/` 采用标准入口：
- `overview.md`
- `playbooks/`
- `checklists/`
```

### Task 6: 自检与清理

**Files:**
- Modify: `.tmp_generate_agent_kb.py`（运行后删除）

- [ ] **Step 1: 运行脚本生成最终文件**

Run: `python .tmp_generate_agent_kb.py`
Expected: 所有目标文件生成完成，无 traceback

- [ ] **Step 2: 检查关键目录与文件数量**

Run: `python -c "from pathlib import Path; root=Path(r'd:\KIMIK2.5\AIAgent'); print((root/'.hermes'/'team'/'knowledge').exists())"`
Expected: 输出 `True`

- [ ] **Step 3: 删除临时生成脚本**

Run: `Remove-Item .tmp_generate_agent_kb.py`
Expected: 临时脚本删除成功

- [ ] **Step 4: 获取诊断并确认无新增问题**

Run: 使用 `GetDiagnostics` 检查更新后的 Markdown 文件
Expected: 无新增诊断错误

- [ ] **Step 5: 提交**

```bash
git add docs/superpowers/plans/2026-05-13-agent-knowledge-base-enrichment.md .hermes/team .hermes/agents
git commit -m "docs: enrich agent knowledge base"
```
