from __future__ import annotations

from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def generate_vue_component_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    component_name = str(payload.get("component_name", "Example"))
    props = payload.get("props", [])
    emits = payload.get("emits", [])
    props_str = "\n".join([f'  {p}: {{ type: String, required: true }},' for p in props])
    emits_str = "\n".join([f'  "{e}",' for e in emits])
    code = f'''<template>
  <div class="{component_name.lower()}-container">
    <!-- TODO: implement -->
  </div>
</template>

<script setup lang="ts">
const props = defineProps({{
{props_str}
}})

const emit = defineEmits([
{emits_str}
])
</script>

<style scoped>
.{component_name.lower()}-container {{
  /* TODO: implement */
}}
</style>
'''
    return ToolResult.ok_result(
        content=code,
        structured_data={"component_name": component_name},
        artifacts=[],
    )


def generate_api_client_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    api_name = str(payload.get("api_name", "Example"))
    endpoint = str(payload.get("endpoint", "/api/example"))
    methods = payload.get("methods", ["GET", "POST"])
    method_str = "\n".join([
        f'  {m.lower()}() {{\n    return request("{m}", "{endpoint}")\n  }}'
        for m in methods
    ])
    code = f'''import {{ request }} from "@/utils/http"

export function use{api_name}Api() {{
{method_str}
}}
'''
    return ToolResult.ok_result(
        content=code,
        structured_data={"api_name": api_name, "endpoint": endpoint},
        artifacts=[],
    )


def run_linter_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    import subprocess
    file_path = str(payload.get("file_path", "."))
    command = f"npx eslint {file_path}"
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=context.cwd if context.cwd else None,
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
        return ToolResult.error_result(error="linter timeout")
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))
