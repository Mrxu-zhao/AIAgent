#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能任务路由器
根据任务类型、Agent负载、技能匹配度自动分配任务
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONTROL_PLANE_DIR = Path(__file__).resolve().parents[2] / "control_plane"
if str(CONTROL_PLANE_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_DIR))

from config import load_control_plane_config


class TaskPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4

class TaskType(Enum):
    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    DATABASE = "database"
    BACKEND = "backend"
    FRONTEND = "frontend"
    UCD = "ucd"
    QA_FUNCTIONAL = "qa_functional"
    QA_PERFORMANCE = "qa_performance"
    DEVOPS = "devops"
    UNKNOWN = "unknown"

@dataclass
class Agent:
    id: str
    name: str
    role: str
    skills: List[str] = field(default_factory=list)
    current_tasks: int = 0
    max_tasks: int = 3
    last_active: float = 0
    success_rate: float = 1.0
    avg_response_time: float = 0


@dataclass
class TaskIntent:
    task_type: TaskType
    requested_agent: Optional[str] = None
    requested_role: Optional[str] = None
    collaboration_mode: str = "single"
    review_policy: str = "none"
    upstream_agent: Optional[str] = None
    upstream_role: Optional[str] = None
    deliverables: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)



@dataclass
class Task:
    id: str
    type: TaskType
    content: str
    priority: TaskPriority
    dependencies: List[str] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    status: str = "pending"  # pending, assigned, running, completed, failed
    created_at: float = 0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    intent: Dict[str, object] = field(default_factory=dict)
    routing_reason: Dict[str, object] = field(default_factory=dict)

