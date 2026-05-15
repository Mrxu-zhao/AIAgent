from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return json.loads(value.replace("'", '"'))
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    if value.isdigit():
        return int(value)
    return value


def _next_relevant_index(lines: list[str], index: int) -> int:
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped and not stripped.startswith("#"):
            return index
        index += 1
    return index


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_mapping(lines: list[str], index: int, indent: int) -> tuple[Dict[str, Any], int]:
    result: Dict[str, Any] = {}
    index = _next_relevant_index(lines, index)
    while index < len(lines):
        index = _next_relevant_index(lines, index)
        if index >= len(lines):
            break
        line = lines[index]
        current_indent = _line_indent(line)
        stripped = line.strip()
        if current_indent < indent or stripped.startswith("- "):
            break
        if ":" not in stripped:
            index += 1
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            result[key] = _parse_scalar(value)
            index += 1
            continue
        child, index = _parse_block(lines, index + 1, current_indent + 2)
        result[key] = child
    return result, index


def _parse_sequence(lines: list[str], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    index = _next_relevant_index(lines, index)
    while index < len(lines):
        index = _next_relevant_index(lines, index)
        if index >= len(lines):
            break
        line = lines[index]
        current_indent = _line_indent(line)
        stripped = line.strip()
        if current_indent < indent or not stripped.startswith("- "):
            break
        item_text = stripped[2:].strip()
        if not item_text:
            child, index = _parse_block(lines, index + 1, current_indent + 2)
            result.append(child)
            continue
        if ":" in item_text:
            key, value = item_text.split(":", 1)
            item: Dict[str, Any] = {}
            key = key.strip()
            value = value.strip()
            if value:
                item[key] = _parse_scalar(value)
                index += 1
            else:
                child, index = _parse_block(lines, index + 1, current_indent + 2)
                item[key] = child
            extra, index = _parse_mapping(lines, index, current_indent + 2)
            item.update(extra)
            result.append(item)
            continue
        result.append(_parse_scalar(item_text))
        index += 1
    return result, index


def _parse_block(lines: list[str], index: int, indent: int) -> tuple[Any, int]:
    index = _next_relevant_index(lines, index)
    if index >= len(lines):
        return {}, index
    line = lines[index]
    current_indent = _line_indent(line)
    if current_indent < indent:
        return {}, index
    if line.strip().startswith("- "):
        return _parse_sequence(lines, index, current_indent)
    return _parse_mapping(lines, index, current_indent)


def _parse_yaml_simple(text: str) -> Dict[str, Any]:
    """Parse the workflow YAML subset used in this repository without external deps."""
    data, _ = _parse_block(text.splitlines(), 0, 0)
    if isinstance(data, dict):
        return data
    return {}


def _workflows_dir() -> Path:
    return Path(__file__).resolve().parent


def _workflow_files() -> list[Path]:
    return sorted(_workflows_dir().rglob("*.yaml"))


def _read_workflow(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    # Use PyYAML if available, else fallback
    try:
        import yaml

        return yaml.safe_load(text)
    except ImportError:
        return _parse_yaml_simple(text)


class WorkflowLoader:
    def load(self, workflow_id: str) -> Dict[str, Any]:
        path = _workflows_dir() / f"{workflow_id}.yaml"
        if path.exists():
            return _read_workflow(path)
        for workflow_path in _workflow_files():
            if workflow_path.stem == workflow_id:
                return _read_workflow(workflow_path)
            workflow = _read_workflow(workflow_path)
            if workflow.get("workflow_id") == workflow_id:
                return workflow
        raise FileNotFoundError(f"workflow not found: {workflow_id}")

    def list_workflows(self) -> Dict[str, str]:
        result = {}
        for path in _workflow_files():
            data = _read_workflow(path)
            result[data["workflow_id"]] = data.get("name", path.stem)
        return result
