# Agent Knowledge Closure Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有控制平面与调度框架上一次性补齐知识消费、推荐、治理、检索、观测、执行联动、handoff 与质量安全八条主链。

**Architecture:** 采用“兼容式统一知识域层”方案，在 `.hermes/team/control_plane/knowledge/` 下新增统一知识模型与服务，再让 `task_router / workflow_engine / handoff_coordinator / runtime / cli / monitor / executor` 逐步接入。保留现有 `knowledge_recommendation` 对外字段，但内部统一由新的知识域对象生成，避免出现多套语义并存。

**Tech Stack:** Python 3, dataclasses, pathlib, unittest, Markdown, Trae file editing tools

---

### Task 1: 建立统一知识域对象与索引骨架

**Files:**
- Create: `.hermes/team/control_plane/knowledge/__init__.py`
- Create: `.hermes/team/control_plane/knowledge/models.py`
- Create: `.hermes/team/control_plane/knowledge/catalog.py`
- Test: `tests/control_plane/test_knowledge_models.py`

- [ ] **Step 1: 写失败测试，固定知识模型字段**

```python
import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from knowledge.models import KnowledgeProfile, KnowledgeBundle, KnowledgeExcerpt  # noqa: E402


class KnowledgeModelsTests(unittest.TestCase):
    def test_knowledge_bundle_keeps_profile_excerpt_and_usage(self):
        profile = KnowledgeProfile(
            task_type="implementation",
            deliverables=["code", "tests"],
            risk_flags=["regression"],
            owner_agent="backend-1",
            role_key="backend-dev",
            collaboration_mode="handoff",
        )

        excerpt = KnowledgeExcerpt(
            path=".hermes/team/knowledge/workflow-playbook.md",
            resolved_path="D:/repo/.hermes/team/knowledge/workflow-playbook.md",
            summary="use the delivery checklist first",
            excerpt="先补测试，再更新交接摘要。",
            priority=90.0,
            matched_by=["task_type", "risk_flag"],
            tokens_estimate=24,
            expandable=True,
        )

        bundle = KnowledgeBundle(
            profile=profile,
            load_order=["team", "role", "instance"],
            team=[".hermes/team/knowledge/workflow-playbook.md"],
            role=[".hermes/agents/backend-dev/knowledge/checklists/delivery-checklist.md"],
            instance=[".hermes/team/agents/backend-1/knowledge/recent-lessons.md"],
            cross_role=["architect+backend-dev+qa-functional"],
            excerpts=[excerpt],
        )

        self.assertEqual(bundle.profile.owner_agent, "backend-1")
        self.assertEqual(bundle.excerpts[0].priority, 90.0)
        self.assertEqual(bundle.cross_role, ["architect+backend-dev+qa-functional"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_knowledge_models -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbols under `knowledge.models`

- [ ] **Step 3: 实现知识模型与索引骨架**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class KnowledgeProfile:
    task_type: str
    deliverables: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    workflow_id: Optional[str] = None
    step_id: Optional[str] = None
    owner_agent: Optional[str] = None
    role_key: Optional[str] = None
    collaboration_mode: str = "single"
    upstream_agent: Optional[str] = None
    upstream_role: Optional[str] = None
    scope_paths: List[str] = field(default_factory=list)
    module_hints: List[str] = field(default_factory=list)


@dataclass
class KnowledgeExcerpt:
    path: str
    resolved_path: str
    summary: str
    excerpt: str
    priority: float
    matched_by: List[str] = field(default_factory=list)
    tokens_estimate: int = 0
    expandable: bool = True
    degraded_reason: Optional[str] = None


@dataclass
class KnowledgeUsage:
    recommended_paths: List[str] = field(default_factory=list)
    consumed_paths: List[str] = field(default_factory=list)
    expanded_paths: List[str] = field(default_factory=list)
    unused_paths: List[str] = field(default_factory=list)
    decision_helpful_count: int = 0
    risk_helpful_count: int = 0
    feedback_score: float = 0.0


@dataclass
class KnowledgeBundle:
    profile: KnowledgeProfile
    load_order: List[str] = field(default_factory=list)
    team: List[str] = field(default_factory=list)
    role: List[str] = field(default_factory=list)
    instance: List[str] = field(default_factory=list)
    cross_role: List[str] = field(default_factory=list)
    excerpts: List[KnowledgeExcerpt] = field(default_factory=list)
    raw_paths: List[str] = field(default_factory=list)
    missing_paths: List[str] = field(default_factory=list)
    cache_key: Optional[str] = None
    usage: KnowledgeUsage = field(default_factory=KnowledgeUsage)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.control_plane.test_knowledge_models -v`
