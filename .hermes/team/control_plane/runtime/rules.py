from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from knowledge.catalog import build_bundle_from_recommendation
from knowledge.consumer import build_excerpt_bundle


_KNOWLEDGE_BUNDLE_CACHE: Dict[str, Dict[str, object]] = {}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_knowledge_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return repository_root() / path


def build_knowledge_bundle(recommendation: Dict[str, object]) -> Dict[str, List[str]]:
    bundle = build_bundle_from_recommendation(recommendation)
    return dict(bundle)


def preload_knowledge_bundle(bundle: Dict[str, object]) -> Dict[str, object]:
    cache_key = str(bundle.get("cache_key") or "")
    if cache_key and cache_key in _KNOWLEDGE_BUNDLE_CACHE:
        cached = dict(_KNOWLEDGE_BUNDLE_CACHE[cache_key])
        cached["cache_hit"] = True
        return cached
    excerpt_bundle = build_excerpt_bundle(
        paths=list(bundle.get("paths", [])),
        resolved_paths=list(bundle.get("resolved_paths", [])),
        profile=dict(bundle.get("profile") or {}),
    )
    loaded = dict(bundle)
    loaded["items"] = excerpt_bundle["items"]
    loaded["preloaded"] = True
    loaded["knowledge_summary"] = excerpt_bundle["summary"]
    loaded["next_read"] = excerpt_bundle["next_read"]
    loaded["cache_hit"] = False
    if cache_key:
        _KNOWLEDGE_BUNDLE_CACHE[cache_key] = dict(loaded)
    return loaded
