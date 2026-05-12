#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Agent 调度框架核心模块

提供:
- 智能任务路由 (task_router)
- Agent间消息总线 (message_bus)
- 工作流引擎 (workflow_engine)
- 监控和故障恢复 (monitor)
"""

from .task_router import TaskRouter, get_router, TaskPriority, TaskType
from .message_bus import MessageBus, get_bus, Message, MessageType, MessagePriority
from .workflow_engine import WorkflowEngine, Workflow, WorkflowStep, StepStatus, StepType
from .monitor import Monitor, RecoveryManager, get_monitor, get_recovery_manager

__all__ = [
    'TaskRouter', 'get_router', 'TaskPriority', 'TaskType',
    'MessageBus', 'get_bus', 'Message', 'MessageType', 'MessagePriority',
    'WorkflowEngine', 'Workflow', 'WorkflowStep', 'StepStatus', 'StepType',
    'Monitor', 'RecoveryManager', 'get_monitor', 'get_recovery_manager'
]

__version__ = "2.0.0"