Expected: PASS

- [ ] **Step 5: 提交这一组骨架改动**

```bash
git add .hermes/team/control_plane/knowledge/__init__.py .hermes/team/control_plane/knowledge/models.py .hermes/team/control_plane/knowledge/catalog.py tests/control_plane/test_knowledge_models.py
git commit -m "feat: add knowledge domain models"
```

### Task 2: 用片段级消费替换整文件预加载

**Files:**
- Create: `.hermes/team/control_plane/knowledge/consumer.py`
- Modify: `.hermes/team/control_plane/runtime/rules.py`
- Modify: `.hermes/team/control_plane/tools/builtin.py`
- Test: `tests/control_plane/test_knowledge_consumer.py`

- [ ] **Step 1: 写失败测试，固定“摘要优先 + 按需展开”行为**

```python
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from knowledge.consumer import build_excerpt_bundle, expand_excerpt_content  # noqa: E402


class KnowledgeConsumerTests(unittest.TestCase):
    def test_build_excerpt_bundle_prioritizes_summary_over_raw_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "delivery-checklist.md"
            file_path.write_text(
                "# Delivery Checklist\n\n- 先补测试\n- 再补回归说明\n- 最后更新 handoff\n",
                encoding="utf-8",
            )

            bundle = build_excerpt_bundle(
                paths=["delivery-checklist.md"],
                resolved_paths=[str(file_path)],
                profile={"task_type": "implementation", "risk_flags": ["regression"]},
            )

            self.assertTrue(bundle["preloaded"])
            self.assertIn("summary", bundle["items"][0])
            self.assertNotIn("content", bundle["items"][0])
            self.assertIn("先补测试", bundle["items"][0]["excerpt"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.control_plane.test_knowledge_consumer -v`
Expected: FAIL because `knowledge.consumer` or expected helper functions do not exist

- [ ] **Step 3: 实现裁剪消费并接入兼容入口**

```python
def preload_knowledge_bundle(bundle: Dict[str, object]) -> Dict[str, object]:
    items = build_excerpt_bundle(
        paths=list(bundle.get("paths", [])),
        resolved_paths=list(bundle.get("resolved_paths", [])),
        profile=bundle.get("profile") or {},
    )["items"]
    loaded = dict(bundle)
    loaded["items"] = items
    loaded["preloaded"] = True
    return loaded


def read_knowledge_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    expand = bool(payload.get("expand"))
    items = list(context.knowledge_bundle.get("items", []))
    if expand:
        records = [expand_excerpt_content(item) for item in items]
    else:
        records = items
    return ToolResult.ok_result(
        content=f"knowledge:{len(records)}",
        structured_data={"items": records},
        artifacts=[item["path"] for item in records],
    )
```

- [ ] **Step 4: 运行消费者测试与现有 tool runtime 测试**

Run: `python -m unittest tests.control_plane.test_knowledge_consumer tests.control_plane.test_executor -v`
Expected: PASS

- [ ] **Step 5: 提交消费链路改动**

```bash
git add .hermes/team/control_plane/knowledge/consumer.py .hermes/team/control_plane/runtime/rules.py .hermes/team/control_plane/tools/builtin.py tests/control_plane/test_knowledge_consumer.py tests/control_plane/test_executor.py
git commit -m "feat: add excerpt-first knowledge consumption"
```

### Task 3: 扩展推荐引擎并引入反馈学习

**Files:**
- Create: `.hermes/team/control_plane/knowledge/recommendation.py`
- Modify: `.hermes/team/调度框架/core/task_router.py`
- Test: `tests/control_plane/test_task_router.py`

- [ ] **Step 1: 写失败测试，固定推荐反馈与组合包行为**

```python
def test_router_returns_cross_role_bundle_and_degrade_reason(self):
    router = router_module.TaskRouter()
    intent = router.analyze_task_intent("架构评审后实现接口并补功能测试")

    recommendation = router._build_knowledge_recommendation(intent, "backend-1")

    self.assertIn("cross_role", recommendation)
    self.assertIn("architect+backend-dev+qa-functional", recommendation["cross_role"])
    self.assertIn("degradations", recommendation)
```

