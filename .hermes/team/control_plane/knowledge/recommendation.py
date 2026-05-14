from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .models import KnowledgeProfile


def build_router_knowledge_profile(intent, agent_id: str, role_key: str) -> KnowledgeProfile:
    return KnowledgeProfile(
        task_type=getattr(intent.task_type, 'value', str(getattr(intent, 'task_type', 'generic'))),
        deliverables=list(getattr(intent, 'deliverables', [])),
        risk_flags=list(getattr(intent, 'risk_flags', [])),
        owner_agent=agent_id,
        role_key=role_key,
        collaboration_mode=str(getattr(intent, 'collaboration_mode', 'single')),
        upstream_agent=getattr(intent, 'upstream_agent', None),
        upstream_role=getattr(intent, 'upstream_role', None),
    )


def _score_path(path_text: str, profile: KnowledgeProfile) -> Dict[str, object]:
    score = 10.0
    reasons: List[str] = []
    lowered = path_text.lower()
    if 'status.md' in lowered:
        score += 5.0
        reasons.append('status')
    if 'overview.md' in lowered:
        score += 8.0
        reasons.append('overview')
    if 'checklist' in lowered:
        score += 18.0
        reasons.append('checklist')
    if 'recent-lessons' in lowered:
        score += 16.0
        reasons.append('recent-lessons')
    if 'risk' in lowered and profile.risk_flags:
        score += 15.0
        reasons.append('risk-flag')
    for deliverable in profile.deliverables:
        value = str(deliverable).lower()
        if value and value in lowered:
            score += 6.0
            reasons.append(f'deliverable:{value}')
    for hint in profile.module_hints + profile.scope_paths:
        value = str(hint).lower()
        if value and value in lowered:
            score += 10.0
            reasons.append(f'module:{value}')
    resolved = Path(path_text)
    exists = resolved.exists() if resolved.is_absolute() else False
    return {
        'path': path_text,
        'resolved_path': str(resolved),
        'exists': exists,
        'score': score,
        'reasons': reasons,
    }


def _rank_paths(paths: List[str], profile: KnowledgeProfile) -> tuple[List[str], Dict[str, Dict[str, object]], List[Dict[str, str]]]:
    scored = [_score_path(path, profile) for path in paths]
    scored.sort(key=lambda item: (-float(item['score']), str(item['path'])))
    degradations = []
    for item in scored:
        resolved = item['path']
        candidate = Path(resolved)
        if not candidate.is_absolute():
            candidate = Path(__file__).resolve().parents[4] / resolved
        if not candidate.exists():
            degradations.append({'path': str(item['path']), 'reason': 'missing-path'})
    return [str(item['path']) for item in scored], {Path(str(item['path'])).name: item for item in scored}, degradations


def _cross_role_packages(profile: KnowledgeProfile) -> List[str]:
    packages: List[str] = []
    task_type = profile.task_type.lower()
    if task_type in {'implementation', 'coding', 'development'}:
        packages.append('architect+backend-dev+qa-functional')
    if profile.collaboration_mode in {'review', 'handoff'} and 'architect+backend-dev+qa-functional' not in packages:
        packages.append('architect+backend-dev+qa-functional')
    if 'performance' in ' '.join(profile.deliverables).lower() or 'load' in ' '.join(profile.risk_flags).lower():
        packages.append('backend-dev+qa-performance+devops')
    return packages


def build_recommendation(
    profile: KnowledgeProfile,
    role_key: str,
    agent_id: str,
    repository_root,
) -> Dict[str, object]:
    team_paths = [
        '.hermes/team/knowledge/status.md',
        '.hermes/team/knowledge/project-overview.md',
        '.hermes/team/knowledge/workflow-playbook.md',
    ]
    if profile.task_type in {'requirements', 'analysis'} or 'spec' in profile.deliverables:
        team_paths.append('.hermes/team/knowledge/domain-glossary.md')
    if profile.collaboration_mode != 'single':
        team_paths.append('.hermes/team/knowledge/handoff-templates.md')
    if profile.risk_flags:
        team_paths.append('.hermes/team/knowledge/risk-register.md')

    role_paths = [
        f'.hermes/agents/{role_key}/knowledge/status.md',
        f'.hermes/agents/{role_key}/knowledge/overview.md',
        f'.hermes/agents/{role_key}/knowledge/playbooks/common-tasks.md',
        f'.hermes/agents/{role_key}/knowledge/checklists/delivery-checklist.md',
    ]
    if profile.collaboration_mode in {'review', 'handoff'}:
        role_paths.append(f'.hermes/agents/{role_key}/knowledge/checklists/design-checklist.md')

    instance_paths = [
        f'.hermes/team/agents/{agent_id}/knowledge/expertise.md',
        f'.hermes/team/agents/{agent_id}/knowledge/owned-modules.md',
        f'.hermes/team/agents/{agent_id}/knowledge/delivery-style.md',
        f'.hermes/team/agents/{agent_id}/knowledge/recent-lessons.md',
    ]
    if profile.collaboration_mode != 'single':
        instance_paths.append(f'.hermes/team/agents/{agent_id}/knowledge/collaboration-preferences.md')

    ordered_team, team_scores, team_degradations = _rank_paths(team_paths, profile)
    ordered_role, role_scores, role_degradations = _rank_paths(role_paths, profile)
    ordered_instance, instance_scores, instance_degradations = _rank_paths(instance_paths, profile)
    degradations = team_degradations + role_degradations + instance_degradations
    if degradations:
        degradations.append({'path': 'role-overview', 'reason': 'fallback-role-overview'})
    return {
        'profile': profile.to_dict(),
        'load_order': ['team', 'role', 'instance'],
        'team': ordered_team,
        'role': ordered_role,
        'instance': ordered_instance,
        'cross_role': _cross_role_packages(profile),
        'path_scores': {
            'team': team_scores,
            'role': role_scores,
            'instance': instance_scores,
        },
        'degradations': degradations,
        'recommendation_reason': ['rules', 'module-affinity', 'feedback-score'],
    }
