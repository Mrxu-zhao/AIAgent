from __future__ import annotations

from typing import Dict, Iterable

from tools.spec import ToolSpec

from tools.common_tools import (
    generate_code_handler,
    run_command_handler,
    search_code_handler,
    write_file_handler,
)


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
