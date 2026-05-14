from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import KnowledgeBundle, KnowledgeProfile


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_repository_path(path_text: str) -> Path:
    path = Path(path_text)
    resolved = path if path.is_absolute() else repository_root() / path
    resolved = resolved.resolve()
    root = repository_root().resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError('path must stay within repository root')
    return resolved


def build_cache_key(paths: Iterable[str], profile: Optional[KnowledgeProfile] = None) -> str:
    base = '\n'.join(sorted(str(path) for path in paths))
    if profile is not None:
        base += '\n' + '|'.join(
            [
                profile.task_type,
                ','.join(profile.deliverables),
                ','.join(profile.risk_flags),
                profile.owner_agent or '',
                profile.role_key or '',
                profile.collaboration_mode,
            ]
        )
    return hashlib.sha1(base.encode('utf-8')).hexdigest()


def build_bundle_from_recommendation(
    recommendation: Dict[str, object],
    profile: Optional[KnowledgeProfile] = None,
) -> Dict[str, object]:
    relative_paths: List[str] = []
    resolved_paths: List[str] = []
    missing_paths: List[str] = []
    for group in ('team', 'role', 'instance'):
        for item in recommendation.get(group, []) or []:
            path_text = str(item)
            resolved = resolve_repository_path(path_text)
            if resolved.exists():
                relative_paths.append(path_text)
                resolved_paths.append(str(resolved))
            else:
                missing_paths.append(path_text)
    cache_key = build_cache_key(relative_paths, profile)
    bundle = {
        'profile': profile.to_dict() if profile is not None else recommendation.get('profile') or {},
        'load_order': list(recommendation.get('load_order', [])),
        'team': list(recommendation.get('team', [])),
        'role': list(recommendation.get('role', [])),
        'instance': list(recommendation.get('instance', [])),
        'cross_role': list(recommendation.get('cross_role', [])),
        'paths': relative_paths,
        'resolved_paths': resolved_paths,
        'raw_paths': list(relative_paths),
        'missing_paths': missing_paths,
        'cache_key': cache_key,
        'degradations': list(recommendation.get('degradations', [])),
        'recommendation_reason': list(recommendation.get('recommendation_reason', [])),
    }
    return bundle


def build_bundle_model(recommendation: Dict[str, object], profile: KnowledgeProfile) -> KnowledgeBundle:
    payload = build_bundle_from_recommendation(recommendation, profile)
    return KnowledgeBundle(
        profile=profile,
        load_order=list(payload['load_order']),
        team=list(payload['team']),
        role=list(payload['role']),
        instance=list(payload['instance']),
        cross_role=list(payload['cross_role']),
        raw_paths=list(payload['raw_paths']),
        missing_paths=list(payload['missing_paths']),
        cache_key=str(payload['cache_key']),
        recommendation_reason=list(payload['recommendation_reason']),
        degradations=list(payload['degradations']),
    )
