#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控和日志系统
实时监控Agent状态、任务执行、系统性能
"""

import json
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

CONTROL_PLANE_DIR = Path(__file__).resolve().parents[2] / "control_plane"
if str(CONTROL_PLANE_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_DIR))

from config import load_control_plane_config
from observability.metrics import get_metrics_registry
from observability.prometheus_exporter import export_metrics_text


@dataclass
class Metric:
    """指标数据"""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)

@dataclass
class Alert:
    """告警信息"""
    id: str
    level: str  # info, warning, critical
    message: str
    agent_id: Optional[str]
    timestamp: float
    resolved: bool = False
    resolved_at: Optional[float] = None

class Monitor:
    """
    监控系统
    
    功能:
    - 实时指标收集
    - 性能监控
    - 异常检测
    - 告警通知
    - 日志聚合
    """
    
    def __init__(self, max_history: int = 10000, task_router=None):
        config = load_control_plane_config()
        self.metrics: Dict[str, deque] = {}
        self.alerts: List[Alert] = []
        self.logs: deque = deque(maxlen=max_history)
        self.task_router = task_router
        self._lock = threading.RLock()
        self._alert_handlers: List[callable] = []
        self._running = False
        self._monitor_thread = None
        
        # 告警阈值配置
        self.thresholds = dict(config.thresholds)

    @property
    def agents(self) -> Dict[str, Any]:
        """兼容旧接口，只读透传 task_router.agents"""
        if self.task_router is None:
            return {}
        return getattr(self.task_router, "agents", {})
    
    def start(self):
        """启动监控"""
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        self.log("INFO", "监控系统已启动")
    
    def stop(self):
        """停止监控"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.log("INFO", "监控系统已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                # 定期检查系统状态
                self._check_system_health()
                time.sleep(30)  # 每30秒检查一次
            except Exception as e:
                self.log("ERROR", f"监控循环异常: {e}")
    
    def _check_system_health(self):
        """检查系统健康状态"""
        # 检查Agent负载
        for metric_name, values in self.metrics.items():
            if metric_name.startswith("agent_load_") and values:
                latest = values[-1].value
                agent_id = metric_name.replace("agent_load_", "")
                
                if latest > self.thresholds["agent_load_high"]:
                    self.create_alert(
                        "warning",
                        f"Agent {agent_id} 负载过高: {latest:.1%}",
                        agent_id
                    )
        
        # 检查错误率
        for metric_name, values in self.metrics.items():
            if metric_name.startswith("error_rate_") and values:
                latest = values[-1].value
                agent_id = metric_name.replace("error_rate_", "")
                
                if latest > self.thresholds["error_rate_high"]:
                    self.create_alert(
                        "critical",
                        f"Agent {agent_id} 错误率过高: {latest:.1%}",
                        agent_id
                    )
    
    def record_metric(self, name: str, value: float, labels: Dict = None):
        """记录指标"""
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = deque(maxlen=1000)
            
            metric = Metric(
                name=name,
                value=value,
                timestamp=time.time(),
                labels=labels or {}
            )
            self.metrics[name].append(metric)
        if name == "agent_load":
            get_metrics_registry().set_gauge("improvement_dashboard_availability_ratio", 1.0)
    
    def record_agent_metric(self, agent_id: str, metric_type: str, value: float):
        """记录Agent相关指标"""
        metric_name = f"{metric_type}_{agent_id}"
        self.record_metric(metric_name, value, {"agent": agent_id})
    
    def create_alert(self, level: str, message: str, agent_id: Optional[str] = None):
        """创建告警"""
        alert = Alert(
            id=f"alert_{int(time.time() * 1000)}",
            level=level,
            message=message,
            agent_id=agent_id,
            timestamp=time.time()
        )
        
        with self._lock:
            self.alerts.append(alert)
        
        # 触发告警处理器
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.log("ERROR", f"告警处理器异常: {e}")
        
        self.log(level, f"[ALERT] {message}", agent_id)
        return alert
    
    def resolve_alert(self, alert_id: str):
        """解决告警"""
        with self._lock:
            for alert in self.alerts:
                if alert.id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = time.time()
                    self.log("INFO", f"告警已解决: {alert.message}", alert.agent_id)
                    return True
        return False
    
    def log(self, level: str, message: str, agent_id: Optional[str] = None):
        """记录日志"""
        log_entry = {
            "timestamp": time.time(),
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message,
            "agent_id": agent_id
        }
        
        with self._lock:
            self.logs.append(log_entry)
        
        # 同时输出到控制台
        prefix = f"[{log_entry['datetime']}] [{level}]"
        if agent_id:
            prefix += f" [{agent_id}]"
        print(f"{prefix} {message}")
    
    def register_alert_handler(self, handler: callable):
        """注册告警处理器"""
        self._alert_handlers.append(handler)
    
    def get_metrics(self, name: Optional[str] = None, 
                   start_time: Optional[float] = None,
                   end_time: Optional[float] = None) -> List[Dict]:
        """获取指标数据"""
        with self._lock:
            if name:
                if name not in self.metrics:
                    return []
                metrics = list(self.metrics[name])
            else:
                metrics = []
                for m_list in self.metrics.values():
                    metrics.extend(m_list)
            
            # 时间过滤
            if start_time:
                metrics = [m for m in metrics if m.timestamp >= start_time]
            if end_time:
                metrics = [m for m in metrics if m.timestamp <= end_time]
            
            return [
                {
                    "name": m.name,
                    "value": m.value,
                    "timestamp": m.timestamp,
                    "labels": m.labels
                }
                for m in metrics
            ]
    
    def get_alerts(self, level: Optional[str] = None, 
                  resolved: Optional[bool] = None,
                  agent_id: Optional[str] = None) -> List[Dict]:
        """获取告警列表"""
        with self._lock:
            alerts = self.alerts
            
            if level:
                alerts = [a for a in alerts if a.level == level]
            if resolved is not None:
                alerts = [a for a in alerts if a.resolved == resolved]
            if agent_id:
                alerts = [a for a in alerts if a.agent_id == agent_id]
            
            return [
                {
                    "id": a.id,
                    "level": a.level,
                    "message": a.message,
                    "agent_id": a.agent_id,
                    "timestamp": a.timestamp,
                    "resolved": a.resolved,
                    "resolved_at": a.resolved_at
                }
                for a in alerts
            ]
    
    def get_logs(self, level: Optional[str] = None,
                agent_id: Optional[str] = None,
                limit: int = 100) -> List[Dict]:
        """获取日志"""
        with self._lock:
            logs = list(self.logs)
            
            if level:
                logs = [l for l in logs if l["level"] == level]
            if agent_id:
                logs = [l for l in logs if l["agent_id"] == agent_id]
            
            return logs[-limit:]
    
    def get_dashboard_data(self) -> Dict:
        """获取仪表盘数据"""
        with self._lock:
            # 计算统计信息
            total_alerts = len(self.alerts)
            unresolved_alerts = len([a for a in self.alerts if not a.resolved])
            critical_alerts = len([a for a in self.alerts if a.level == "critical" and not a.resolved])
            
            # Agent负载
            agent_loads = {}
            for name, values in self.metrics.items():
                if name.startswith("agent_load_") and values:
                    agent_id = name.replace("agent_load_", "")
                    agent_loads[agent_id] = values[-1].value
            
            payload = {
                "summary": {
                    "total_alerts": total_alerts,
                    "unresolved_alerts": unresolved_alerts,
                    "critical_alerts": critical_alerts,
                    "total_logs": len(self.logs)
                },
                "agent_loads": agent_loads,
                "recent_alerts": self.get_alerts(resolved=False)[:5],
                "recent_logs": self.get_logs(limit=10)
            }
            get_metrics_registry().set_gauge("improvement_dashboard_availability_ratio", 1.0)
            get_metrics_registry().set_gauge("improvement_high_risk_issues_total", float(critical_alerts))
            return payload
    
    def export_metrics(self, filepath: str):
        """导出指标到文件"""
        data = {
            "metrics": self.get_metrics(),
            "alerts": self.get_alerts(),
            "logs": self.get_logs(limit=1000)
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.log("INFO", f"指标已导出到: {filepath}")

    def export_prometheus_metrics(self) -> str:
        """导出 Prometheus 文本格式指标。"""
        return export_metrics_text()


class RecoveryManager:
    """
    故障恢复管理器
    
    功能:
    - 任务失败自动重试
    - Agent故障转移
    - 状态恢复
    - 优雅降级
    """
    
    def __init__(self, task_router=None, monitor=None):
        self.task_router = task_router
        self.monitor = monitor
        self._retry_policies: Dict[str, Dict] = {}
        self._failure_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def set_retry_policy(self, agent_id: str, max_retries: int = 3, 
                        backoff_factor: float = 2.0):
        """设置重试策略"""
        self._retry_policies[agent_id] = {
            "max_retries": max_retries,
            "backoff_factor": backoff_factor,
            "current_retries": 0
        }
    
    def handle_task_failure(self, agent_id: str, task_id: str, 
                           error: str) -> Dict:
        """处理任务失败"""
        with self._lock:
            if agent_id not in self._failure_counts:
                self._failure_counts[agent_id] = 0
            self._failure_counts[agent_id] += 1
        
        # 记录告警
        if self.monitor:
            self.monitor.create_alert(
                "warning",
                f"Agent {agent_id} 任务失败: {error}",
                agent_id
            )
        
        # 检查是否需要重试
        policy = self._retry_policies.get(agent_id, {})
        max_retries = policy.get("max_retries", 3)
        current_failures = self._failure_counts.get(agent_id, 0)
        
        if current_failures < max_retries:
            # 计算退避时间
            backoff = policy.get("backoff_factor", 2.0) ** current_failures
            
            return {
                "action": "retry",
                "delay": backoff,
                "reason": f"将在 {backoff:.1f} 秒后重试 (第 {current_failures} 次)"
            }
        else:
            # 超过重试次数，进行故障转移
            return self._failover(agent_id, task_id)
    
    def _failover(self, failed_agent_id: str, task_id: str) -> Dict:
        """故障转移到其他Agent"""
        # 重置失败计数
        self._failure_counts[failed_agent_id] = 0
        
        # 标记Agent为不健康
        if self.monitor:
            self.monitor.create_alert(
                "critical",
                f"Agent {failed_agent_id} 连续失败，触发故障转移",
                failed_agent_id
            )
        
        # 尝试重新路由任务
        if self.task_router:
            # 临时降低该Agent的评分
            if failed_agent_id in self.task_router.agents:
                self.task_router.agents[failed_agent_id].success_rate *= 0.5
            
            return {
                "action": "failover",
                "from_agent": failed_agent_id,
                "reason": "任务将重新路由到其他Agent"
            }
        
        return {
            "action": "escalate",
            "reason": "需要人工介入处理"
        }
    
    def reset_failure_count(self, agent_id: str):
        """重置失败计数"""
        with self._lock:
            self._failure_counts[agent_id] = 0
    
    def get_health_status(self) -> Dict:
        """获取健康状态"""
        return {
            agent_id: {
                "failure_count": count,
                "healthy": count < self._retry_policies.get(agent_id, {}).get("max_retries", 3)
            }
            for agent_id, count in self._failure_counts.items()
        }


# 单例
_monitor = None
_recovery = None

def get_monitor() -> Monitor:
    global _monitor
    if _monitor is None:
        _monitor = Monitor()
    return _monitor

def get_recovery_manager(task_router=None) -> RecoveryManager:
    global _recovery
    if _recovery is None:
        _recovery = RecoveryManager(task_router)
    return _recovery


if __name__ == "__main__":
    # 测试
    monitor = get_monitor()
    monitor.start()
    
    # 模拟记录一些指标
    for i in range(10):
        monitor.record_agent_metric("backend-1", "agent_load", 0.3 + i * 0.05)
        monitor.record_agent_metric("backend-1", "error_rate", 0.01 * i)
        time.sleep(0.1)
    
    # 模拟高负载
    monitor.record_agent_metric("backend-1", "agent_load", 0.9)
    
    # 等待监控循环检查
    time.sleep(2)
    
    # 查看仪表盘
    dashboard = monitor.get_dashboard_data()
    print("\n=== 仪表盘数据 ===")
    print(json.dumps(dashboard, ensure_ascii=False, indent=2))
    
    monitor.stop()
