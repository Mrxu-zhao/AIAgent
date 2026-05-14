from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .governance import load_governance_records


def _match(record: Dict[str, object], query_text: Optional[str], filters: Dict[str, object]) -> bool:
    if query_text:
        haystack = ' '.join(
            str(record.get(key, ''))
            for key in ('content', 'entry_type', 'owner', 'source_workflow_id', 'source_step_id', 'source_agent')
        ).lower()
        if query_text.lower() not in haystack:
            return False
    mapping = {
        'agent': 'source_agent',
        'role': 'owner',
        'review_status': 'review_status',
        'workflow_id': 'source_workflow_id',
        'step_id': 'source_step_id',
        'task_type': 'entry_type',
    }
    for filter_name, record_field in mapping.items():
        value = filters.get(filter_name)
        if value is not None and record.get(record_field) != value:
            return False
    risk_tag = filters.get('risk_tag')
    if risk_tag is not None and risk_tag not in str(record.get('content', '')):
        return False
    return True


def query_knowledge_records(
    root: Path,
    query_text: Optional[str] = None,
    filters: Optional[Dict[str, object]] = None,
    limit: int = 100,
) -> Dict[str, object]:
    filters = dict(filters or {})
    records = [record for record in load_governance_records(root) if _match(record, query_text, filters)]
    records = records[:limit]
    aggregations = {
        'by_review_status': {},
        'by_owner': {},
    }
    for record in records:
        review_status = str(record.get('review_status') or 'unknown')
        owner = str(record.get('owner') or 'unknown')
        aggregations['by_review_status'][review_status] = aggregations['by_review_status'].get(review_status, 0) + 1
        aggregations['by_owner'][owner] = aggregations['by_owner'].get(owner, 0) + 1
    return {
        'filters': filters,
        'records': records,
        'summary': {'record_count': len(records), 'query_text': query_text},
        'aggregations': aggregations,
    }
