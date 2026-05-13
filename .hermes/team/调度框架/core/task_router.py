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
    
    def route_task(self, content: str, priority: TaskPriority = TaskPriority.NORMAL) -> Tuple[str, Task]:
        """
        智能路由任务到最合适的Agent
        
        Returns:
            (agent_id, task)
        """
        # 1. 分类任务
        task_type = self.classify_task(content)
        
        # 2. 创建任务对象
        task_id = f"task_{int(time.time() * 1000)}"
        task = Task(
            id=task_id,
            type=task_type,
            content=content,
            priority=priority,
            created_at=time.time()
        )
        self.tasks[task_id] = task
        
        # 3. 找到最合适的Agent
        best_agent = None
        best_score = -1
        
        for agent_id, agent in self.agents.items():
            # 跳过已满载的Agent
            if agent.current_tasks >= agent.max_tasks:
                continue
            
            # 计算匹配分数
            score = self.calculate_agent_score(agent, task)
            
            if score > best_score:
                best_score = score
                best_agent = agent_id
        
        if best_agent is None:
            # 所有Agent都满载，选择负载最低的
            best_agent = min(self.agents.keys(), 
                           key=lambda a: self.agents[a].current_tasks)
        
        # 4. 分配任务
        task.assigned_agent = best_agent
        task.status = "assigned"
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
