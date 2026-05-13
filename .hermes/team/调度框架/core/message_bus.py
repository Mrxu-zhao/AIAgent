#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent间消息总线
支持广播、点对点、组播通信模式
"""

import queue
import sys
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

CONTROL_PLANE_DIR = Path(__file__).resolve().parents[2] / "control_plane"
if str(CONTROL_PLANE_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_DIR))

from config import load_control_plane_config
from observability.metrics import get_metrics_registry
from persistent_bus import PersistentMessageBus


class MessageType(Enum):
    TASK_ASSIGN = "task_assign"           # 任务分配
    TASK_COMPLETE = "task_complete"       # 任务完成
    TASK_FAILED = "task_failed"           # 任务失败
    COLLAB_REQUEST = "collab_request"     # 协作请求
    COLLAB_RESPONSE = "collab_response"   # 协作响应
    BROADCAST = "broadcast"               # 广播消息
    STATUS_UPDATE = "status_update"       # 状态更新
    KNOWLEDGE_SHARE = "knowledge_share"   # 知识共享
    HANDOFF = "handoff"                   # 任务交接

class MessagePriority(Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4

@dataclass
class Message:
    """消息实体"""
    id: str
    type: MessageType
    from_agent: str
    to_agent: Optional[str]  # None表示广播
    content: Dict[str, Any]
    priority: MessagePriority
    timestamp: float
    reply_to: Optional[str] = None  # 回复哪条消息
    
    @classmethod
    def create(cls, msg_type: MessageType, from_agent: str, to_agent: Optional[str],
               content: Dict, priority: MessagePriority = MessagePriority.NORMAL,
               reply_to: Optional[str] = None) -> "Message":
        return cls(
            id=str(uuid.uuid4())[:8],
            type=msg_type,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            priority=priority,
            timestamp=time.time(),
            reply_to=reply_to
        )
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "from": self.from_agent,
            "to": self.to_agent,
            "content": self.content,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Message":
        return cls(
            id=payload["id"],
            type=MessageType(payload["type"]),
            from_agent=payload["from"],
            to_agent=payload.get("to"),
            content=payload["content"],
            priority=MessagePriority(payload["priority"]),
            timestamp=payload["timestamp"],
            reply_to=payload.get("reply_to"),
        )

class MessageBus:
    """
    Agent间消息总线
    
    支持:
    - 点对点通信 (P2P)
    - 广播 (Broadcast)
    - 组播 (Group)
    - 消息持久化
    - 消息订阅/发布模式
    """
    
    def __init__(self):
        config = load_control_plane_config()
        self._queues: Dict[str, queue.PriorityQueue] = {}  # Agent消息队列
        self._history: List[Message] = []  # 消息历史
        self._subscribers: Dict[MessageType, List[Callable]] = {}  # 订阅者
        self._groups: Dict[str, List[str]] = {group_id: list(agent_ids) for group_id, agent_ids in config.groups.items()}
        self._lock = Lock()
        self._max_history = 1000
        self._persistent_bus = None
        if config.feature_flags.get("persistent_bus_enabled", False):
            self._persistent_bus = PersistentMessageBus(Path(config.directories["message_bus_dir"]))
    
    def register_agent(self, agent_id: str):
        """注册Agent到消息总线"""
        with self._lock:
            if agent_id not in self._queues:
                self._queues[agent_id] = queue.PriorityQueue()
        if self._persistent_bus:
            self._persistent_bus.register_agent(agent_id)
    
    def unregister_agent(self, agent_id: str):
        """注销Agent"""
        with self._lock:
            if agent_id in self._queues:
                del self._queues[agent_id]
        if self._persistent_bus:
            self._persistent_bus.unregister_agent(agent_id)
    
    def send(self, message: Message) -> bool:
        """
        发送消息
        
        Args:
            message: 消息对象
            
        Returns:
            是否发送成功
        """
        with self._lock:
            # 记录历史
            self._history.append(message)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            
            # 触发订阅者
            self._notify_subscribers(message)
            
            # 分发消息
            if self._persistent_bus:
                success = self._persistent_bus.send(message)
                get_metrics_registry().inc_counter("improvement_cross_process_trace_ratio", 1)
                return success
            if message.to_agent is None:
                # 广播给所有Agent
                success = True
                for agent_id, q in self._queues.items():
                    if agent_id != message.from_agent:
                        try:
                            q.put((message.priority.value, message.timestamp, message))
                        except:
                            success = False
                return success
            elif message.to_agent in self._groups:
                # 组播
                success = True
                for agent_id in self._groups[message.to_agent]:
                    if agent_id in self._queues and agent_id != message.from_agent:
                        try:
                            self._queues[agent_id].put((message.priority.value, message.timestamp, message))
                        except:
                            success = False
                return success
            elif message.to_agent in self._queues:
                # 点对点
                try:
                    self._queues[message.to_agent].put(
                        (message.priority.value, message.timestamp, message)
                    )
                    return True
                except:
                    return False
            else:
                return False
    
    def receive(self, agent_id: str, timeout: float = 0.1) -> Optional[Message]:
        """
        接收消息
        
        Args:
            agent_id: Agent ID
            timeout: 超时时间(秒)
            
        Returns:
            消息对象或None
        """
        if self._persistent_bus:
            message = self._persistent_bus.receive(agent_id)
            if message is None:
                return None
            if isinstance(message, Message):
                return message
            if hasattr(message, "to_dict"):
                return Message.from_dict(message.to_dict())
            return Message.from_dict(message)

        if agent_id not in self._queues:
            return None
        
        try:
            _, _, message = self._queues[agent_id].get(timeout=timeout)
            return message
        except queue.Empty:
            return None
    
    def subscribe(self, msg_type: MessageType, callback: Callable[[Message], None]):
        """订阅特定类型的消息"""
        with self._lock:
            if msg_type not in self._subscribers:
                self._subscribers[msg_type] = []
            self._subscribers[msg_type].append(callback)
    
    def unsubscribe(self, msg_type: MessageType, callback: Callable[[Message], None]):
        """取消订阅"""
        with self._lock:
            if msg_type in self._subscribers:
                self._subscribers[msg_type] = [
                    cb for cb in self._subscribers[msg_type] if cb != callback
                ]
    
    def _notify_subscribers(self, message: Message):
        """通知订阅者"""
        if message.type in self._subscribers:
            for callback in self._subscribers[message.type]:
                try:
                    callback(message)
                except Exception as e:
                    print(f"订阅者回调错误: {e}")
    
    def get_history(self, agent_id: Optional[str] = None, 
                   msg_type: Optional[MessageType] = None,
                   limit: int = 50) -> List[Dict]:
        """获取消息历史"""
        result = self._history
        
        if agent_id:
            result = [m for m in result if m.from_agent == agent_id or m.to_agent == agent_id]
        
        if msg_type:
            result = [m for m in result if m.type == msg_type]
        
        return [m.to_dict() for m in result[-limit:]]
    
    def get_pending_count(self, agent_id: str) -> int:
        """获取Agent待处理消息数"""
        if self._persistent_bus:
            return self._persistent_bus.get_pending_count(agent_id)
        if agent_id not in self._queues:
            return 0
        return self._queues[agent_id].qsize()

    def ack(self, agent_id: str, message_id: str) -> bool:
        """确认消费消息。"""
        if self._persistent_bus:
            return self._persistent_bus.ack(agent_id, message_id)
        return True

    def nack(self, agent_id: str, message_id: str) -> bool:
        """拒绝消费消息。"""
        if self._persistent_bus:
            return self._persistent_bus.nack(agent_id, message_id)
        return False

    def requeue(self, agent_id: str, message_id: str) -> bool:
        """重新入队消息。"""
        if self._persistent_bus:
            return self._persistent_bus.requeue(agent_id, message_id)
        return False

    def list_unacked(self, agent_id: str) -> List[Dict]:
        """列出未确认消息。"""
        if self._persistent_bus:
            return self._persistent_bus.list_unacked(agent_id)
        return []

    def stats(self) -> Dict[str, Any]:
        """返回消息总线的兼容统计快照"""
        if self._persistent_bus:
            persistent_snapshot = self._persistent_bus.stats()
            snapshot = {
                "registered_agents": len(self._queues),
                "history_size": len(self._history),
                "pending_counts": {
                    agent_id: persistent_snapshot.get("pending_counts", {}).get(agent_id, 0)
                    for agent_id in self._queues
                },
                "subscriber_counts": {
                    msg_type.value: len(callbacks)
                    for msg_type, callbacks in self._subscribers.items()
                },
                "groups": {
                    group_id: list(agent_ids)
                    for group_id, agent_ids in self._groups.items()
                },
            }
            return snapshot
        with self._lock:
            pending_counts = {
                agent_id: q.qsize()
                for agent_id, q in self._queues.items()
            }
            subscriber_counts = {
                msg_type.value: len(callbacks)
                for msg_type, callbacks in self._subscribers.items()
            }
            return {
                "registered_agents": len(self._queues),
                "history_size": len(self._history),
                "pending_counts": pending_counts,
                "subscriber_counts": subscriber_counts,
                "groups": {
                    group_id: list(agent_ids)
                    for group_id, agent_ids in self._groups.items()
                },
            }
    
    def create_task_message(self, from_agent: str, to_agent: str, 
                          task_id: str, task_content: str,
                          priority: MessagePriority = MessagePriority.NORMAL) -> Message:
        """创建任务分配消息"""
        return Message.create(
            MessageType.TASK_ASSIGN,
            from_agent,
            to_agent,
            {"task_id": task_id, "content": task_content},
            priority
        )
    
    def create_collab_message(self, from_agent: str, to_agent: str,
                            request_type: str, details: Dict,
                            priority: MessagePriority = MessagePriority.NORMAL) -> Message:
        """创建协作请求消息"""
        return Message.create(
            MessageType.COLLAB_REQUEST,
            from_agent,
            to_agent,
            {"request_type": request_type, "details": details},
            priority
        )
    
    def create_handoff_message(self, from_agent: str, to_agent: str,
                             task_id: str, context: Dict,
                             priority: MessagePriority = MessagePriority.HIGH) -> Message:
        """创建任务交接消息"""
        return Message.create(
            MessageType.HANDOFF,
            from_agent,
            to_agent,
            {"task_id": task_id, "context": context},
            priority
        )


# 单例
_bus = None

def get_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus


if __name__ == "__main__":
    # 测试
    bus = get_bus()
    
    # 注册Agent
    for agent in ["architect", "backend-1", "frontend-1"]:
        bus.register_agent(agent)
    
    # 测试点对点
    msg1 = Message.create(MessageType.TASK_ASSIGN, "architect", "backend-1",
                         {"task": "设计API"}, MessagePriority.HIGH)
    bus.send(msg1)
    
    received = bus.receive("backend-1")
    print(f"收到消息: {received.to_dict() if received else None}")
    
    # 测试广播
    msg2 = Message.create(MessageType.BROADCAST, "architect", None,
                         {"message": "项目启动"}, MessagePriority.NORMAL)
    bus.send(msg2)
    
    print(f"\nbackend-1 待处理: {bus.get_pending_count('backend-1')}")
    print(f"frontend-1 待处理: {bus.get_pending_count('frontend-1')}")
    
    # 测试组播
    msg3 = Message.create(MessageType.TASK_ASSIGN, "architect", "backend",
                         {"task": "后端组任务"}, MessagePriority.NORMAL)
    bus.send(msg3)
    
    print(f"\n组播后 backend-1 待处理: {bus.get_pending_count('backend-1')}")