- [ ] **Step 2: 运行单测确认失败**

Run: `python -m unittest tests.control_plane.test_task_router -v`
Expected: FAIL because recommendation payload has no `cross_role` or `degradations`

- [ ] **Step 3: 实现推荐服务并替换 router 内部拼装**

```python
def _build_knowledge_recommendation(self, intent: TaskIntent, agent_id: str) -> Dict[str, object]:
    role_key = self._resolve_role_knowledge_key(agent_id)
    profile = build_router_knowledge_profile(intent, agent_id=agent_id, role_key=role_key)
    return build_recommendation(
        profile=profile,
        role_key=role_key,
        agent_id=agent_id,
        repository_root=repository_root(),
    )
```

- [ ] **Step 4: 运行 router 与 workflow 回归**

Run: `python -m unittest tests.control_plane.test_task_router tests.control_plane.test_workflow_runtime -v`
Expected: PASS

- [ ] **Step 5: 提交推荐能力改动**

```bash
git add .hermes/team/control_plane/knowledge/recommendation.py .hermes/team/调度框架/core/task_router.py tests/control_plane/test_task_router.py tests/control_plane/test_workflow_runtime.py
git commit -m "feat: improve knowledge recommendation scoring"
```

### Task 4: 扩展 TaskCard、Workflow 与 Handoff 的知识联动

**Files:**
- Modify: `.hermes/team/control_plane/models.py`
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Modify: `.hermes/team/调度框架/core/handoff_coordinator.py`
- Modify: `.hermes/team/control_plane/protocols/handoff.py`
- Test: `tests/control_plane/test_workflow_runtime.py`
- Test: `tests/control_plane/test_handoff.py`

- [ ] **Step 1: 写失败测试，固定 TaskCard 与 handoff 强约束字段**

```python
def test_handoff_payload_requires_knowledge_summary_and_next_read(self):
    payload = handoff_module.HandoffPayload.create(
        source_backend="hermes",
        target_backend="openclaw",
        task_id="task-knowledge",
        summary="handoff",
        context={},
        knowledge_recommendation={"team": [".hermes/team/knowledge/status.md"]},
        knowledge_summary="先看状态与风险",
        next_read=[".hermes/team/knowledge/risk-register.md"],
    )

    self.assertTrue(handoff_module.validate_handoff_payload(payload.to_dict()))
```

- [ ] **Step 2: 运行相关测试确认失败**

Run: `python -m unittest tests.control_plane.test_handoff tests.control_plane.test_workflow_runtime -v`
Expected: FAIL because payload and task card do not include the new fields

- [ ] **Step 3: 扩展 TaskCard、workflow step task card 与 handoff payload**

```python
@dataclass
class TaskCard:
    ...
    executor_backend: Optional[str] = None
    knowledge_recommendation: Optional[Dict[str, object]] = None
    knowledge_bundle: Optional[Dict[str, object]] = None
    knowledge_summary: Optional[str] = None
```

```python
payload = HandoffPayload.create(
    ...,
    knowledge_recommendation=knowledge_recommendation,
    knowledge_summary=build_handoff_knowledge_summary(step_context, knowledge_recommendation),
    next_read=build_handoff_next_read(knowledge_recommendation),
)
```

- [ ] **Step 4: 运行 workflow/handoff 回归**

Run: `python -m unittest tests.control_plane.test_workflow_runtime tests.control_plane.test_handoff tests.control_plane.test_handoff_runtime -v`
Expected: PASS

- [ ] **Step 5: 提交执行联动与 handoff 改动**

```bash
git add .hermes/team/control_plane/models.py .hermes/team/调度框架/core/workflow_engine.py .hermes/team/调度框架/core/handoff_coordinator.py .hermes/team/control_plane/protocols/handoff.py tests/control_plane/test_workflow_runtime.py tests/control_plane/test_handoff.py tests/control_plane/test_handoff_runtime.py
git commit -m "feat: thread knowledge bundles through workflow and handoff"
```

### Task 5: 落地治理元数据、人工确认与审计

