#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流引擎
支持定义、执行和监控复杂的多Agent协作工作流
"""

import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class StepStatus(Enum):
    PENDING = "pending"
    WAITING = "waiting"      # 等待依赖完成
    RUNNING = "running"
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
    
    def __init__(self, task_router=None, message_bus=None):
        self.task_router = task_router
        self.message_bus = message_bus
        self.workflows: Dict[str, Workflow] = {}
        self._executors: Dict[str, ThreadPoolExecutor] = {}
        self._running: Dict[str, bool] = {}
        self._lock = threading.Lock()
    
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
            step = WorkflowStep(
                id=step_config.get("id", f"step_{i}"),
                name=step_config.get("name", f"步骤 {i}"),
                type=StepType(step_config.get("type", "sequential")),
                agent=step_config.get("agent"),
                task_template=step_config.get("task", ""),
                dependencies=step_config.get("dependencies", []),
                condition=step_config.get("condition"),
                loop_condition=step_config.get("loop_condition"),
                timeout=step_config.get("timeout", 300),
                retries=step_config.get("retries", 1)
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
        
        if context:
            workflow.variables.update(context)
        
        self._running[workflow_id] = True
        
        try:
            # 构建依赖图
            dependency_graph = self._build_dependency_graph(workflow.steps)
            
            # 执行步骤
            completed_steps = set()
            failed_steps = set()
            
            while len(completed_steps) + len(failed_steps) < len(workflow.steps):
                if not self._running.get(workflow_id, False):
                    workflow.status = "cancelled"
                    return {"success": False, "error": "工作流被取消"}
                
                # 找到可以执行的步骤
                ready_steps = self._get_ready_steps(
                    workflow.steps, dependency_graph, 
                    completed_steps, failed_steps
                )
                
                if not ready_steps:
                    if failed_steps:
                        workflow.status = "failed"
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
            
            workflow.status = "completed" if not failed_steps else "failed"
            workflow.completed_at = time.time()
            
            return {
                "success": not failed_steps,
                "workflow_id": workflow_id,
                "completed_steps": list(completed_steps),
                "failed_steps": list(failed_steps),
                "variables": workflow.variables,
                "duration": workflow.completed_at - workflow.started_at
            }
            
        except Exception as e:
            workflow.status = "failed"
            workflow.completed_at = time.time()
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
        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        
        try:
            # 渲染任务模板
            task_content = self._render_template(step.task_template, workflow.variables)
            
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
                result = self._execute_human_review(step, task_content)
            else:
                result = {"success": False, "error": "未知的步骤类型"}
            
            if result.get("success"):
                step.status = StepStatus.COMPLETED
                step.output = result.get("output")
            else:
                step.status = StepStatus.FAILED
                step.error = result.get("error")
                
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
        
        step.completed_at = time.time()
    
    def _render_template(self, template: str, variables: Dict) -> str:
        """渲染任务模板"""
        result = template
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
    
    def _execute_agent_task(self, step: WorkflowStep, task_content: str) -> Dict:
        """执行Agent任务"""
        if self.task_router:
            agent_id, task = self.task_router.route_task(task_content)
            if step.agent and step.agent in self.task_router.agents and agent_id != step.agent:
                self.task_router.agents[agent_id].current_tasks = max(
                    0, self.task_router.agents[agent_id].current_tasks - 1
                )
                self.task_router.agents[step.agent].current_tasks += 1
                task.assigned_agent = step.agent
                agent_id = step.agent
            # 这里可以集成实际的Agent调用
            return {
                "success": True,
                "output": f"任务已分配给 {agent_id}: {task_content}",
                "agent": agent_id
            }
        else:
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
    
    def _execute_human_review(self, step: WorkflowStep, task_content: str) -> Dict:
        """人工审核步骤"""
        # 在实际实现中，这里会发送通知等待人工确认
        return {
            "success": True,
            "output": f"等待人工审核: {task_content}",
            "requires_human": True
        }
    
    def _evaluate_condition(self, condition: str, variables: Dict) -> bool:
        """评估条件表达式"""
        try:
            # 安全地评估条件
            allowed_names = {"true": True, "false": False}
            allowed_names.update(variables)
            
            # 替换变量占位符
            expr = condition
            for key, value in variables.items():
                expr = expr.replace(f"{{{key}}}", repr(value))
            
            return eval(expr, {"__builtins__": {}}, allowed_names)
        except:
            return False
    
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


# 预定义的标准工作流
def create_standard_project_workflow() -> List[Dict]:
    """创建标准项目开发工作流"""
    return [
        {
            "id": "requirements",
            "name": "需求分析",
            "type": "sequential",
            "agent": "requirements-analyst",
            "task": "分析项目需求，输出需求文档"
        },
        {
            "id": "architecture",
            "name": "架构设计",
            "type": "sequential",
            "agent": "architect",
            "task": "基于需求文档设计系统架构",
            "dependencies": ["requirements"]
        },
        {
            "id": "database",
            "name": "数据库设计",
            "type": "sequential",
            "agent": "dba",
            "task": "设计数据库表结构",
            "dependencies": ["architecture"]
        },
        {
            "id": "ucd",
            "name": "UI/UX设计",
            "type": "sequential",
            "agent": "ucd",
            "task": "设计用户界面和交互",
            "dependencies": ["requirements"]
        },
        {
            "id": "backend_dev",
            "name": "后端开发",
            "type": "parallel",
            "agent": "backend",
            "task": "开发后端API | 实现业务逻辑 | 编写单元测试",
            "dependencies": ["architecture", "database"]
        },
        {
            "id": "frontend_dev",
            "name": "前端开发",
            "type": "parallel",
            "agent": "frontend",
            "task": "开发页面组件 | 实现页面交互 | 对接后端API",
            "dependencies": ["ucd", "backend_dev"]
        },
        {
            "id": "qa",
            "name": "测试",
            "type": "parallel",
            "agent": "qa",
            "task": "功能测试 | 性能测试",
            "dependencies": ["frontend_dev"]
        },
        {
            "id": "deploy",
            "name": "部署上线",
            "type": "sequential",
            "agent": "devops",
            "task": "部署到生产环境",
            "dependencies": ["qa"]
        }
    ]


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
