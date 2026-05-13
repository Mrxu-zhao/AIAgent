from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class AgentConfig:
    id: str
    name: str
    role: str
    max_tasks: int
    skills: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)


@dataclass
class ControlPlaneConfig:
    task_keywords: Dict[str, List[str]]
    agents: Dict[str, AgentConfig]
    groups: Dict[str, List[str]]
    thresholds: Dict[str, float]
    executors: Dict[str, Dict[str, object]]
    directories: Dict[str, str]
    feature_flags: Dict[str, bool]
    sensitive_actions: List[str]
    aliases: Dict[str, str]
    default_executor: str = "hermes"

    def to_dict(self) -> Dict[str, object]:
        return {
            "task_keywords": self.task_keywords,
            "agents": {
                agent_id: {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "max_tasks": agent.max_tasks,
                    "skills": list(agent.skills),
                    "aliases": list(agent.aliases),
                }
                for agent_id, agent in self.agents.items()
            },
            "groups": self.groups,
            "thresholds": self.thresholds,
            "executors": self.executors,
            "directories": self.directories,
            "feature_flags": self.feature_flags,
            "sensitive_actions": self.sensitive_actions,
            "aliases": self.aliases,
            "default_executor": self.default_executor,
        }


def _control_plane_root() -> Path:
    return Path(__file__).resolve().parent


def _default_directories() -> Dict[str, str]:
    root = _control_plane_root()
    return {
        "state_dir": str(root / "state"),
        "events_dir": str(root / "events"),
        "artifacts_dir": str(root / "artifacts"),
        "message_bus_dir": str(root / "state" / "message_bus"),
        "workflow_runtime_dir": str(root / "state" / "workflow_runtime"),
        "audit_log": str(root / "artifacts" / "audit-log.jsonl"),
    }


def _build_default_agents() -> Dict[str, AgentConfig]:
    raw = [
        ("requirements-analyst", "吴雪梅", "需求分析师", 2, ["requirements"], ["需求", "吴雪梅"]),
        ("architect", "张欣怡", "系统架构师", 2, ["architecture"], ["架构师", "张欣怡"]),
        ("dba", "周嘉诚", "数据库设计师", 3, ["database"], ["dba", "周嘉诚"]),
        ("backend-1", "陈启明", "后端开发", 3, ["backend"], ["后端", "后端1", "陈启明"]),
        ("backend-2", "王浩然", "后端开发", 3, ["backend"], ["后端2", "王浩然"]),
        ("backend-3", "赵文杰", "后端开发", 3, ["backend"], ["后端3", "赵文杰"]),
        ("frontend-1", "李思雨", "前端开发", 3, ["frontend"], ["前端", "前端1", "李思雨"]),
        ("frontend-2", "周晓明", "前端开发", 3, ["frontend"], ["前端2", "周晓明"]),
        ("frontend-3", "林雅婷", "前端开发", 3, ["frontend"], ["前端3", "林雅婷"]),
        ("ucd", "吴俊杰", "UCD设计师", 2, ["ucd"], ["ucd", "吴俊杰"]),
        ("qa-functional", "郑晓彤", "功能测试", 4, ["qa_functional"], ["测试", "郑晓彤"]),
        ("qa-performance", "孙美玲", "性能测试", 3, ["qa_performance"], ["性能", "孙美玲"]),
        ("devops", "黄志远", "运维", 3, ["devops"], ["运维", "黄志远"]),
    ]
    return {
        agent_id: AgentConfig(
            id=agent_id,
            name=name,
            role=role,
            max_tasks=max_tasks,
            skills=skills,
            aliases=aliases,
        )
        for agent_id, name, role, max_tasks, skills, aliases in raw
    }


def _build_aliases(agents: Dict[str, AgentConfig]) -> Dict[str, str]:
    aliases = {}
    for agent_id, agent in agents.items():
        aliases[agent_id] = agent_id
        for alias in agent.aliases:
            aliases[alias] = agent_id
    aliases["测试组"] = "qa-functional"
    return aliases


def _default_payload() -> Dict[str, object]:
    agents = _build_default_agents()
    return {
        "task_keywords": {
            "requirements": ["需求", "分析", "调研", "用户故事", "prd", "requirement"],
            "architecture": ["架构", "设计", "技术选型", "架构图", "architecture"],
            "database": ["数据库", "表设计", "sql", "索引", "mysql", "redis"],
            "backend": ["后端", "接口", "api", "服务", "controller", "service", "dao", "java", "spring"],
            "frontend": ["前端", "页面", "组件", "ui", "vue", "react", "html", "css", "js"],
            "ucd": ["设计", "原型", "交互", "ux", "figma", "mockup"],
            "qa_functional": ["测试", "用例", "bug", "功能测试", "回归", "test", "qa"],
            "qa_performance": ["性能", "压测", "jmeter", "tps", "并发", "performance"],
            "devops": ["部署", "docker", "k8s", "jenkins", "ci/cd", "运维", "服务器", "devops"],
        },
        "agents": agents,
        "groups": {
            "backend": ["backend-1", "backend-2", "backend-3"],
            "frontend": ["frontend-1", "frontend-2", "frontend-3"],
            "qa": ["qa-functional", "qa-performance"],
            "design": ["architect", "dba", "ucd"],
            "dev": ["backend-1", "backend-2", "backend-3", "frontend-1", "frontend-2", "frontend-3"],
            "all": list(agents.keys()),
        },
        "thresholds": {
            "agent_load_high": 0.8,
            "task_timeout": 300,
            "error_rate_high": 0.1,
            "queue_length_high": 10,
        },
        "executors": {
            "hermes": {"command": "hermes", "mode": "live", "dispatch_args": ["team", "dispatch"]},
            "openclaw": {"command": "openclaw", "mode": "dry-run", "dispatch_args": ["dispatch"]},
        },
        "directories": _default_directories(),
        "feature_flags": {
            "persistent_bus_enabled": True,
            "workflow_runtime_enabled": True,
            "governance_enabled": True,
            "metrics_enabled": True,
        },
        "sensitive_actions": ["provider.execute_sensitive", "provider.openclaw.live"],
        "aliases": _build_aliases(agents),
        "default_executor": "hermes",
    }


def _deep_merge(base: Dict[str, object], override: Dict[str, object]) -> Dict[str, object]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=4)
def load_control_plane_config(config_path: Optional[str] = None) -> ControlPlaneConfig:
    payload = _default_payload()
    if config_path:
        override = json.loads(Path(config_path).read_text(encoding="utf-8"))
        payload = _deep_merge(payload, override)

    agents = {
        agent_id: AgentConfig(**agent_payload) if isinstance(agent_payload, dict) else agent_payload
        for agent_id, agent_payload in payload["agents"].items()
    }
    config = ControlPlaneConfig(
        task_keywords=payload["task_keywords"],
        agents=agents,
        groups=payload["groups"],
        thresholds=payload["thresholds"],
        executors=payload["executors"],
        directories=payload["directories"],
        feature_flags=payload["feature_flags"],
        sensitive_actions=payload["sensitive_actions"],
        aliases=payload["aliases"],
        default_executor=payload["default_executor"],
    )

    try:
        from observability.metrics import get_metrics_registry

        get_metrics_registry().set_gauge("improvement_config_sources_total", 1.0)
    except Exception:
        pass
    return config