**Files:**
- Create: `.hermes/team/control_plane/knowledge/governance.py`
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Modify: `.hermes/team/control_plane/cli.py`
- Test: `tests/control_plane/test_governance.py`

- [ ] **Step 1: 写失败测试，固定 review_status 与来源反查**

```python
def test_sync_workflow_feedback_marks_entries_pending_review(self):
    feedback = governance_module.append_governance_entry(
        root=Path(tmp),
        entry_type="decision",
        content="统一使用控制平面批入口",
        owner="architect",
        source_workflow_id="wf-1",
        source_step_id="design",
        source_agent="architect",
    )

    self.assertEqual(feedback["review_status"], "pending_review")
    self.assertEqual(feedback["source_workflow_id"], "wf-1")
```

- [ ] **Step 2: 运行治理测试确认失败**

Run: `python -m unittest tests.control_plane.test_governance -v`
Expected: FAIL because governance helper and review metadata are incomplete

- [ ] **Step 3: 实现治理服务并给 CLI 增加确认入口**

```python
if args.resource == "audit" and args.action in {"accept", "reject", "archive"}:
    result = apply_governance_action(
        knowledge_root=Path(config.directories["knowledge_dir"]),
        action=args.action,
        actor=args.actor,
        entry_id=args.id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result
```

- [ ] **Step 4: 运行治理与 CLI 回归**

Run: `python -m unittest tests.control_plane.test_governance tests.control_plane.test_unified_cli -v`
Expected: PASS

- [ ] **Step 5: 提交治理链路改动**

```bash
git add .hermes/team/control_plane/knowledge/governance.py .hermes/team/调度框架/core/workflow_engine.py .hermes/team/control_plane/cli.py tests/control_plane/test_governance.py tests/control_plane/test_unified_cli.py
git commit -m "feat: add governed knowledge writeback flow"
```

### Task 6: 扩展统一 Query 与全文检索

**Files:**
- Create: `.hermes/team/control_plane/knowledge/query.py`
- Modify: `.hermes/team/control_plane/cli.py`
- Modify: `.hermes/team/control_plane/tools/builtin.py`
- Test: `tests/control_plane/test_knowledge_query.py`
- Test: `tests/control_plane/test_unified_cli.py`

- [ ] **Step 1: 写失败测试，固定过滤、聚合与全文检索行为**

```python
def test_query_supports_agent_role_and_review_status_filters(self):
    result = knowledge_query_module.query_knowledge_records(
        root=self.tmp_path,
        query_text="统一批入口",
        filters={
            "agent": "architect",
            "role": "architect",
            "review_status": "pending_review",
        },
    )

    self.assertIn("records", result)
    self.assertIn("summary", result)
    self.assertIn("aggregations", result)
```

- [ ] **Step 2: 运行 query 测试确认失败**

Run: `python -m unittest tests.control_plane.test_knowledge_query tests.control_plane.test_unified_cli -v`
Expected: FAIL because unified knowledge query is not implemented

- [ ] **Step 3: 实现统一 query 输出并接入 CLI/tool runtime**

```python
query.add_argument("--agent")
query.add_argument("--role")
query.add_argument("--task-type")
query.add_argument("--risk-tag")
query.add_argument("--review-status")
query.add_argument("--search")
```

```python
return ToolResult.ok_result(
    content=f"knowledge-query:{len(result['records'])}",
    structured_data=result,
)
```

- [ ] **Step 4: 运行 query 与 handoff/workflow 查询回归**

Run: `python -m unittest tests.control_plane.test_knowledge_query tests.control_plane.test_unified_cli tests.control_plane.test_workflow_runtime tests.control_plane.test_handoff_runtime -v`
Expected: PASS

- [ ] **Step 5: 提交查询能力改动**

```bash
git add .hermes/team/control_plane/knowledge/query.py .hermes/team/control_plane/cli.py .hermes/team/control_plane/tools/builtin.py tests/control_plane/test_knowledge_query.py tests/control_plane/test_unified_cli.py
git commit -m "feat: add unified knowledge query and search"
```

### Task 7: 深化 dashboard 与 analytics

**Files:**
- Create: `.hermes/team/control_plane/knowledge/analytics.py`
- Modify: `.hermes/team/调度框架/core/monitor.py`
- Test: `tests/control_plane/test_knowledge_analytics.py`
- Test: `tests/control_plane/test_framework_monitor.py`

