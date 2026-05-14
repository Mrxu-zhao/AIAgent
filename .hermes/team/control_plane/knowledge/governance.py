from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from .models import GovernanceEntry


def _store_dir(root: Path) -> Path:
    return root / '.governance'


def _entries_path(root: Path) -> Path:
    directory = _store_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / 'entries.jsonl'


def _audit_path(root: Path) -> Path:
    directory = _store_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / 'audit.jsonl'


def _write_jsonl(path: Path, payload: Dict[str, object]) -> None:
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + '\n')


def append_governance_entry(
    root: Path,
    entry_type: str,
    content: str,
    owner: str,
    source_workflow_id: Optional[str] = None,
    source_step_id: Optional[str] = None,
    source_agent: Optional[str] = None,
) -> Dict[str, object]:
    entry = GovernanceEntry(
        entry_id=f'gov-{uuid4().hex}',
        entry_type=entry_type,
        content=content,
        owner=owner,
        source_workflow_id=source_workflow_id,
        source_step_id=source_step_id,
        source_agent=source_agent,
        created_at=time.time(),
        audit_trail=[{'action': 'append', 'actor': source_agent or owner, 'timestamp': time.time()}],
    )
    _write_jsonl(_entries_path(root), entry.to_dict())
    _write_jsonl(_audit_path(root), {'action': 'append', 'entry_id': entry.entry_id, 'actor': source_agent or owner, 'timestamp': time.time()})
    return entry.to_dict()


def load_governance_records(root: Path, entry_type: Optional[str] = None, review_status: Optional[str] = None) -> List[Dict[str, object]]:
    path = _entries_path(root)
    if not path.exists():
        return []
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if entry_type is not None:
        records = [record for record in records if record.get('entry_type') == entry_type]
    if review_status is not None:
        records = [record for record in records if record.get('review_status') == review_status]
    return records


def _replace_records(root: Path, records: Iterable[Dict[str, object]]) -> None:
    path = _entries_path(root)
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    path.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')


def apply_governance_action(knowledge_root: Path, action: str, actor: str, entry_id: str) -> Dict[str, object]:
    records = load_governance_records(knowledge_root)
    updated = None
    now = time.time()
    for record in records:
        if record.get('entry_id') != entry_id:
            continue
        if action == 'accept':
            record['review_status'] = 'accepted'
            record['accepted'] = True
            record['rejected'] = False
            record['archived'] = False
        elif action == 'reject':
            record['review_status'] = 'rejected'
            record['accepted'] = False
            record['rejected'] = True
        elif action == 'archive':
            record['review_status'] = 'archived'
            record['archived'] = True
        else:
            raise ValueError(f'unsupported action: {action}')
        record['reviewed_at'] = now
        record.setdefault('audit_trail', []).append({'action': action, 'actor': actor, 'timestamp': now})
        updated = record
        break
    if updated is None:
        raise FileNotFoundError(entry_id)
    _replace_records(knowledge_root, records)
    _write_jsonl(_audit_path(knowledge_root), {'action': action, 'entry_id': entry_id, 'actor': actor, 'timestamp': now})
    return updated


def summarize_pending_governance_counts(knowledge_root: Path) -> Dict[str, int]:
    records = load_governance_records(knowledge_root)
    pending = [record for record in records if record.get('review_status') == 'pending_review']
    decisions = sum(1 for record in pending if record.get('entry_type') == 'decision')
    risks = sum(1 for record in pending if record.get('entry_type') == 'risk')
    lessons = sum(1 for record in pending if record.get('entry_type') == 'lesson')
    return {'pending_total': len(pending), 'decision': decisions, 'risk': risks, 'lesson': lessons}
