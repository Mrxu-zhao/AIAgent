from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .models import KnowledgeProfile


def build_router_knowledge_profile(intent, agent_id: str, role_key: str) -> KnowledgeProfile:
    return KnowledgeProfile(
        task_type=getattr(intent.task_type, 'value', str(getattr(intent, 'task_type', 'generic'))),
        deliverables=list(getattr(intent, 'deliverables', [])),
        risk_flags=list(getattr(intent, 'risk_flags', [])),
        search_terms=list(getattr(intent, 'search_terms', [])),
        owner_agent=agent_id,
        role_key=role_key,
        collaboration_mode=str(getattr(intent, 'collaboration_mode', 'single')),
        upstream_agent=getattr(intent, 'upstream_agent', None),
        upstream_role=getattr(intent, 'upstream_role', None),
    )


def resolve_role_key(agent_id: str) -> str:
    if agent_id.startswith("backend-"):
        return "backend-dev"
    if agent_id.startswith("frontend-"):
        return "frontend-dev"
    return agent_id


def _resolve_path(path_text: str, repository_root: Path) -> Path:
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate
    return repository_root / path_text


def _content_match_bonus(
    path_text: str,
    resolved: Path,
    profile: KnowledgeProfile,
) -> tuple[float, List[str]]:
    lowered = path_text.lower()
    if "lessons" not in lowered and "patterns" not in lowered:
        return 0.0, []
    if not resolved.exists():
        return 0.0, []
    text = resolved.read_text(encoding="utf-8").lower()
    score = 0.0
    reasons: List[str] = []
    seen = set()
    for term in list(profile.search_terms)[:24]:
        normalized = str(term).strip().lower()
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        if normalized in text:
            bonus = 8.0 if len(normalized) >= 4 else 4.0
            score += bonus
            reasons.append(f"content:{normalized}")
    return min(score, 48.0), reasons


def _score_path(path_text: str, profile: KnowledgeProfile, repository_root: Path) -> Dict[str, object]:
    score = 10.0
    reasons: List[str] = []
    lowered = path_text.lower()
    if 'status.md' in lowered:
        score += 5.0
        reasons.append('status')
    if 'overview.md' in lowered:
        score += 8.0
        reasons.append('overview')
    if 'project-lessons' in lowered:
        score += 20.0
        reasons.append('project-lessons')
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
    resolved = _resolve_path(path_text, repository_root)
    content_bonus, content_reasons = _content_match_bonus(path_text, resolved, profile)
    score += content_bonus
    reasons.extend(content_reasons)
    exists = resolved.exists()
    return {
        'path': path_text,
        'resolved_path': str(resolved),
        'exists': exists,
        'score': score,
        'reasons': reasons,
    }


def _rank_paths(
    paths: List[str],
    profile: KnowledgeProfile,
    repository_root: Path,
) -> tuple[List[str], Dict[str, Dict[str, object]], List[Dict[str, str]]]:
    scored = [_score_path(path, profile, repository_root) for path in paths]
    scored.sort(key=lambda item: (-float(item['score']), str(item['path'])))
    degradations = []
    for item in scored:
        candidate = _resolve_path(str(item['path']), repository_root)
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
    repository_root = Path(repository_root)
    team_paths = [
        '.hermes/team/knowledge/status.md',
        '.hermes/team/knowledge/project-overview.md',
        '.hermes/team/knowledge/workflow-playbook.md',
        '.hermes/team/knowledge/project-lessons.md',
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
        f'.hermes/agents/{role_key}/knowledge/project-lessons.md',
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

    ordered_team, team_scores, team_degradations = _rank_paths(team_paths, profile, repository_root)
    ordered_role, role_scores, role_degradations = _rank_paths(role_paths, profile, repository_root)
    ordered_instance, instance_scores, instance_degradations = _rank_paths(instance_paths, profile, repository_root)
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
