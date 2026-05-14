#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流引擎
支持定义、执行和监控复杂的多Agent协作工作流
"""

import ast
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

CONTROL_PLANE_DIR = Path(__file__).resolve().parents[2] / "control_plane"
if str(CONTROL_PLANE_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_DIR))

from config import load_control_plane_config
from knowledge.consumer import build_knowledge_summary, build_next_read
from knowledge.governance import append_governance_entry
from knowledge_feedback import sync_workflow_feedback
from models import LockScope, RetryPolicy, RollbackPolicy, TaskCard, TaskPriority
from observability.metrics import get_metrics_registry
from protocols.handoff import HandoffPayload
from providers.registry import build_default_provider_registry
from runtime.rules import build_knowledge_bundle
from workflow_runtime import WorkflowRunStore


class StepStatus(Enum):
    PENDING = "pending"
    WAITING = "waiting"      # 等待依赖完成
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class StepType(Enum):
    SEQUENTIAL = "sequential"    # 顺序执行
    PARALLEL = "parallel"        # 并行执行
    CONDITIONAL = "conditional"  # 条件执行
    LOOP = "loop"               # 循环执行
    HUMAN = "human"             # 人工审核

@dataclass
class WorkflowStep:
    """工作流步骤"""
    id: str
    name: str
    type: StepType
    agent: Optional[str]           # 指定Agent，None表示自动路由
    task_template: str             # 任务模板
    dependencies: List[str] = field(default_factory=list)
    condition: Optional[str] = None  # 条件表达式（用于CONDITIONAL）
    loop_condition: Optional[str] = None  # 循环条件
    timeout: int = 300             # 超时时间（秒）
    retries: int = 1               # 重试次数
    entry_checks: Dict[str, Any] = field(default_factory=dict)
    required_deliverables: List[str] = field(default_factory=list)
    approval_required: bool = False
    approval_role: Optional[str] = None
    
    # 运行时状态
    status: StepStatus = StepStatus.PENDING
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

@dataclass
class Workflow:
    """工作流定义"""
    id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    variables: Dict[str, Any] = field(default_factory=dict)
    
    # 运行时状态
    status: str = "pending"
    current_step: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    handoffs: List[Dict[str, Any]] = field(default_factory=list)

class WorkflowEngine:
    """
    工作流引擎
    
    特性:
    - 支持顺序、并行、条件、循环等多种执行模式
    - 自动处理步骤依赖关系
    - 支持变量传递和上下文共享
    - 内置超时和重试机制
    - 实时状态监控
    """
    
    def __init__(
        self,
        task_router=None,
        message_bus=None,
        runtime_store=None,
        provider_registry=None,
        control_plane_store=None,
        control_plane_executor=None,
        control_plane_adapter=None,
        command_runner=None,
        knowledge_root=None,
    ):
        self.task_router = task_router
        self.message_bus = message_bus
        self.config = load_control_plane_config()
        if runtime_store is None:
            if self.config.feature_flags.get("workflow_runtime_enabled", False):
                runtime_store = WorkflowRunStore()
        self.runtime_store = runtime_store
        self.provider_registry = provider_registry
        self.control_plane_store = control_plane_store
        self.control_plane_executor = control_plane_executor
        self.control_plane_adapter = control_plane_adapter
        self.command_runner = command_runner
        self.knowledge_root = Path(knowledge_root) if knowledge_root is not None else Path(__file__).resolve().parents[2] / "knowledge"
        self.workflows: Dict[str, Workflow] = {}
        self._executors: Dict[str, ThreadPoolExecutor] = {}
        self._running: Dict[str, bool] = {}
        self._lock = threading.Lock()
        self._active_workflow: Optional[Workflow] = None

    def _can_use_control_plane_execution(self) -> bool:
        return all(
            dependency is not None
            for dependency in (
                self.control_plane_store,
                self.control_plane_executor,
                self.control_plane_adapter,
                self.command_runner,
            )
        )

    def _merge_unique_list(self, target: List[Any], values: List[Any]) -> None:
        """按顺序合并列表并去重。"""
        for value in values:
            if value not in target:
                target.append(value)

    def _default_collaboration_context(self) -> Dict[str, Any]:
        return {
            "artifacts": [],
            "open_questions": [],
            "risks": [],
            "decisions": [],
            "decision_summary_template": "[{step_id}] {summary} | rationale: {rationale} | impact: {impact} | next: {next_action}",
        }

    def _compress_decision(self, step_id: str, decision: Any) -> Dict[str, str]:
        """将 decision 压成稳定模板，避免上下文体积持续膨胀。"""
        if isinstance(decision, dict):
            summary = str(decision.get("summary", "")).strip() or f"{step_id}-decision"
            rationale = str(decision.get("rationale", "n/a")).strip() or "n/a"
            impact = str(decision.get("impact", "n/a")).strip() or "n/a"
            next_action = str(
                decision.get("next_action", decision.get("next", "n/a"))
            ).strip() or "n/a"
        else:
            summary = str(decision).strip()
            rationale = "n/a"
            impact = "n/a"
            next_action = "n/a"
        return {
            "step_id": step_id,
            "decision_summary": (
                f"[{step_id}] {summary} | rationale: {rationale} | "
                f"impact: {impact} | next: {next_action}"
            ),
        }
    
    def register_workflow(self, workflow: Workflow):
        """注册工作流"""
        self.workflows[workflow.id] = workflow
    
    def create_workflow(self, workflow_id: str, name: str, description: str,
                       steps: List[Dict], variables: Dict = None) -> Workflow:
        """
        从配置创建工作流
        
        Args:
            workflow_id: 工作流ID
            name: 名称
            description: 描述
            steps: 步骤配置列表
            variables: 初始变量
        """
        workflow_steps = []
        for i, step_config in enumerate(steps):
            entry_checks = dict(step_config.get("entry_checks") or {})
            step_type = StepType(step_config.get("type", "sequential"))
            approval_role = step_config.get("approval_role", entry_checks.get("approval_role"))
            agent = step_config.get("agent")
            if not agent and step_type == StepType.HUMAN and approval_role == "项目经理":
                agent = "project-manager"
            step = WorkflowStep(
                id=step_config.get("id", f"step_{i}"),
                name=step_config.get("name", f"步骤 {i}"),
                type=step_type,
                agent=agent,
                task_template=step_config.get("task", ""),
                dependencies=step_config.get("dependencies", []),
                condition=step_config.get("condition"),
                loop_condition=step_config.get("loop_condition"),
                timeout=step_config.get("timeout", 300),
                retries=step_config.get("retries", 1),
                entry_checks=entry_checks,
                required_deliverables=list(
                    step_config.get("required_deliverables")
                    or entry_checks.get("required_deliverables", [])
                ),
                approval_required=bool(
                    step_config.get("approval_required", entry_checks.get("approval_required", False))
                ),
                approval_role=approval_role,
            )
            workflow_steps.append(step)
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            steps=workflow_steps,
            variables=variables or {}
        )
        
        self.register_workflow(workflow)
        return workflow
    
    def execute_workflow(self, workflow_id: str, context: Dict = None) -> Dict:
        """
        执行工作流
        
        Args:
            workflow_id: 工作流ID
            context: 执行上下文
            
        Returns:
            执行结果
        """
        if workflow_id not in self.workflows:
            return {"success": False, "error": f"工作流 {workflow_id} 不存在"}
        
        workflow = self.workflows[workflow_id]
        workflow.status = "running"
        workflow.started_at = time.time()
        if self.runtime_store:
            self.runtime_store.record_workflow_started(
                workflow_id,
                {"name": workflow.name, "description": workflow.description},
            )
        
        if context:
            workflow.variables.update(context)
        workflow.variables.setdefault("step_contexts", {})
        workflow.variables.setdefault(
            "collaboration_context",
            self._default_collaboration_context(),
        )
        workflow.handoffs = []
        
        self._running[workflow_id] = True
        
        try:
            # 构建依赖图
            dependency_graph = self._build_dependency_graph(workflow.steps)
            
            # 执行步骤
            completed_steps = set()
            failed_steps = set()
            blocked_steps = set()
            
            while len(completed_steps) + len(failed_steps) + len(blocked_steps) < len(workflow.steps):
                if not self._running.get(workflow_id, False):
                    workflow.status = "cancelled"
                    return {"success": False, "error": "工作流被取消"}
                
                # 找到可以执行的步骤
                ready_steps = self._get_ready_steps(
                    workflow.steps, dependency_graph, 
                    completed_steps, failed_steps
                )
                
                if not ready_steps:
                    if blocked_steps:
                        workflow.status = "blocked"
                        if self.runtime_store:
                            self.runtime_store.record_workflow_completed(
                                workflow_id,
                                {"status": "blocked", "blocked_steps": list(blocked_steps)},
                            )
                        return {
                            "success": False,
                            "error": f"步骤等待阻塞审批或准入条件: {sorted(blocked_steps)}",
                            "blocked_steps": list(blocked_steps),
                            "failed_steps": list(failed_steps),
                        }
                    if failed_steps:
                        workflow.status = "failed"
                        if self.runtime_store:
                            self.runtime_store.record_workflow_completed(
                                workflow_id,
                                {"status": "failed", "failed_steps": list(failed_steps)},
                            )
                        return {"success": False, "error": f"步骤执行失败: {failed_steps}"}
                    break
                
                # 执行就绪的步骤
                for step in ready_steps:
                    if not self._running.get(workflow_id, False):
                        break
                    
                    workflow.current_step = step.id
                    self._execute_step(workflow, step)
                    
                    if step.status == StepStatus.COMPLETED:
                        completed_steps.add(step.id)
                    elif step.status == StepStatus.BLOCKED:
                        blocked_steps.add(step.id)
                    elif step.status == StepStatus.FAILED:
                        failed_steps.add(step.id)
                        if step.retries > 0:
                            # 重试逻辑
                            step.retries -= 1
                            step.status = StepStatus.PENDING
                            failed_steps.discard(step.id)
                    
                    # 更新变量
                    if step.output:
                        workflow.variables[f"{step.id}_output"] = step.output
            
            if blocked_steps:
                workflow.status = "blocked"
            elif failed_steps:
                workflow.status = "failed"
            else:
                workflow.status = "completed"
            workflow.completed_at = time.time()
            knowledge_feedback = self._sync_team_knowledge(workflow)
            knowledge_recommendations = workflow.variables.get("knowledge_recommendations", {})
            knowledge_bundles = {
                step_id: build_knowledge_bundle(recommendation)
                for step_id, recommendation in knowledge_recommendations.items()
                if isinstance(recommendation, dict)
            }
            if self.runtime_store:
                self.runtime_store.record_workflow_completed(
                    workflow_id,
                    {
                        "status": workflow.status,
                        "completed_steps": list(completed_steps),
                        "failed_steps": list(failed_steps),
                        "blocked_steps": list(blocked_steps),
                        "knowledge_recommendations": knowledge_recommendations,
                        "knowledge_bundles": knowledge_bundles,
                        "knowledge_feedback": knowledge_feedback,
                    },
                )
            blocked_error = None
            if blocked_steps:
                for step_id in blocked_steps:
                    step_context = workflow.variables.get("step_contexts", {}).get(step_id, {})
                    if step_context.get("error"):
                        blocked_error = step_context["error"]
                        break

            return {
                "success": not failed_steps and not blocked_steps,
                "workflow_id": workflow_id,
                "completed_steps": list(completed_steps),
                "failed_steps": list(failed_steps),
                "blocked_steps": list(blocked_steps),
                "error": blocked_error,
                "variables": workflow.variables,
                "step_contexts": workflow.variables.get("step_contexts", {}),
                "knowledge_recommendations": knowledge_recommendations,
                "knowledge_bundles": knowledge_bundles,
                "knowledge_feedback": knowledge_feedback,
                "collaboration_context": workflow.variables.get("collaboration_context", {}),
                "handoffs": list(workflow.handoffs),
                "duration": workflow.completed_at - workflow.started_at
            }
            
        except Exception as e:
            workflow.status = "failed"
            workflow.completed_at = time.time()
            if self.runtime_store:
                self.runtime_store.record_workflow_completed(
                    workflow_id,
                    {"status": "failed", "error": str(e)},
                )
            return {"success": False, "error": str(e)}
    
    def _build_dependency_graph(self, steps: List[WorkflowStep]) -> Dict[str, List[str]]:
        """构建依赖图"""
        graph = {}
        for step in steps:
            graph[step.id] = step.dependencies
        return graph
    
    def _get_ready_steps(self, steps: List[WorkflowStep], 
                        dependency_graph: Dict,
                        completed: set, failed: set) -> List[WorkflowStep]:
        """获取可以执行的步骤"""
        ready = []
        for step in steps:
            if step.status != StepStatus.PENDING:
                continue
            
            # 检查依赖是否满足
            deps_satisfied = all(
                dep in completed for dep in dependency_graph.get(step.id, [])
            )
            
            # 检查是否有依赖失败
            deps_failed = any(
                dep in failed for dep in dependency_graph.get(step.id, [])
            )
            
            if deps_failed:
                step.status = StepStatus.SKIPPED
                continue
            
            if deps_satisfied:
                ready.append(step)
        
        return ready
    
    def _execute_step(self, workflow: Workflow, step: WorkflowStep):
        """执行单个步骤"""
        task_content = self._render_template(step.task_template, workflow.variables)
        gate_error = self._validate_entry_checks(workflow, step, workflow.variables)
        if gate_error:
            step.status = StepStatus.BLOCKED
            step.started_at = time.time()
            step.completed_at = step.started_at
            step.error = gate_error
            result = {
                "success": False,
                "error": gate_error,
                "blocked": True,
                "agent": step.agent,
            }
            step_context = self._build_step_context(step, result, task_content)
            self._merge_step_context_into_variables(workflow, step_context)
            if self.runtime_store:
                self.runtime_store.record_step_event(
                    workflow.id,
                    step.id,
                    step.status.value,
                    {"agent": step.agent, "error": step.error, "output": step.output},
                )
            return

        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        if self.runtime_store:
            self.runtime_store.record_step_event(
                workflow.id,
                step.id,
                "running",
                {"agent": step.agent, "task_template": step.task_template},
            )
        
        result = {"success": False, "error": "step did not produce a result"}
        self._active_workflow = workflow
        try:
            inherited_backend = (
                workflow.variables.get("backend_recommendation", {}).get("selected_backend")
                if isinstance(workflow.variables.get("backend_recommendation"), dict)
                else None
            )

            # 根据步骤类型执行
            if step.type == StepType.SEQUENTIAL:
                result = self._execute_agent_task(step, task_content)
            elif step.type == StepType.PARALLEL:
                result = self._execute_parallel_tasks(step, task_content)
            elif step.type == StepType.CONDITIONAL:
                result = self._execute_conditional(step, task_content, workflow.variables)
            elif step.type == StepType.LOOP:
                result = self._execute_loop(step, task_content, workflow.variables)
            elif step.type == StepType.HUMAN:
                result = self._execute_human_review(step, task_content, workflow)
            else:
                result = {"success": False, "error": "未知的步骤类型"}

            if isinstance(result, dict) and inherited_backend:
                result.setdefault("inherited_backend", inherited_backend)
            
            if result.get("success"):
                step.status = StepStatus.COMPLETED
                step.output = result.get("output")
            elif result.get("blocked"):
                step.status = StepStatus.BLOCKED
                step.error = result.get("error")
            else:
                step.status = StepStatus.FAILED
                step.error = result.get("error")
                
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            result = {"success": False, "error": str(e)}
        finally:
            self._active_workflow = None
        
        step.completed_at = time.time()
        step_context = self._build_step_context(step, result, task_content)
        self._merge_step_context_into_variables(workflow, step_context)
        self._record_followup_handoffs(workflow, step, step_context)
        if self.runtime_store:
            self.runtime_store.record_step_event(
                workflow.id,
                step.id,
                step.status.value,
                {"agent": step.agent, "error": step.error, "output": step.output},
            )

    def _validate_entry_checks(self, workflow: Workflow, step: WorkflowStep, variables: Dict[str, Any]) -> Optional[str]:
        """校验 step 准入门槛，失败时返回错误信息。"""
        del workflow
        entry_checks = dict(getattr(step, "entry_checks", {}) or {})
        deliverables = {str(item) for item in variables.get("deliverables", [])}
        quality_gates = dict(variables.get("quality_gates", {}) or {})

        required_deliverables = list(
            entry_checks.get("required_deliverables") or getattr(step, "required_deliverables", [])
        )
        if required_deliverables:
            missing = [name for name in required_deliverables if name not in deliverables]
            if missing:
                return f"missing required deliverables for {step.id}: {', '.join(missing)}"

        coverage_threshold = entry_checks.get("coverage_threshold")
        if coverage_threshold is not None:
            actual_coverage = quality_gates.get("coverage", {})
            if isinstance(coverage_threshold, dict):
                for scope, threshold in coverage_threshold.items():
                    actual = actual_coverage.get(scope)
                    if actual is None or float(actual) < float(threshold):
                        return f"coverage gate failed for {step.id}: {scope}={actual} < {threshold}"
            else:
                actual = actual_coverage if not isinstance(actual_coverage, dict) else actual_coverage.get("overall")
                if actual is None or float(actual) < float(coverage_threshold):
                    return f"coverage gate failed for {step.id}: overall={actual} < {coverage_threshold}"

        test_pass_rate = entry_checks.get("test_pass_rate")
        if test_pass_rate is not None:
            actual_pass_rate = quality_gates.get("test_pass_rate")
            if isinstance(test_pass_rate, dict):
                actual_mapping = actual_pass_rate if isinstance(actual_pass_rate, dict) else {}
                for scope, threshold in test_pass_rate.items():
                    actual = actual_mapping.get(scope)
                    if actual is None or float(actual) < float(threshold):
                        return f"test pass gate failed for {step.id}: {scope}={actual} < {threshold}"
            else:
                actual = actual_pass_rate.get("overall") if isinstance(actual_pass_rate, dict) else actual_pass_rate
                if actual is None or float(actual) < float(test_pass_rate):
                    return f"test pass gate failed for {step.id}: overall={actual} < {test_pass_rate}"

        defect_closure_rate = entry_checks.get("defect_closure_rate")
        if defect_closure_rate is not None:
            actual_closure_rate = quality_gates.get("defect_closure_rate", {})
            if isinstance(defect_closure_rate, dict):
                for scope, threshold in defect_closure_rate.items():
                    actual = actual_closure_rate.get(scope)
                    if actual is None or float(actual) < float(threshold):
                        return f"defect closure gate failed for {step.id}: {scope}={actual} < {threshold}"
            else:
                actual = (
                    actual_closure_rate.get("overall")
                    if isinstance(actual_closure_rate, dict)
                    else actual_closure_rate
                )
                if actual is None or float(actual) < float(defect_closure_rate):
                    return f"defect closure gate failed for {step.id}: overall={actual} < {defect_closure_rate}"

        approval_required = bool(
            getattr(step, "approval_required", False) or entry_checks.get("approval_required", False)
        )
        approval_role = getattr(step, "approval_role", None) or entry_checks.get("approval_role")
        if approval_required and step.type != StepType.HUMAN:
            approvals = dict(variables.get("approvals", {}) or {})
            approval = approvals.get(step.id)
            if not approval:
                return f"approval required for {step.id} by {approval_role or 'reviewer'}"
            if not approval.get("approved"):
                return f"approval rejected for {step.id} by {approval_role or 'reviewer'}"

        return None
    
    def _render_template(self, template: str, variables: Dict) -> str:
        """渲染任务模板"""
        result = template
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result

    def _build_step_context(self, step: WorkflowStep, result: Dict, task_content: str) -> Dict[str, Any]:
        """把步骤执行结果归一化成结构化上下文。"""
        output = result.get("output") if isinstance(result, dict) else result
        summary = output if isinstance(output, str) else task_content
        error = result.get("error") if isinstance(result, dict) else None
        knowledge_recommendation = result.get("knowledge_recommendation") if isinstance(result, dict) else None
        context = {
            "step_id": step.id,
            "agent": result.get("agent", step.agent) if isinstance(result, dict) else step.agent,
            "summary": summary,
            "artifacts": list(result.get("artifacts", [])) if isinstance(result, dict) else [],
            "open_questions": list(result.get("open_questions", [])) if isinstance(result, dict) else [],
            "risks": list(result.get("risks", [])) if isinstance(result, dict) else [],
            "decisions": list(result.get("decisions", [])) if isinstance(result, dict) else [],
            "handoff_hint": result.get("handoff_hint") if isinstance(result, dict) else None,
            "backend_recommendation": result.get("backend_recommendation") if isinstance(result, dict) else None,
            "inherited_backend": result.get("inherited_backend") if isinstance(result, dict) else None,
        }
        if knowledge_recommendation is not None:
            context["knowledge_recommendation"] = knowledge_recommendation
        if error is not None:
            context["error"] = error
        if isinstance(result, dict) and result.get("execution"):
            context["execution"] = dict(result["execution"])
        return context

    def _resolve_step_backend(
        self,
        workflow: Workflow,
        step: WorkflowStep,
        task_result: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        explicit_backend = getattr(step, "backend", None)
        if explicit_backend:
            return explicit_backend
        task_result = task_result or {}
        recommendation = task_result.get("backend_recommendation") or {}
        if recommendation.get("selected_backend"):
            return recommendation["selected_backend"]
        inherited = workflow.variables.get("backend_recommendation", {})
        if isinstance(inherited, dict) and inherited.get("selected_backend"):
            return inherited["selected_backend"]
        return None

    def _build_task_card_for_step(
        self,
        workflow: Workflow,
        step: WorkflowStep,
        task_content: str,
        agent_id: str,
        executor_backend: Optional[str],
        knowledge_recommendation: Optional[Dict[str, Any]] = None,
    ) -> TaskCard:
        knowledge_bundle = (
            build_knowledge_bundle(knowledge_recommendation)
            if isinstance(knowledge_recommendation, dict)
            else None
        )
        knowledge_items = list((knowledge_bundle or {}).get("items", []))
        entry_checks = dict(getattr(step, "entry_checks", {}) or {})
        required_deliverables = list(
            entry_checks.get("required_deliverables") or getattr(step, "required_deliverables", [])
        )
        approval_required = bool(
            getattr(step, "approval_required", False) or entry_checks.get("approval_required", False)
        )
        approval_role = getattr(step, "approval_role", None) or entry_checks.get("approval_role")
        return TaskCard(
            task_id=f"wf-{workflow.id}-{step.id}",
            title=f"Workflow step {step.id}",
            goal=task_content,
            scope=[workflow.id, step.id],
            lock_scope=LockScope(files=[], modules=["workflow"], contracts=[]),
            inputs=["workflow-step"],
            outputs=["stdout", "stderr"],
            dependencies=[],
            owner_agent=agent_id,
            review_agent=agent_id,
            priority=TaskPriority.P1,
            timeout_seconds=max(1, int(step.timeout)),
            retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=[0]),
            rollback_policy=RollbackPolicy(mode="manual"),
            acceptance_criteria=[f"step {step.id} executed"],
            executor_backend=executor_backend,
            knowledge_recommendation=knowledge_recommendation,
            knowledge_bundle=knowledge_bundle,
            knowledge_summary=build_knowledge_summary(knowledge_items) if knowledge_items else None,
            entry_checks=entry_checks,
            required_deliverables=required_deliverables,
            approval_required=approval_required,
            approval_role=approval_role,
        )

    def _execute_via_control_plane(
        self,
        workflow: Workflow,
        step: WorkflowStep,
        task_content: str,
        agent_id: str,
        task_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        inherited_backend = (
            workflow.variables.get("backend_recommendation", {}).get("selected_backend")
            if isinstance(workflow.variables.get("backend_recommendation"), dict)
            else None
        )
        executor_backend = self._resolve_step_backend(workflow, step, task_result) or self.config.default_executor
        knowledge_recommendation = None
        if isinstance(task_result, dict):
            knowledge_recommendation = task_result.get("knowledge_recommendation")
        card = self._build_task_card_for_step(
            workflow,
            step,
            task_content,
            agent_id,
            executor_backend,
            knowledge_recommendation,
        )
        if hasattr(self.control_plane_store, "register_task"):
            try:
                self.control_plane_store.read_snapshot(card.task_id)
            except Exception:
                self.control_plane_store.register_task(card)
        outcome = self.control_plane_executor.execute_task(
            card,
            self.control_plane_adapter,
            self.command_runner,
        )
        error_message = outcome.get("error") or outcome.get("stderr") or None
        return {
            "success": outcome.get("success", False),
            "output": outcome.get("stdout") or task_content,
            "error": error_message,
            "agent": agent_id,
            "backend_recommendation": {"selected_backend": executor_backend},
            "inherited_backend": inherited_backend,
            "execution": {
                "command": outcome.get("command", []),
                "stdout": outcome.get("stdout", ""),
                "stderr": outcome.get("stderr", ""),
                "executor_backend": executor_backend,
            },
        }

    def _merge_step_context_into_variables(self, workflow: Workflow, step_context: Dict[str, Any]) -> None:
        """把步骤上下文写入 workflow 变量，供后续步骤引用。"""
        step_id = step_context["step_id"]
        workflow.variables[f"{step_id}_summary"] = step_context["summary"]
        workflow.variables[f"{step_id}_artifacts"] = list(step_context["artifacts"])
        workflow.variables[f"{step_id}_open_questions"] = list(step_context["open_questions"])
        workflow.variables[f"{step_id}_risks"] = list(step_context["risks"])
        workflow.variables.setdefault("step_contexts", {})[step_id] = step_context
        if step_context.get("backend_recommendation"):
            workflow.variables["backend_recommendation"] = dict(step_context["backend_recommendation"])
        if step_context.get("knowledge_recommendation"):
            workflow.variables.setdefault("knowledge_recommendations", {})[step_id] = dict(
                step_context["knowledge_recommendation"]
            )
        collaboration_context = workflow.variables.setdefault(
            "collaboration_context",
            self._default_collaboration_context(),
        )
        self._merge_unique_list(collaboration_context["artifacts"], list(step_context["artifacts"]))
        self._merge_unique_list(collaboration_context["open_questions"], list(step_context["open_questions"]))
        self._merge_unique_list(collaboration_context["risks"], list(step_context["risks"]))
        decisions = [self._compress_decision(step_id, decision) for decision in step_context["decisions"]]
        self._merge_unique_list(collaboration_context["decisions"], decisions)

    def _publish_handoff_message(self, handoff_payload: Dict[str, Any]) -> None:
        """优先发布标准 handoff 消息，兼容仅支持字典的轻量 bus。"""
        if not self.message_bus:
            return
        if hasattr(self.message_bus, "create_handoff_message"):
            message = self.message_bus.create_handoff_message(
                handoff_payload.get("source_agent"),
                handoff_payload.get("target_agent"),
                handoff_payload.get("task_id"),
                handoff_payload,
            )
            self.message_bus.send(message)
            return
        self.message_bus.send({"type": "handoff", "payload": handoff_payload})

    def _record_followup_handoffs(self, workflow: Workflow, step: WorkflowStep, step_context: Dict[str, Any]) -> None:
        """当后继步骤由其他 agent 负责时，自动生成 handoff。"""
        for index, candidate in enumerate(workflow.steps):
            is_direct_successor = False
            if step.id in candidate.dependencies:
                is_direct_successor = True
            elif index > 0 and workflow.steps[index - 1].id == step.id:
                is_direct_successor = True
            if not is_direct_successor:
                continue
            if candidate.agent == step_context["agent"]:
                continue
            source_backend, selected_backend, backend_candidates, backend_reason = self._resolve_handoff_backend(step_context)
            knowledge_recommendation = self._build_handoff_knowledge_recommendation(
                step_context,
                candidate,
            )
            payload = HandoffPayload.create(
                source_backend=source_backend,
                target_backend=selected_backend,
                task_id=f"{workflow.id}:{step.id}->{candidate.id}",
                summary=step_context["summary"],
                context={"workflow_id": workflow.id, "step_context": step_context},
                source_agent=step_context["agent"],
                target_agent=candidate.agent,
                source_step=step.id,
                target_step=candidate.id,
                reason="workflow-step-transition",
                artifacts=list(step_context["artifacts"]),
                open_questions=list(step_context["open_questions"]),
                risks=list(step_context["risks"]),
                selected_backend=selected_backend,
                backend_candidates=backend_candidates,
                backend_reason=backend_reason,
                review_policy=workflow.variables.get("review_policy"),
                knowledge_recommendation=knowledge_recommendation,
                knowledge_summary=build_knowledge_summary(
                    list(build_knowledge_bundle(knowledge_recommendation).get("items", []))
                )
                if isinstance(knowledge_recommendation, dict)
                else None,
                next_read=build_next_read(
                    list(build_knowledge_bundle(knowledge_recommendation).get("items", []))
                )
                if isinstance(knowledge_recommendation, dict)
                else [],
            )
            handoff_payload = payload.to_dict()
            workflow.handoffs.append(handoff_payload)
            self._publish_handoff_message(handoff_payload)

    def _build_handoff_knowledge_recommendation(
        self,
        step_context: Dict[str, Any],
        candidate: WorkflowStep,
    ) -> Optional[Dict[str, Any]]:
        if self.task_router is None or not candidate.agent:
            return None
        source_agent = step_context.get("agent")
        upstream_role = None
        if source_agent and source_agent in getattr(self.task_router, "agents", {}):
            upstream_role = self.task_router.agents[source_agent].role
        intent = self.task_router.analyze_task_intent(
            candidate.task_template,
            upstream_agent=source_agent,
            upstream_role=upstream_role,
        )
        return self.task_router._build_knowledge_recommendation(intent, candidate.agent)

    def _sync_team_knowledge(self, workflow: Workflow) -> Dict[str, Any]:
        collaboration_context = workflow.variables.get("collaboration_context", {})
        feedback = sync_workflow_feedback(
            self.knowledge_root,
            workflow.id,
            collaboration_context,
        )
        for decision in list(collaboration_context.get("decisions", [])):
            summary = str(decision.get("decision_summary") if isinstance(decision, dict) else decision).strip()
            if summary:
                append_governance_entry(
                    root=self.knowledge_root,
                    entry_type="decision",
                    content=summary,
                    owner="architect",
                    source_workflow_id=workflow.id,
                    source_step_id=decision.get("step_id") if isinstance(decision, dict) else None,
                    source_agent=decision.get("step_id") if isinstance(decision, dict) else None,
                )
        for risk in list(collaboration_context.get("risks", [])):
            risk_text = str(risk).strip()
            if risk_text:
                append_governance_entry(
                    root=self.knowledge_root,
                    entry_type="risk",
                    content=risk_text,
                    owner="qa-functional",
                    source_workflow_id=workflow.id,
                    source_agent="workflow",
                )
        return feedback

    def _resolve_handoff_backend(self, step_context: Dict[str, Any]) -> tuple[str, str, List[str], str]:
        """把步骤建议与真实 provider registry 合并成 handoff backend 元信息。"""
        backend_recommendation = step_context.get("backend_recommendation") or {}
        registry = self.provider_registry or build_default_provider_registry()
        backend_candidates = list(registry.list_providers())
        source_backend = backend_recommendation.get("current_backend") or backend_recommendation.get("source_backend")
        if source_backend not in backend_candidates:
            source_backend = (
                self.config.default_executor
                if self.config.default_executor in backend_candidates
                else (backend_candidates[0] if backend_candidates else "hermes")
            )
        selected_backend = backend_recommendation.get("selected_backend")
        if selected_backend not in backend_candidates:
            selected_backend = (
                self.config.default_executor
                if self.config.default_executor in backend_candidates
                else (backend_candidates[0] if backend_candidates else "hermes")
            )
        provider = registry.get(selected_backend)
        provider_mode = "dry-run" if getattr(provider, "dry_run", False) else "live"
        recommendation_reason = backend_recommendation.get("backend_reason")
        if recommendation_reason:
            backend_reason = (
                f"{recommendation_reason}; source={source_backend}; provider={selected_backend}; "
                f"mode={provider_mode}; registry={','.join(backend_candidates)}"
            )
        else:
            backend_reason = (
                f"selected from provider registry; source={source_backend}; provider={selected_backend}; "
                f"mode={provider_mode}; default={self.config.default_executor}; "
                f"registry={','.join(backend_candidates)}"
            )
        return source_backend, selected_backend, backend_candidates, backend_reason

    def _resolve_upstream_step_context(self, workflow: Workflow, step: WorkflowStep) -> Optional[Dict[str, Any]]:
        """优先从显式依赖中定位 review/handoff 的上游步骤上下文。"""
        step_contexts = workflow.variables.get("step_contexts", {})
        for dependency_id in reversed(step.dependencies):
            dependency_context = step_contexts.get(dependency_id)
            if dependency_context:
                return dependency_context
        for candidate in reversed(workflow.steps):
            if candidate.id == step.id:
                break
            candidate_context = step_contexts.get(candidate.id)
            if candidate_context:
                return candidate_context
        return None
    
    def _execute_agent_task(self, step: WorkflowStep, task_content: str) -> Dict:
        """执行Agent任务"""
        if self.task_router:
            route_kwargs = {}
            if step.agent is None and self._active_workflow is not None:
                upstream_context = self._resolve_upstream_step_context(self._active_workflow, step)
                if upstream_context:
                    route_kwargs["upstream_agent"] = upstream_context.get("agent")
                    upstream_agent = route_kwargs["upstream_agent"]
                    if upstream_agent and upstream_agent in self.task_router.agents:
                        route_kwargs["upstream_role"] = self.task_router.agents[upstream_agent].role
            agent_id, task = self.task_router.route_task(task_content, **route_kwargs)
            if step.agent and step.agent in self.task_router.agents and agent_id != step.agent:
                self.task_router.agents[agent_id].current_tasks = max(
                    0, self.task_router.agents[agent_id].current_tasks - 1
                )
                self.task_router.agents[step.agent].current_tasks += 1
                if hasattr(task, "routing_reason") and isinstance(task.routing_reason, dict):
                    intent = self.task_router.analyze_task_intent(
                        task_content,
                        upstream_agent=route_kwargs.get("upstream_agent"),
                        upstream_role=route_kwargs.get("upstream_role"),
                    )
                    task.routing_reason["knowledge_recommendation"] = (
                        self.task_router._build_knowledge_recommendation(intent, step.agent)
                    )
                task.assigned_agent = step.agent
                agent_id = step.agent
            if step.agent:
                registry = get_metrics_registry()
                registry.inc_counter("improvement_workflow_role_hit_total", 1)
                if agent_id == step.agent:
                    registry.inc_counter("improvement_workflow_role_hit_success_total", 1)
                success = registry._counters.get("improvement_workflow_role_hit_success_total", 0.0)
                total = registry._counters.get("improvement_workflow_role_hit_total", 0.0)
                registry.record_ratio("improvement_workflow_role_hit_ratio", success, total)
            if self._can_use_control_plane_execution() and self._active_workflow is not None:
                return self._execute_via_control_plane(
                    self._active_workflow,
                    step,
                    task_content,
                    agent_id,
                    getattr(task, "routing_reason", None),
                )
            return {
                "success": True,
                "output": f"任务已分配给 {agent_id}: {task_content}",
                "agent": agent_id,
                "backend_recommendation": getattr(task, "routing_reason", {}).get("backend_recommendation"),
                "knowledge_recommendation": getattr(task, "routing_reason", {}).get("knowledge_recommendation"),
            }
        else:
            if self._can_use_control_plane_execution() and self._active_workflow is not None:
                return self._execute_via_control_plane(
                    self._active_workflow,
                    step,
                    task_content,
                    step.agent or "auto",
                )
            return {
                "success": True,
                "output": f"模拟执行: {task_content}",
                "agent": step.agent or "auto"
            }
    
    def _execute_parallel_tasks(self, step: WorkflowStep, task_content: str) -> Dict:
        """并行执行多个子任务"""
        # 解析并行任务（用 | 分隔）
        subtasks = [t.strip() for t in task_content.split("|")]
        
        results = []
        with ThreadPoolExecutor(max_workers=len(subtasks)) as executor:
            futures = {}
            for subtask in subtasks:
                future = executor.submit(self._execute_agent_task, step, subtask)
                futures[future] = subtask
            
            for future in as_completed(futures):
                subtask = futures[future]
                try:
                    result = future.result(timeout=step.timeout)
                    results.append(result)
                except Exception as e:
                    results.append({"success": False, "error": str(e)})
        
        all_success = all(r.get("success") for r in results)
        return {
            "success": all_success,
            "output": results
        }
    
    def _execute_conditional(self, step: WorkflowStep, task_content: str,
                            variables: Dict) -> Dict:
        """条件执行"""
        if not step.condition:
            return self._execute_agent_task(step, task_content)
        
        # 简单条件评估
        condition_met = self._evaluate_condition(step.condition, variables)
        
        if condition_met:
            return self._execute_agent_task(step, task_content)
        else:
            return {
                "success": True,
                "output": "条件不满足，跳过执行"
            }
    
    def _execute_loop(self, step: WorkflowStep, task_content: str,
                     variables: Dict) -> Dict:
        """循环执行"""
        max_iterations = 10
        iterations = 0
        all_results = []
        
        while iterations < max_iterations:
            if step.loop_condition:
                if not self._evaluate_condition(step.loop_condition, variables):
                    break
            
            result = self._execute_agent_task(step, task_content)
            all_results.append(result)
            
            if not result.get("success"):
                break
            
            iterations += 1
        
        return {
            "success": True,
            "output": {
                "iterations": iterations,
                "results": all_results
            }
        }
    
    def _execute_human_review(self, step: WorkflowStep, task_content: str, workflow: Workflow) -> Dict:
        """人工审核步骤"""
        approvals = dict(workflow.variables.get("approvals", {}) or {})
        approval = approvals.get(step.id)
        approval_role = step.approval_role or (step.entry_checks or {}).get("approval_role") or step.agent or "reviewer"
        if approval is None:
            return {
                "success": False,
                "error": f"approval required for {step.id} by {approval_role}",
                "requires_human": True,
                "blocked": True,
                "agent": step.agent,
            }
        if not approval.get("approved"):
            return {
                "success": False,
                "error": f"approval rejected for {step.id} by {approval_role}",
                "requires_human": True,
                "agent": step.agent,
            }
        return {
            "success": True,
            "output": approval.get("comment") or f"审批通过: {task_content}",
            "requires_human": True,
            "agent": step.agent,
        }
    
    def _evaluate_condition(self, condition: str, variables: Dict) -> bool:
        """评估条件表达式"""
        try:
            expr = condition
            for key, value in variables.items():
                expr = expr.replace(f"{{{key}}}", repr(value))

            parsed = ast.parse(expr, mode="eval")
            return bool(self._safe_eval_expr(parsed.body, {"true": True, "false": False}))
        except:
            return False

    def _safe_eval_expr(self, node, names: Dict[str, Any]):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in names:
                return names[node.id]
            raise ValueError(f"unsupported name: {node.id}")
        if isinstance(node, ast.List):
            return [self._safe_eval_expr(item, names) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._safe_eval_expr(item, names) for item in node.elts)
        if isinstance(node, ast.Set):
            return {self._safe_eval_expr(item, names) for item in node.elts}
        if isinstance(node, ast.Dict):
            return {
                self._safe_eval_expr(key, names): self._safe_eval_expr(value, names)
                for key, value in zip(node.keys, node.values)
            }
        if isinstance(node, ast.BoolOp):
            values = [bool(self._safe_eval_expr(value, names)) for value in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
        if isinstance(node, ast.UnaryOp):
            operand = self._safe_eval_expr(node.operand, names)
            if isinstance(node.op, ast.Not):
                return not bool(operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
        if isinstance(node, ast.BinOp):
            left = self._safe_eval_expr(node.left, names)
            right = self._safe_eval_expr(node.right, names)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Mod):
                return left % right
        if isinstance(node, ast.Compare):
            left = self._safe_eval_expr(node.left, names)
            for operator, comparator in zip(node.ops, node.comparators):
                right = self._safe_eval_expr(comparator, names)
                if isinstance(operator, ast.Eq):
                    ok = left == right
                elif isinstance(operator, ast.NotEq):
                    ok = left != right
                elif isinstance(operator, ast.Gt):
                    ok = left > right
                elif isinstance(operator, ast.GtE):
                    ok = left >= right
                elif isinstance(operator, ast.Lt):
                    ok = left < right
                elif isinstance(operator, ast.LtE):
                    ok = left <= right
                elif isinstance(operator, ast.In):
                    ok = left in right
                elif isinstance(operator, ast.NotIn):
                    ok = left not in right
                else:
                    raise ValueError("unsupported comparison operator")
                if not ok:
                    return False
                left = right
            return True
        raise ValueError(f"unsupported expression: {ast.dump(node)}")
    
    def cancel_workflow(self, workflow_id: str):
        """取消工作流执行"""
        self._running[workflow_id] = False
    
    def get_workflow_status(self, workflow_id: str) -> Dict:
        """获取工作流状态"""
        if workflow_id not in self.workflows:
            return {"error": "工作流不存在"}
        
        workflow = self.workflows[workflow_id]
        return {
            "id": workflow.id,
            "name": workflow.name,
            "status": workflow.status,
            "current_step": workflow.current_step,
            "progress": self._calculate_progress(workflow),
            "steps": [
                {
                    "id": step.id,
                    "name": step.name,
                    "status": step.status.value,
                    "duration": (step.completed_at - step.started_at) 
                               if step.completed_at and step.started_at else None
                }
                for step in workflow.steps
            ]
        }
    
    def _calculate_progress(self, workflow: Workflow) -> float:
        """计算工作流进度"""
        if not workflow.steps:
            return 0.0
        
        completed = sum(1 for s in workflow.steps 
                       if s.status in [StepStatus.COMPLETED, StepStatus.SKIPPED])
        return completed / len(workflow.steps)


def workflow_definition_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "workflows"


def default_workflow_definition_path(workflow_id: str = "project_delivery") -> Path:
    return workflow_definition_dir() / f"{workflow_id}.json"


def load_workflow_definition(path: Path | str) -> Dict[str, Any]:
    definition_path = Path(path)
    if not definition_path.is_absolute():
        definition_path = workflow_definition_dir() / definition_path
    if not definition_path.exists():
        raise FileNotFoundError(f"workflow definition not found: {definition_path}")

    suffix = definition_path.suffix.lower()
    raw = definition_path.read_text(encoding="utf-8")
    if suffix == ".json":
        return json.loads(raw)
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise ValueError("YAML workflow support requires PyYAML") from exc
        return yaml.safe_load(raw)
    raise ValueError(f"unsupported workflow definition format: {definition_path.suffix}")


# 预定义的标准工作流
def create_standard_project_workflow(workflow_path: Optional[Path | str] = None) -> List[Dict]:
    """从 workflow 定义文件读取标准项目开发工作流。"""
    definition = load_workflow_definition(workflow_path or default_workflow_definition_path())
    return list(definition.get("steps", []))


if __name__ == "__main__":
    # 测试
    engine = WorkflowEngine()
    
    # 创建工作流
    steps = create_standard_project_workflow()
    workflow = engine.create_workflow(
        "project_v1",
        "标准项目开发",
        "完整的项目开发流程",
        steps,
        {"project_name": "电商平台"}
    )
    
    print(f"工作流创建: {workflow.name}")
    print(f"步骤数: {len(workflow.steps)}")
    print("\n工作流结构:")
    for step in workflow.steps:
        deps = f" (依赖: {', '.join(step.dependencies)})" if step.dependencies else ""
        print(f"  [{step.type.value}] {step.name}{deps}")
