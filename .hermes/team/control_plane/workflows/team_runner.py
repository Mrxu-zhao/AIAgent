from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflows.executor import execute_role_workflow


@dataclass(frozen=True)
class TeamWorkflowStage:
    workflow_id: str
    role: str
    stage_name: str


DEFAULT_TEAM_STAGES = [
    TeamWorkflowStage("requirements-analysis", "requirements-analyst", "需求分析"),
    TeamWorkflowStage("architect-design-review", "architect", "架构设计"),
    TeamWorkflowStage("dba-table-design", "dba", "数据库设计"),
    TeamWorkflowStage("ucd-interaction-design", "ucd", "UCD设计"),
    TeamWorkflowStage("backend-api-development", "backend-dev", "后端开发"),
    TeamWorkflowStage("frontend-page-development", "frontend-dev", "前端开发"),
    TeamWorkflowStage("qa-test-case-design", "qa-functional", "功能测试"),
    TeamWorkflowStage("devops-deployment", "devops", "部署上线"),
]


class TeamWorkflowRunner:
    def __init__(self, stages: Optional[List[TeamWorkflowStage]] = None):
        self.stages = list(stages or DEFAULT_TEAM_STAGES)

    def run(
        self,
        feature: str,
        context_values: Optional[Dict[str, Any]] = None,
        cwd: Optional[Path] = None,
        knowledge_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        base_context = self._build_base_context(feature, context_values or {})
        stage_results: List[Dict[str, Any]] = []
        for index, stage in enumerate(self.stages, start=1):
            stage_context = dict(base_context)
            stage_context.update(self._context_for_stage(stage.workflow_id, base_context))
            result = execute_role_workflow(
                stage.workflow_id,
                context_values=stage_context,
                cwd=cwd,
                knowledge_root=knowledge_root,
            )
            self._materialize_handoff_files(result, stage_context, cwd)
            quality_report = dict(result.get("quality_report") or {})
            quality_summary = dict(quality_report.get("summary") or {})
            stage_results.append(
                {
                    "index": index,
                    "stage_name": stage.stage_name,
                    "workflow_id": stage.workflow_id,
                    "role": stage.role,
                    "ok": bool(result.get("ok")),
                    "quality_status": quality_report.get("overall_status"),
                    "quality_failed": int(quality_summary.get("failed", 0)),
                    "result": result,
                }
            )
        return {
            "feature": feature,
            "mode": "team-delivery",
            "stages": [
                {
                    "index": item["index"],
                    "stage_name": item["stage_name"],
                    "workflow_id": item["workflow_id"],
                    "role": item["role"],
                    "ok": item["ok"],
                    "quality_status": item["quality_status"],
                    "quality_failed": item["quality_failed"],
                }
                for item in stage_results
            ],
            "summary": self._build_summary(stage_results),
            "quality_gate_summary": self._build_quality_gate_summary(stage_results),
            "action_items": self._build_action_items(stage_results),
            "stage_results": [item["result"] for item in stage_results],
        }

    def _build_base_context(self, feature: str, context_values: Dict[str, Any]) -> Dict[str, Any]:
        context = dict(context_values)
        context.setdefault("feature", feature)
        context.setdefault("Feature", feature.replace("-", " ").title().replace(" ", ""))
        context.setdefault("background", f"{context['Feature']} 需要支持端到端交付")
        context.setdefault(
            "api_spec",
            (
                f"Endpoint: /api/{feature}/register\n"
                "Method: POST\n"
                f"Request: {context['Feature']} payload\n"
                f"Response: {context['Feature']} result"
            ),
        )
        context.setdefault(
            "columns",
            [
                {"name": "name", "type": "VARCHAR(128)", "required": True, "comment": "名称"},
                {"name": "status", "type": "VARCHAR(32)", "required": True, "comment": "状态"},
            ],
        )
        context.setdefault("platform", "web")
        context.setdefault("app_type", "spring-boot")
        context.setdefault("port", 8080)
        return context

    def _context_for_stage(self, workflow_id: str, base_context: Dict[str, Any]) -> Dict[str, Any]:
        if workflow_id == "frontend-page-development":
            return {"platform": base_context.get("platform", "web")}
        if workflow_id == "devops-deployment":
            return {
                "app_type": base_context.get("app_type", "spring-boot"),
                "port": base_context.get("port", 8080),
            }
        return {}

    def _materialize_handoff_files(
        self,
        result: Dict[str, Any],
        context_values: Dict[str, Any],
        cwd: Optional[Path],
    ) -> None:
        root = Path(cwd).resolve() if cwd else Path.cwd().resolve()
        feature = str(context_values.get("feature") or "feature")
        deliverables = dict(result.get("deliverables") or {})
        files_to_write = {
            f"requirements/{feature}.md": deliverables.get("prd_doc"),
            f"architecture/{feature}.md": deliverables.get("design_doc"),
            f"api/{feature}.md": deliverables.get("api_doc"),
            f"design/{feature}.md": deliverables.get("design_doc"),
            f"deploy/{feature}.md": deliverables.get("deployment_config"),
        }
        for relative_path, content in files_to_write.items():
            if not content:
                continue
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")

    def _build_summary(self, stage_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "total_stages": len(stage_results),
            "successful_stages": sum(1 for item in stage_results if item["ok"]),
            "failed_stages": sum(1 for item in stage_results if not item["ok"]),
            "quality_fail_stage_count": sum(1 for item in stage_results if item["quality_failed"] > 0),
        }

    def _build_quality_gate_summary(self, stage_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = 0
        failed = 0
        passed = 0
        for item in stage_results:
            quality_report = dict(item["result"].get("quality_report") or {})
            summary = dict(quality_report.get("summary") or {})
            total += int(summary.get("total_gates", 0))
            failed += int(summary.get("failed", 0))
            passed += int(summary.get("passed", 0))
        return {
            "total_gates": total,
            "passed": passed,
            "failed": failed,
        }

    def _build_action_items(self, stage_results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        for item in stage_results:
            quality_report = dict(item["result"].get("quality_report") or {})
            for gate in list(quality_report.get("results") or []):
                if gate.get("status") != "fail":
                    continue
                items.append(
                    {
                        "stage": item["stage_name"],
                        "role": item["role"],
                        "gate": str(gate.get("gate_name") or ""),
                        "message": str(gate.get("message") or ""),
                    }
                )
        return items
