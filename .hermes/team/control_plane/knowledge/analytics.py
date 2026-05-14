from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .governance import summarize_pending_governance_counts


def build_knowledge_heat_ranking(task_router=None) -> List[Dict[str, object]]:
    counts: Dict[str, int] = {}
    if task_router is not None:
        for task in getattr(task_router, 'tasks', {}).values():
            recommendation = getattr(task, 'routing_reason', {}).get('knowledge_recommendation') or {}
            for group in ('team', 'role', 'instance'):
                for path in recommendation.get(group, [])[:3]:
                    counts[path] = counts.get(path, 0) + 1
    items = [{'path': path, 'count': count} for path, count in counts.items()]
    items.sort(key=lambda item: (-int(item['count']), str(item['path'])))
    return items[:10]


def build_consumption_by_agent(task_router=None) -> List[Dict[str, object]]:
    distribution: Dict[str, int] = {}
    if task_router is not None:
        for task in getattr(task_router, 'tasks', {}).values():
            agent_id = getattr(task, 'assigned_agent', None)
            recommendation = getattr(task, 'routing_reason', {}).get('knowledge_recommendation') or {}
            count = sum(len(recommendation.get(group, [])) for group in ('team', 'role', 'instance'))
            if agent_id:
                distribution[agent_id] = distribution.get(agent_id, 0) + count
    return [{'agent': agent, 'count': count} for agent, count in sorted(distribution.items())]


def build_unused_recommendations(task_router=None) -> List[Dict[str, object]]:
    result = []
    if task_router is not None:
        for task in getattr(task_router, 'tasks', {}).values():
            recommendation = getattr(task, 'routing_reason', {}).get('knowledge_recommendation') or {}
            unused = list(recommendation.get('team', []))[:1]
            if unused:
                result.append({'task_id': getattr(task, 'id', ''), 'unused_paths': unused})
    return result[:5]


def build_high_risk_coverage(workflow_runtime_dir) -> Dict[str, object]:
    snapshots_dir = Path(workflow_runtime_dir) / 'snapshots' if workflow_runtime_dir else None
    if snapshots_dir is None or not snapshots_dir.exists():
        return {'workflow_count': 0, 'covered_count': 0, 'coverage_ratio': 0.0}
    workflow_count = 0
    covered_count = 0
    for path in snapshots_dir.glob('*.json'):
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        workflow_count += 1
        recommendations = snapshot.get('knowledge_recommendations') or {}
        if recommendations:
            covered_count += 1
    ratio = covered_count / workflow_count if workflow_count else 0.0
    return {'workflow_count': workflow_count, 'covered_count': covered_count, 'coverage_ratio': ratio}


def build_pending_governance_counts(knowledge_root) -> Dict[str, int]:
    return summarize_pending_governance_counts(Path(knowledge_root))
