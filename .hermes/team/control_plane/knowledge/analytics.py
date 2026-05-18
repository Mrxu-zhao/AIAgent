from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

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


def build_knowledge_effectiveness_report(workflow_runtime_dir) -> Dict[str, object]:
    snapshots_dir = Path(workflow_runtime_dir) / 'snapshots' if workflow_runtime_dir else None
    if snapshots_dir is None or not snapshots_dir.exists():
        return {
            'workflow_count': 0,
            'usage_record_count': 0,
            'average_feedback_score': 0.0,
            'usage_heat_ranking': [],
            'unused_path_ranking': [],
        }

    workflow_count = 0
    usage_record_count = 0
    score_total = 0.0
    usage_heat: Dict[str, int] = {}
    unused_heat: Dict[str, int] = {}

    for snapshot in _iter_snapshots(snapshots_dir):
        workflow_count += 1
        usage_payload = snapshot.get('knowledge_usage') or {}
        summary = usage_payload.get('summary') or {}
        step_records = usage_payload.get('steps') or []
        if not summary and not step_records:
            continue
        usage_record_count += 1
        score_total += float(summary.get('feedback_score', 0.0) or 0.0)
        for path in summary.get('consumed_paths', []) or []:
            usage_heat[str(path)] = usage_heat.get(str(path), 0) + 1
        for path in summary.get('unused_paths', []) or []:
            unused_heat[str(path)] = unused_heat.get(str(path), 0) + 1

    average_feedback_score = round(score_total / usage_record_count, 4) if usage_record_count else 0.0
    return {
        'workflow_count': workflow_count,
        'usage_record_count': usage_record_count,
        'average_feedback_score': average_feedback_score,
        'usage_heat_ranking': _sorted_counts(usage_heat),
        'unused_path_ranking': _sorted_counts(unused_heat),
    }


def _iter_snapshots(snapshots_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in sorted(snapshots_dir.glob('*.json')):
        records.append(json.loads(path.read_text(encoding='utf-8')))
    return records


def _sorted_counts(counts: Dict[str, int]) -> List[Dict[str, object]]:
    items = [{'path': path, 'count': count} for path, count in counts.items()]
    items.sort(key=lambda item: (-int(item['count']), str(item['path'])))
    return items[:10]