class TaskRouter:
    """智能任务路由器"""

    def __init__(self):
        self.config = load_control_plane_config()
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self._init_agents()
    
    def _init_agents(self):
        """初始化Agent配置"""
        for agent_id, agent_config in self.config.agents.items():
            self.agents[agent_id] = Agent(
                id=agent_id,
                name=agent_config.name,
                role=agent_config.role,
                skills=list(agent_config.skills),
                max_tasks=agent_config.max_tasks,
            )
    
    def classify_task(self, content: str) -> TaskType:
        """根据内容自动分类任务类型"""
        content_lower = content.lower()
        scores = {task_type: 0 for task_type in TaskType}
        
        keyword_mapping = {
            TaskType.REQUIREMENTS: self.config.task_keywords.get("requirements", []),
            TaskType.ARCHITECTURE: self.config.task_keywords.get("architecture", []),
            TaskType.DATABASE: self.config.task_keywords.get("database", []),
            TaskType.BACKEND: self.config.task_keywords.get("backend", []),
            TaskType.FRONTEND: self.config.task_keywords.get("frontend", []),
            TaskType.UCD: self.config.task_keywords.get("ucd", []),
            TaskType.QA_FUNCTIONAL: self.config.task_keywords.get("qa_functional", []),
            TaskType.QA_PERFORMANCE: self.config.task_keywords.get("qa_performance", []),
            TaskType.DEVOPS: self.config.task_keywords.get("devops", []),
        }

        for task_type, keywords in keyword_mapping.items():
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    scores[task_type] += 1
        
        # 返回得分最高的类型
        best_match = max(scores, key=scores.get)
        return best_match if scores[best_match] > 0 else TaskType.UNKNOWN

    def analyze_task_intent(
        self,
        content: str,
        upstream_agent: Optional[str] = None,
        upstream_role: Optional[str] = None,
    ) -> TaskIntent:
        """提取任务中的显式指派、协作模式与交付物信号。"""
        content_lower = content.lower()
        task_type = self.classify_task(content)
        requested_agent = None
        requested_role = None
        matched_keywords = []

        for alias, agent_id in self.config.aliases.items():
            if alias.lower() in content_lower:
                requested_agent = agent_id
                requested_role = self.agents[agent_id].role
                break

        deliverables = []
        deliverable_mapping = {
            "spec": ("spec", "设计文档", "方案"),
            "test": ("测试", "test", "用例"),
            "review": ("review", "评审", "验收"),
            "code": ("代码", "实现", "接口"),
        }
        for deliverable, keywords in deliverable_mapping.items():
            if any(keyword.lower() in content_lower for keyword in keywords):
                deliverables.append(deliverable)

        collaboration_mode = "single"
        if any(keyword in content_lower for keyword in ("review", "评审", "验收")):
            collaboration_mode = "review"
        elif any(keyword in content_lower for keyword in ("handoff", "交接", "移交")):
            collaboration_mode = "handoff"
        elif any(keyword in content_lower for keyword in ("并行", "parallel")):
            collaboration_mode = "parallel"

        risk_flags = []
        if any(keyword in content_lower for keyword in ("线上", "生产", "critical", "高风险", "风险")):
            risk_flags.append("critical")
        if any(keyword in content_lower for keyword in ("性能", "performance")):
            risk_flags.append("performance")

        for keyword_list in self.config.task_keywords.values():
            matched_keywords.extend([keyword for keyword in keyword_list if keyword.lower() in content_lower])

        return TaskIntent(
            task_type=task_type,
            requested_agent=requested_agent,
            requested_role=requested_role,
            collaboration_mode=collaboration_mode,
            review_policy="soft-prefer-reviewer" if collaboration_mode == "review" else "none",
            upstream_agent=upstream_agent,
            upstream_role=upstream_role,
            deliverables=deliverables,
            risk_flags=risk_flags,
            keywords=matched_keywords,
        )

    def _reviewer_candidate_pool(self, intent: TaskIntent) -> List[str]:
        """返回 review 任务的优先候选池。"""
        if "performance" in intent.risk_flags:
            return ["qa-performance", "qa-functional"]
        return ["qa-functional", "qa-performance"]

    def _build_backend_recommendation(self, intent: TaskIntent) -> Dict[str, str]:
        """为后续执行层提供稳定的 backend 建议。"""
        if intent.collaboration_mode == "review":
            return {
                "selected_backend": "openclaw",
                "backend_reason": "review tasks prefer openclaw when external execution is acceptable",
            }
        return {
            "selected_backend": "hermes",
            "backend_reason": "default to hermes for local execution",
        }

    def _resolve_role_knowledge_key(self, agent_id: str) -> str:
        """把实例 agent 映射到角色知识目录。"""
        if agent_id.startswith("backend-"):
            return "backend-dev"
        if agent_id.startswith("frontend-"):
            return "frontend-dev"
        return agent_id

    def _build_knowledge_recommendation(self, intent: TaskIntent, agent_id: str) -> Dict[str, object]:
        """为执行层和协作层提供稳定的知识加载建议。"""
        role_key = self._resolve_role_knowledge_key(agent_id)
        team_paths = [
            ".hermes/team/knowledge/status.md",
            ".hermes/team/knowledge/project-overview.md",
            ".hermes/team/knowledge/workflow-playbook.md",
        ]
        if intent.task_type == TaskType.REQUIREMENTS or "spec" in intent.deliverables:
            team_paths.append(".hermes/team/knowledge/domain-glossary.md")
        if intent.collaboration_mode != "single":
            team_paths.append(".hermes/team/knowledge/handoff-templates.md")
        if intent.risk_flags:
            team_paths.append(".hermes/team/knowledge/risk-register.md")

        role_paths = [
            f".hermes/agents/{role_key}/knowledge/status.md",
            f".hermes/agents/{role_key}/knowledge/overview.md",
            f".hermes/agents/{role_key}/knowledge/playbooks/common-tasks.md",
            f".hermes/agents/{role_key}/knowledge/checklists/delivery-checklist.md",
        ]
        if intent.collaboration_mode in {"review", "handoff"}:
            role_paths.append(f".hermes/agents/{role_key}/knowledge/checklists/design-checklist.md")

        instance_paths = [
            f".hermes/team/agents/{agent_id}/knowledge/expertise.md",
            f".hermes/team/agents/{agent_id}/knowledge/owned-modules.md",
            f".hermes/team/agents/{agent_id}/knowledge/delivery-style.md",
        ]
        if intent.collaboration_mode != "single":
            instance_paths.append(f".hermes/team/agents/{agent_id}/knowledge/collaboration-preferences.md")

        return {
            "load_order": ["team", "role", "instance"],
            "team": team_paths,
            "role": role_paths,
            "instance": instance_paths,
        }

    def select_best_agent(self, intent: TaskIntent, priority: TaskPriority) -> Tuple[str, Dict[str, object]]:
        """根据任务画像选择最合适的 Agent，并返回可解释原因。"""
        backend_recommendation = self._build_backend_recommendation(intent)
        if intent.requested_agent and intent.requested_agent in self.agents:
            knowledge_recommendation = self._build_knowledge_recommendation(
                intent,
                intent.requested_agent,
            )
            return intent.requested_agent, {
                "strategy": "explicit-agent",
                "requested_agent": intent.requested_agent,
                "collaboration_mode": intent.collaboration_mode,
                "priority": priority.name,
                "backend_recommendation": backend_recommendation,
                "knowledge_recommendation": knowledge_recommendation,
            }

        excluded_agents = []
        if intent.upstream_agent:
            excluded_agents.append(intent.upstream_agent)
        excluded_roles = []
        if intent.upstream_role:
            excluded_roles.append(intent.upstream_role)

        if intent.collaboration_mode == "review":
            candidate_pool = self._reviewer_candidate_pool(intent)
            for candidate_id in candidate_pool:
                if candidate_id not in self.agents or candidate_id in excluded_agents:
                    continue
                candidate = self.agents[candidate_id]
                if candidate.role in excluded_roles:
                    continue
                if candidate.current_tasks < candidate.max_tasks:
                    knowledge_recommendation = self._build_knowledge_recommendation(
                        intent,
                        candidate_id,
                    )
                    return candidate_id, {
                        "strategy": "reviewer-preferred",
                        "review_policy": intent.review_policy,
                        "fallback_used": False,
                        "candidate_pool": candidate_pool,
                        "excluded_agents": excluded_agents,
                        "excluded_roles": excluded_roles,
                        "priority": priority.name,
                        "backend_recommendation": backend_recommendation,
                        "knowledge_recommendation": knowledge_recommendation,
                    }

        task = Task(
            id="intent-selection",
            type=intent.task_type,
            content="",
            priority=priority,
        )
        best_agent = None
        best_score = -1.0
        for agent_id, agent in self.agents.items():
            if agent.current_tasks >= agent.max_tasks:
                continue
            if agent_id in excluded_agents:
                continue
            if agent.role in excluded_roles:
                continue
            score = self.calculate_agent_score(agent, task)
            if intent.requested_role and agent.role == intent.requested_role:
                score += 50
            if intent.collaboration_mode == "review" and "qa" in agent_id:
                score += 20
            if score > best_score:
                best_score = score
                best_agent = agent_id

        if best_agent is None:
            best_agent = min(self.agents.keys(), key=lambda agent_id: self.agents[agent_id].current_tasks)

        knowledge_recommendation = self._build_knowledge_recommendation(intent, best_agent)
        return best_agent, {
            "strategy": "scored-selection",
            "collaboration_mode": intent.collaboration_mode,
            "review_policy": intent.review_policy,
            "fallback_used": intent.collaboration_mode == "review",
            "candidate_pool": self._reviewer_candidate_pool(intent) if intent.collaboration_mode == "review" else [],
            "excluded_agents": excluded_agents,
            "excluded_roles": excluded_roles,
            "priority": priority.name,
            "backend_recommendation": backend_recommendation,
            "knowledge_recommendation": knowledge_recommendation,
        }
    
    def calculate_agent_score(self, agent: Agent, task: Task) -> float:
        """计算Agent与任务的匹配分数"""
        score = 0.0
        
        # 1. 技能匹配度 (0-40分)
        if task.type.value in agent.skills:
            score += 40
        
        # 2. 负载情况 (0-30分) - 当前任务越少分数越高
        load_ratio = agent.current_tasks / agent.max_tasks
        score += max(0, 30 * (1 - load_ratio))
        
        # 3. 成功率 (0-20分)
        score += 20 * agent.success_rate
        
        # 4. 响应时间 (0-10分) - 响应越快分数越高
        if agent.avg_response_time > 0:
            score += max(0, 10 * (1 - min(agent.avg_response_time / 60, 1)))
        else:
            score += 10
        
        return score
    
    def route_task(
        self,
        content: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        upstream_agent: Optional[str] = None,
        upstream_role: Optional[str] = None,
    ) -> Tuple[str, Task]:
        """
        智能路由任务到最合适的Agent
        
        Returns:
            (agent_id, task)
        """
        # 1. 分析任务画像
        intent = self.analyze_task_intent(
            content,
            upstream_agent=upstream_agent,
            upstream_role=upstream_role,
        )
        task_type = intent.task_type
        
        # 2. 创建任务对象
        task_id = f"task_{int(time.time() * 1000)}"
        task = Task(
            id=task_id,
            type=task_type,
            content=content,
            priority=priority,
            created_at=time.time(),
            intent={
                "task_type": intent.task_type.value,
                "requested_agent": intent.requested_agent,
                "requested_role": intent.requested_role,
                "collaboration_mode": intent.collaboration_mode,
                "review_policy": intent.review_policy,
                "upstream_agent": intent.upstream_agent,
                "upstream_role": intent.upstream_role,
                "deliverables": list(intent.deliverables),
                "risk_flags": list(intent.risk_flags),
                "keywords": list(intent.keywords),
            },
        )
        self.tasks[task_id] = task

        # 3. 找到最合适的Agent
        best_agent, routing_reason = self.select_best_agent(intent, priority)
        
        # 4. 分配任务
        task.assigned_agent = best_agent
        task.status = "assigned"
        task.routing_reason = routing_reason
        self.agents[best_agent].current_tasks += 1
        
        return best_agent, task
    
    def complete_task(self, task_id: str, success: bool = True):
        """完成任务，更新Agent状态"""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        task.status = "completed" if success else "failed"
        task.completed_at = time.time()
        
        if task.assigned_agent and task.assigned_agent in self.agents:
            agent = self.agents[task.assigned_agent]
            agent.current_tasks = max(0, agent.current_tasks - 1)
            agent.last_active = time.time()
            
            # 更新成功率 (指数移动平均)
            agent.success_rate = 0.9 * agent.success_rate + 0.1 * (1.0 if success else 0.0)
            
            # 更新平均响应时间
            if task.started_at:
                duration = task.completed_at - task.started_at
                if agent.avg_response_time == 0:
                    agent.avg_response_time = duration
                else:
                    agent.avg_response_time = 0.7 * agent.avg_response_time + 0.3 * duration
    
    def get_agent_status(self) -> Dict:
        """获取所有Agent状态"""
        return {
            agent_id: {
                "name": agent.name,
                "role": agent.role,
                "current_tasks": agent.current_tasks,
                "max_tasks": agent.max_tasks,
                "load": f"{agent.current_tasks}/{agent.max_tasks}",
                "success_rate": f"{agent.success_rate:.1%}",
                "status": "🟢 空闲" if agent.current_tasks == 0 else 
                         "🟡 忙碌" if agent.current_tasks < agent.max_tasks else "🔴 满载"
            }
            for agent_id, agent in self.agents.items()
        }
    
    def get_task_queue(self) -> List[Dict]:
        """获取任务队列状态"""
        return [
            {
                "id": task.id,
                "type": task.type.value,
                "priority": task.priority.name,
                "status": task.status,
                "assigned_to": task.assigned_agent,
                "content": task.content[:50] + "..." if len(task.content) > 50 else task.content
            }
            for task in sorted(self.tasks.values(), 
                             key=lambda t: (t.priority.value, t.created_at))
        ]

    def resolve_agent_alias(self, alias: str) -> str:
        """从统一配置中心解析 Agent 别名。"""
        return self.config.aliases.get(alias, alias)


# 单例模式
_router = None

def get_router() -> TaskRouter:
    global _router
    if _router is None:
        _router = TaskRouter()
    return _router


if __name__ == "__main__":
    # 测试
    router = get_router()
    
    # 测试任务分类和路由
    test_tasks = [
        "设计用户模块的数据库表结构",
        "开发用户登录接口",
        "设计首页UI原型",
        "编写用户模块的单元测试",
        "分析订单模块的需求",
    ]
    
    print("=== 智能任务路由测试 ===\n")
    for task_content in test_tasks:
        agent_id, task = router.route_task(task_content)
        agent = router.agents[agent_id]
        print(f"任务: {task_content}")
        print(f"  分类: {task.type.value}")
        print(f"  分配给: {agent.name} ({agent.role})")
        print(f"  当前负载: {agent.current_tasks}/{agent.max_tasks}")
        print()
    
    print("\n=== Agent状态 ===")
    for agent_id, status in router.get_agent_status().items():
        print(f"{status['name']}: {status['load']} {status['status']}")
