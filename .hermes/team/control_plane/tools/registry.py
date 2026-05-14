from __future__ import annotations

from typing import Dict, Iterable

from tools.spec import ToolSpec


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolSpec] | None = None):
        self._tools: Dict[str, ToolSpec] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def names(self):
        return sorted(self._tools.keys())
