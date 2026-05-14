from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple

MAX_SUMMARY_CHARS = 240
MAX_EXCERPT_CHARS = 600
MAX_FILE_BYTES = 64 * 1024
SUSPICIOUS_MARKERS = ('<script', 'rm -rf', 'powershell -enc', 'BEGIN PRIVATE KEY')


def _decode_content(raw_content) -> Tuple[str, str | None]:
    if isinstance(raw_content, bytes):
        try:
            return raw_content.decode('utf-8'), None
        except UnicodeDecodeError:
            return '', 'decode-error'
    return str(raw_content), None


def suspicious_content(text: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in SUSPICIOUS_MARKERS)


def _summarize_text(text: str) -> str:
    compact = ' '.join(line.strip() for line in text.splitlines() if line.strip())
    return compact[:MAX_SUMMARY_CHARS]


def _excerpt_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    excerpt = ' '.join(lines[:6])
    return excerpt[:MAX_EXCERPT_CHARS]


def _priority_for_text(path: str, text: str, profile: Dict[str, object]) -> tuple[float, List[str]]:
    score = 10.0
    matched_by: List[str] = []
    lowered_path = path.lower()
    lowered_text = text.lower()
    task_type = str(profile.get('task_type', '')).lower()
    for risk in profile.get('risk_flags', []) or []:
        if str(risk).lower() in lowered_text or str(risk).lower() in lowered_path:
            score += 15.0
            matched_by.append('risk_flag')
    for deliverable in profile.get('deliverables', []) or []:
        if str(deliverable).lower() in lowered_text or str(deliverable).lower() in lowered_path:
            score += 10.0
            matched_by.append('deliverable')
    if task_type and task_type in lowered_path:
        score += 8.0
        matched_by.append('task_type')
    if 'checklist' in lowered_path:
        score += 20.0
        matched_by.append('checklist')
    if 'recent-lessons' in lowered_path:
        score += 18.0
        matched_by.append('recent-lessons')
    if 'risk' in lowered_path and profile.get('risk_flags'):
        score += 12.0
        matched_by.append('risk-register')
    return score, matched_by


def build_excerpt_record(path: str, resolved_path: str, raw_content, profile: Dict[str, object] | None = None) -> Dict[str, object]:
    profile = dict(profile or {})
    text, degraded_reason = _decode_content(raw_content)
    expandable = True
    if degraded_reason is None and suspicious_content(text):
        return {
            'path': path,
            'resolved_path': resolved_path,
            'summary': 'content isolated due to suspicious markers',
            'excerpt': '',
            'priority': 0.0,
            'matched_by': ['isolated-content'],
            'tokens_estimate': 0,
            'expandable': False,
            'degraded_reason': 'isolated-content',
        }
    if degraded_reason is None and len(text.encode('utf-8')) > MAX_FILE_BYTES:
        degraded_reason = 'oversized-file'
        text = text[:MAX_FILE_BYTES]
    if degraded_reason is not None:
        expandable = degraded_reason not in {'decode-error', 'isolated-content'}
    priority, matched_by = _priority_for_text(path, text, profile)
    return {
        'path': path,
        'resolved_path': resolved_path,
        'summary': _summarize_text(text) if text else f'knowledge degraded: {degraded_reason}',
        'excerpt': _excerpt_text(text),
        'priority': priority,
        'matched_by': matched_by,
        'tokens_estimate': max(1, len(text) // 4) if text else 0,
        'expandable': expandable,
        'degraded_reason': degraded_reason,
    }


def build_excerpt_bundle(paths: Iterable[str], resolved_paths: Iterable[str], profile: Dict[str, object] | None = None) -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    for path, resolved_path in zip(list(paths), list(resolved_paths)):
        file_path = Path(str(resolved_path))
        if not file_path.exists():
            items.append(
                {
                    'path': str(path),
                    'resolved_path': str(resolved_path),
                    'summary': 'knowledge file missing',
                    'excerpt': '',
                    'priority': 0.0,
                    'matched_by': ['missing-path'],
                    'tokens_estimate': 0,
                    'expandable': False,
                    'degraded_reason': 'missing-path',
                }
            )
            continue
        try:
            raw_content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            raw_content = file_path.read_bytes()
        items.append(build_excerpt_record(str(path), str(file_path), raw_content, profile))
    items.sort(key=lambda item: (-float(item['priority']), str(item['path'])))
    return {
        'items': items,
        'preloaded': True,
        'summary': build_knowledge_summary(items),
        'next_read': build_next_read(items),
    }


def build_knowledge_summary(items: Iterable[Dict[str, object]], limit: int = 3) -> str:
    parts = []
    for item in list(items)[:limit]:
        summary = str(item.get('summary') or '').strip()
        if summary:
            parts.append(summary)
    return ' | '.join(parts)


def build_next_read(items: Iterable[Dict[str, object]], limit: int = 3) -> List[str]:
    result: List[str] = []
    for item in list(items):
        path = str(item.get('path') or '')
        if path and path not in result:
            result.append(path)
        if len(result) >= limit:
            break
    return result


def expand_excerpt_content(item: Dict[str, object]) -> Dict[str, object]:
    expanded = dict(item)
    resolved = Path(str(item.get('resolved_path', '')))
    if not item.get('expandable', True):
        return expanded
    if not resolved.exists():
        expanded['degraded_reason'] = 'missing-path'
        return expanded
    try:
        expanded['content'] = resolved.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        expanded['degraded_reason'] = 'decode-error'
    return expanded
