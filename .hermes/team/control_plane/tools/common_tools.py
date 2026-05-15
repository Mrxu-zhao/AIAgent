from __future__ import annotations

import re
import subprocess
from pathlib import Path
from string import Template
from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def _resolve_safe_path(context: ToolExecutionContext, raw_path: str) -> Path:
    root = Path(context.cwd).resolve() if context.cwd else Path.cwd().resolve()
    target = (root / raw_path).resolve()
    if root not in target.parents and target != root:
        raise ValueError(f"path must stay within repository root: {raw_path}")
    forbidden = {".git", "node_modules", ".venv", "__pycache__", ".hermes-sandbox"}
    for part in target.relative_to(root).parts:
        if part in forbidden:
            raise ValueError(f"writing to forbidden directory: {part}")
    return target


def write_file_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    try:
        target = _resolve_safe_path(context, str(payload["path"]))
        content = str(payload["content"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult.ok_result(
            content=f"written:{target}",
            structured_data={"path": str(payload["path"]), "bytes": len(content.encode("utf-8"))},
            artifacts=[str(payload["path"])],
        )
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))


def search_code_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    try:
        root = Path(context.cwd).resolve() if context.cwd else Path.cwd().resolve()
        pattern = str(payload.get("pattern", ""))
        glob = str(payload.get("glob", "*"))
        max_results = int(payload.get("max_results", 50))
        matches = []
        for path in root.rglob(glob):
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue
            lines = content.splitlines()
            for lineno, line in enumerate(lines, start=1):
                if pattern in line:
                    matches.append({
                        "path": str(path.relative_to(root)),
                        "lineno": lineno,
                        "line": line.strip(),
                    })
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break
        return ToolResult.ok_result(
            content=f"found:{len(matches)}",
            structured_data={"matches": matches, "total": len(matches)},
            artifacts=[m["path"] for m in matches],
        )
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))


ALLOWED_COMMAND_PATTERNS = {
    "echo", "python", "python3", "pytest", "mvn", "npm", "node",
    "git", "java", "javac",
}
FORBIDDEN_PATTERNS = [r"rm\s+-rf\s+/", r">\s*/dev/null", r"curl\s+.*\|", r"wget\s+.*\|", r"\bsudo\b"]


def _is_command_allowed(command: str) -> bool:
    cmd_lower = command.lower().strip()
    for forbidden in FORBIDDEN_PATTERNS:
        if re.search(forbidden, cmd_lower):
            return False
    first_word = cmd_lower.split()[0] if cmd_lower else ""
    return first_word in ALLOWED_COMMAND_PATTERNS


def run_command_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    command = str(payload.get("command", "")).strip()
    if not command:
        return ToolResult.error_result(error="empty command")
    if not _is_command_allowed(command):
        return ToolResult.error_result(error=f"command not allowed: {command}")
    try:
        cwd = context.cwd if context.cwd else None
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=int(payload.get("timeout", 60)),
        )
        return ToolResult.ok_result(
            content=result.stdout or "(no output)",
            structured_data={
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            artifacts=[],
        )
    except subprocess.TimeoutExpired:
        return ToolResult.error_result(error="command timeout")
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))


CODE_TEMPLATES = {
    "spring_controller": '''package ${package};

import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("${endpoint}")
public class ${class_name} {

    @GetMapping
    public List<${entity_name}> list() {
        // TODO: implement list
        return null;
    }

    @GetMapping("/{id}")
    public ${entity_name} getById(@PathVariable Long id) {
        // TODO: implement getById
        return null;
    }

    @PostMapping
    public ${entity_name} create(@RequestBody ${entity_name} entity) {
        // TODO: implement create
        return null;
    }

    @PutMapping("/{id}")
    public ${entity_name} update(@PathVariable Long id, @RequestBody ${entity_name} entity) {
        // TODO: implement update
        return null;
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        // TODO: implement delete
    }
}
''',
    "vue_component": '''<template>
  <div class="${component_name}-container">
    <!-- TODO: implement -->
  </div>
</template>

<script setup lang="ts">
// TODO: implement
</script>

<style scoped>
.${component_name}-container {
  /* TODO: implement */
}
</style>
''',
}


def generate_code_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    template_name = str(payload.get("template", ""))
    variables = dict(payload.get("variables") or {})
    template_str = CODE_TEMPLATES.get(template_name)
    if not template_str:
        available = ", ".join(CODE_TEMPLATES.keys())
        return ToolResult.error_result(error=f"unknown template '{template_name}'. Available: {available}")
    try:
        t = Template(template_str)
        code = t.safe_substitute(variables)
        return ToolResult.ok_result(
            content=code,
            structured_data={"template": template_name, "variables": variables},
            artifacts=[],
        )
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))
