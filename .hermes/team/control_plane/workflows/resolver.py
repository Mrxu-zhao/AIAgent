from __future__ import annotations

import re
from typing import Any, Dict


class WorkflowValueResolver:
    _STEP_PATTERN = re.compile(r"\$\{([^}]+)\}")

    def __init__(self, context: Dict[str, Any]):
        self.context = context
        self.context.setdefault("step_outputs", {})

    def resolve_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._resolve_string(value)
        if isinstance(value, list):
            return [self.resolve_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self.resolve_value(item) for key, item in value.items()}
        return value

    def register_step_result(self, step_id: str, result: Dict[str, Any]) -> None:
        structured = dict(result.get("structured_data") or {})
        output = structured.get("output")
        if output is None:
            output = result.get("content", "")
        self.context.setdefault("step_outputs", {})[step_id] = {
            "output": output,
            "content": result.get("content", ""),
            "structured_data": structured,
            "artifacts": list(result.get("artifacts") or []),
            "ok": bool(result.get("ok")),
            "error": result.get("error"),
        }

    def _resolve_string(self, value: str) -> Any:
        protected: list[str] = []

        def _protect(match: re.Match[str]) -> str:
            protected.append(match.group(1))
            return f"__STEP_REF_{len(protected) - 1}__"

        template = self._STEP_PATTERN.sub(_protect, value)
        try:
            template = template.format(**self._scalar_context())
        except KeyError:
            pass
        if template.startswith("__STEP_REF_") and template.endswith("__") and template.count("__STEP_REF_") == 1:
            index = int(template[len("__STEP_REF_") : -2])
            return self._resolve_step_expression(protected[index])
        for index, expression in enumerate(protected):
            token = f"__STEP_REF_{index}__"
            template = template.replace(token, str(self._resolve_step_expression(expression)))
        return template

    def _resolve_step_expression(self, expression: str) -> Any:
        parts = expression.split(".")
        current: Any = self.context.get("step_outputs", {})
        for part in parts:
            if not isinstance(current, dict):
                return ""
            current = current.get(part)
        return current if current is not None else ""

    def _scalar_context(self) -> Dict[str, Any]:
        return {
            key: value
            for key, value in self.context.items()
            if isinstance(value, (str, int, float, bool))
        }
