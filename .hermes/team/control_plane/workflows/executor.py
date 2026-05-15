from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

from delivery.quality_gate import QualityGateChecker
from governance.tool_permissions import is_role_tool_allowed
from knowledge_loop import ExperienceExtractor, KnowledgeUpdater
from runtime.rules import repository_root
from stacks.registry import get_stack_config
from tools.builtin import build_default_tool_registry
from tools.executor import ToolExecutor
from tools.spec import ToolExecutionContext
from workflows.models import RoleWorkflow
from workflows.resolver import WorkflowValueResolver

ROLE_CONTRACT_ALIASES = {
    "backend-dev": "backend",
    "frontend-dev": "frontend",
    "requirements-analyst": "analyst",
}


class RoleWorkflowExecutor:
    def __init__(
        self,
        cwd: Optional[Path] = None,
        knowledge_root: Optional[Path] = None,
        registry=None,
        tool_executor: Optional[ToolExecutor] = None,
        quality_checker: Optional[QualityGateChecker] = None,
        extractor: Optional[ExperienceExtractor] = None,
        updater: Optional[KnowledgeUpdater] = None,
    ):
        self.cwd = Path(cwd) if cwd else repository_root()
        self.registry = registry or build_default_tool_registry()
        self.tool_executor = tool_executor or ToolExecutor()
        self.quality_checker = quality_checker or QualityGateChecker()
        self.extractor = extractor or ExperienceExtractor()
        self.updater = updater or KnowledgeUpdater(
            knowledge_root=str(knowledge_root) if knowledge_root else None
        )

    def execute_from_definition(
        self,
        definition: Dict[str, Any],
        context_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        workflow = RoleWorkflow.from_dict(definition)
        return self.execute(workflow, context_values or {})

    def execute(self, workflow: RoleWorkflow, context_values: Dict[str, Any]) -> Dict[str, Any]:
        context_data = dict(context_values)
        context_data.setdefault("feature", "")
        if "Feature" not in context_data and context_data.get("feature"):
            context_data["Feature"] = str(context_data["feature"]).replace("-", " ").title().replace(" ", "")
        resolver = WorkflowValueResolver(context_data)
        execution_context = self._build_context(workflow, context_data)
        stack_info = self._resolve_stack(workflow, context_data)
        step_results = []
        for step in workflow.steps:
            payload = resolver.resolve_value(step.input)
            if not is_role_tool_allowed(workflow.role, step.tool):
                result_dict = {
                    "ok": False,
                    "content": "",
                    "structured_data": None,
                    "error": f"ROLE_TOOL_FORBIDDEN:{workflow.role}:{step.tool}",
                    "artifacts": [],
                }
            else:
                tool = self.registry.get(step.tool)
                self._prepare_context_knowledge(execution_context, payload)
                result = self.tool_executor.execute_many(execution_context, [(tool, payload)])[0]
                result_dict = result.to_dict()
            step_payload = {
                "step_id": step.step_id,
                "name": step.name,
                "tool": step.tool,
                "input": payload,
                **result_dict,
            }
            resolver.register_step_result(step.step_id, step_payload)
            step_results.append(step_payload)
        quality_report = self.quality_checker.check(
            self._normalize_contract_role(workflow.role),
            self._build_deliverables(step_results),
        ).to_dict()
        knowledge_feedback = self._update_knowledge(workflow, quality_report)
        return {
            "ok": all(item["ok"] for item in step_results),
            "workflow_id": workflow.workflow_id,
            "role": workflow.role,
            "stack": stack_info,
            "steps": step_results,
            "quality_report": quality_report,
            "knowledge_feedback": knowledge_feedback,
        }

    def _build_context(self, workflow: RoleWorkflow, context_values: Dict[str, Any]) -> ToolExecutionContext:
        backend = str(context_values.get("backend") or "hermes")
        actor = str(context_values.get("actor") or "admin")
        return ToolExecutionContext(
            task_id=f"role-workflow-{workflow.workflow_id}-{int(time.time() * 1000)}",
            agent_id=workflow.role,
            backend=backend,
            cwd=str(self.cwd),
            actor=actor,
            knowledge_bundle={},
        )

    def _prepare_context_knowledge(
        self,
        execution_context: ToolExecutionContext,
        payload: Dict[str, Any],
    ) -> None:
        paths = list(payload.get("paths") or [])
        resolved_paths = [str((self.cwd / Path(path)).resolve()) for path in paths]
        execution_context.knowledge_bundle = {
            "paths": paths,
            "resolved_paths": resolved_paths,
        }

    def _build_deliverables(self, step_results: list[Dict[str, Any]]) -> Dict[str, Any]:
        code_outputs = [
            item.get("content", "")
            for item in step_results
            if item.get("tool", "").startswith("generate_") or item.get("tool") == "write_file"
        ]
        return {
            "coverage": 100 if all(item.get("ok") for item in step_results) else 0,
            "code": "\n\n".join(text for text in code_outputs if text),
            "api_docs": [artifact for item in step_results for artifact in item.get("artifacts", [])],
            "review_comments": [],
        }

    def _resolve_stack(self, workflow: RoleWorkflow, context_values: Dict[str, Any]) -> Dict[str, Any]:
        selection = dict(workflow.stack_selection or {})
        stack_id = context_values.get("stack") or selection.get("default")
        if not stack_id:
            return {}
        category = self._infer_stack_category(workflow.role)
        config = get_stack_config(category, str(stack_id))
        return {
            "category": category,
            "stack_id": str(stack_id),
            "name": config.name,
            "templates_dir": config.templates_dir,
            "commands": dict(config.commands),
            "file_extensions": list(config.file_extensions),
        }

    def _update_knowledge(self, workflow: RoleWorkflow, quality_report: Dict[str, Any]) -> Dict[str, Any]:
        records = self.extractor.extract_from_quality_report(
            workflow.role,
            workflow.workflow_id,
            quality_report,
        )
        unique = self.extractor.deduplicate(records)
        update_result = self.updater.update_role_knowledge(workflow.role, unique)
        lesson_result = self.updater.append_lessons(
            workflow.role,
            [record.title for record in unique],
        )
        return {
            "records": [record.to_dict() for record in unique],
            "updated_files": update_result.get("updated_files", []),
            "recent_lessons_path": lesson_result.get("path"),
            "lessons": [record.title for record in unique],
        }

    def _normalize_contract_role(self, role: str) -> str:
        return ROLE_CONTRACT_ALIASES.get(role, role)

    def _infer_stack_category(self, role: str) -> str:
        if role in {"backend-dev", "architect", "devops"}:
            return "backend"
        if role in {"frontend-dev", "ucd", "analyst", "requirements-analyst"}:
            return "frontend"
        if role in {"dba", "qa-functional", "qa-performance"}:
            return "database"
        return "backend"


def build_role_workflow_executor(
    cwd: Optional[Path] = None,
    knowledge_root: Optional[Path] = None,
) -> RoleWorkflowExecutor:
    return RoleWorkflowExecutor(cwd=cwd, knowledge_root=knowledge_root)


def execute_role_workflow(
    workflow_id: str,
    context_values: Optional[Dict[str, Any]] = None,
    cwd: Optional[Path] = None,
    knowledge_root: Optional[Path] = None,
):
    from workflows.loader import WorkflowLoader

    definition = WorkflowLoader().load(workflow_id)
    executor = build_role_workflow_executor(cwd=cwd, knowledge_root=knowledge_root)
    return executor.execute_from_definition(definition, context_values or {})