- [ ] **Step 1: 写失败测试，固定新 dashboard 面板字段**

```python
def test_dashboard_exposes_knowledge_heat_and_pending_counts(self):
    payload = self.monitor.get_dashboard_data()

    self.assertIn("knowledge_heat_ranking", payload)
    self.assertIn("knowledge_consumption_by_agent", payload)
    self.assertIn("unused_recommendations", payload)
    self.assertIn("high_risk_workflow_coverage", payload)
    self.assertIn("pending_governance_counts", payload)
```

- [ ] **Step 2: 运行 monitor 测试确认失败**

Run: `python -m unittest tests.control_plane.test_framework_monitor tests.control_plane.test_knowledge_analytics -v`
Expected: FAIL because monitor payload does not expose the new analytics keys

- [ ] **Step 3: 实现 analytics 聚合并接入 monitor**

```python
payload.update(
    {
        "knowledge_heat_ranking": build_knowledge_heat_ranking(...),
        "knowledge_consumption_by_agent": build_consumption_by_agent(...),
        "unused_recommendations": build_unused_recommendations(...),
        "high_risk_workflow_coverage": build_high_risk_coverage(...),
        "pending_governance_counts": build_pending_governance_counts(...),
    }
)
```

- [ ] **Step 4: 运行 dashboard 回归**

Run: `python -m unittest tests.control_plane.test_framework_monitor tests.control_plane.test_knowledge_analytics tests.control_plane.test_metrics -v`
Expected: PASS

- [ ] **Step 5: 提交 analytics 改动**

```bash
git add .hermes/team/control_plane/knowledge/analytics.py .hermes/team/调度框架/core/monitor.py tests/control_plane/test_knowledge_analytics.py tests/control_plane/test_framework_monitor.py
git commit -m "feat: deepen knowledge analytics dashboard"
```

### Task 8: 让控制平面执行链和 batch runner 真正消费知识摘要

**Files:**
- Modify: `.hermes/team/control_plane/runtime/context.py`
- Modify: `.hermes/team/control_plane/executor.py`
- Modify: `.hermes/team/control_plane/runner.py`
- Test: `tests/control_plane/test_executor.py`
- Test: `tests/control_plane/test_unified_cli.py`

- [ ] **Step 1: 写失败测试，固定 executor 命令上下文带知识摘要**

```python
def test_executor_receives_knowledge_summary_from_task_card(self):
    card = TaskCard(
        ...,
        knowledge_summary="优先补测试，再更新 handoff",
        knowledge_bundle={"next_read": [".hermes/team/knowledge/workflow-playbook.md"]},
    )

    result = self.executor.execute_task(card, self.adapter, self.runner)

    self.assertIn("knowledge_summary", result)
```

- [ ] **Step 2: 运行执行层测试确认失败**

Run: `python -m unittest tests.control_plane.test_executor tests.control_plane.test_unified_cli -v`
Expected: FAIL because executor output has no structured knowledge injection payload

- [ ] **Step 3: 在 context/runner/executor 中统一注入知识摘要**

```python
result["knowledge_summary"] = card.knowledge_summary
result["knowledge_next_read"] = list((card.knowledge_bundle or {}).get("next_read", []))
```

```python
payload["knowledge"] = {
    "summary": card.knowledge_summary,
    "next_read": list((card.knowledge_bundle or {}).get("next_read", [])),
    "raw_paths": list((card.knowledge_bundle or {}).get("paths", [])),
}
```

- [ ] **Step 4: 运行执行链回归**

Run: `python -m unittest tests.control_plane.test_executor tests.control_plane.test_unified_cli tests.control_plane.test_workflow_runtime -v`
Expected: PASS

- [ ] **Step 5: 提交执行联动改动**

```bash
git add .hermes/team/control_plane/runtime/context.py .hermes/team/control_plane/executor.py .hermes/team/control_plane/runner.py tests/control_plane/test_executor.py tests/control_plane/test_unified_cli.py tests/control_plane/test_workflow_runtime.py
git commit -m "feat: inject knowledge summaries into execution chain"
```

### Task 9: 补齐质量、安全与性能基线

**Files:**
- Test: `tests/control_plane/test_validation.py`
- Test: `tests/control_plane/test_knowledge_consumer.py`
- Test: `tests/control_plane/test_knowledge_query.py`
- Test: `tests/control_plane/test_baseline.py`

