from __future__ import annotations

from pathlib import Path
from typing import Dict, List


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_knowledge_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return repository_root() / path


def build_knowledge_bundle(recommendation: Dict[str, object]) -> Dict[str, List[str]]:
    relative_paths: List[str] = []
    resolved_paths: List[str] = []
    for group in ("team", "role", "instance"):
        for item in recommendation.get(group, []):
            resolved = resolve_knowledge_path(str(item))
            if resolved.exists():
                relative_paths.append(str(item))
                resolved_paths.append(str(resolved))
    return {"paths": relative_paths, "resolved_paths": resolved_paths}