- [ ] **Step 1: 写失败测试，覆盖坏文件、编码异常、路径越权与大文件裁剪**

```python
def test_read_file_rejects_path_escape(self):
    with self.assertRaises(ValueError):
        read_file_handler(self.context, {"path": "../outside.txt"})


def test_consumer_degrades_on_bad_encoding(self):
    item = build_excerpt_record("bad.md", "bad.md", b"\xff\xfe")
    self.assertEqual(item["degraded_reason"], "decode-error")
```

- [ ] **Step 2: 运行质量测试确认失败**

Run: `python -m unittest tests.control_plane.test_validation tests.control_plane.test_knowledge_consumer tests.control_plane.test_knowledge_query tests.control_plane.test_baseline -v`
Expected: FAIL on missing degradation and benchmark support

- [ ] **Step 3: 实现容错、隔离和 benchmark 输出**

```python
if suspicious_content(text):
    return {
        "path": path,
        "summary": "content isolated due to suspicious markers",
        "excerpt": "",
        "degraded_reason": "isolated-content",
        "expandable": False,
    }
```

```python
baseline["knowledge_query_ms"] = query_cost_ms
baseline["knowledge_preload_ms"] = preload_cost_ms
baseline["dashboard_analytics_ms"] = analytics_cost_ms
```

- [ ] **Step 4: 运行质量与性能回归**

Run: `python -m unittest tests.control_plane.test_validation tests.control_plane.test_knowledge_consumer tests.control_plane.test_knowledge_query tests.control_plane.test_baseline tests.control_plane.test_framework_monitor -v`
Expected: PASS

- [ ] **Step 5: 提交质量与性能改动**

```bash
git add tests/control_plane/test_validation.py tests/control_plane/test_knowledge_consumer.py tests/control_plane/test_knowledge_query.py tests/control_plane/test_baseline.py .hermes/team/control_plane/knowledge/consumer.py .hermes/team/control_plane/knowledge/query.py .hermes/team/调度框架/core/monitor.py
git commit -m "test: cover knowledge safety and performance cases"
```

### Task 10: 收尾验证与文档同步

**Files:**
- Modify: `docs/architecture/control-plane-overview.md`
- Modify: `docs/runtime/handoff-and-continuation.md`
- Modify: `docs/runtime/runtime-governance.md`
- Modify: `docs/contracts/handoff-contract.md`

- [ ] **Step 1: 同步文档中的知识链路说明**

```markdown
- `knowledge/consumer.py` 提供片段级摘要消费与按需展开原文能力。
- `TaskCard`、handoff payload 和 executor 统一共享 `knowledge_summary / next_read / raw_paths` 注入协议。
- query 与 dashboard 基于统一 knowledge analytics，而不是只读 workflow snapshot。
```

- [ ] **Step 2: 跑核心测试集合**

Run: `python -m unittest tests.control_plane.test_knowledge_models tests.control_plane.test_knowledge_consumer tests.control_plane.test_knowledge_query tests.control_plane.test_knowledge_analytics tests.control_plane.test_task_router tests.control_plane.test_workflow_runtime tests.control_plane.test_handoff tests.control_plane.test_handoff_runtime tests.control_plane.test_unified_cli tests.control_plane.test_executor tests.control_plane.test_framework_monitor tests.control_plane.test_governance tests.control_plane.test_validation tests.control_plane.test_baseline -v`
Expected: PASS

- [ ] **Step 3: 获取诊断并修复新增问题**

Run: 使用 `GetDiagnostics` 检查所有新增和修改的 Python/Markdown 文件
Expected: 无新增诊断错误

- [ ] **Step 4: 提交最终收尾**

```bash
git add docs/architecture/control-plane-overview.md docs/runtime/handoff-and-continuation.md docs/runtime/runtime-governance.md docs/contracts/handoff-contract.md
git commit -m "docs: align knowledge closure architecture"
```

## 自检结论

- spec 覆盖：8 类需求都已映射到独立任务，且每个任务都绑定具体文件与测试。
- 占位符扫描：计划中没有 `TBD`、`TODO` 或“后续补齐”型空步骤。
- 类型一致性：`knowledge_recommendation / knowledge_bundle / knowledge_summary / next_read / review_status` 在任务间保持同名。
