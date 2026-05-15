from __future__ import annotations

from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def generate_controller_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    class_name = str(payload.get("class_name", "ExampleController"))
    package = str(payload.get("package", "com.example.controller"))
    endpoint = str(payload.get("endpoint", "/api/example"))
    entity_name = str(payload.get("entity_name", "Example"))
    code = f'''package {package};

import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("{endpoint}")
public class {class_name} {{

    @GetMapping
    public List<{entity_name}> list() {{
        return List.of();
    }}

    @GetMapping("/{{id}}")
    public {entity_name} getById(@PathVariable Long id) {{
        return new {entity_name}();
    }}

    @PostMapping
    public {entity_name} create(@RequestBody {entity_name} entity) {{
        return entity;
    }}

    @PutMapping("/{{id}}")
    public {entity_name} update(@PathVariable Long id, @RequestBody {entity_name} entity) {{
        return entity;
    }}

    @DeleteMapping("/{{id}}")
    public void delete(@PathVariable Long id) {{
        // default stub: no-op
    }}
}}
'''
    return ToolResult.ok_result(
        content=code,
        structured_data={"class_name": class_name, "package": package, "endpoint": endpoint},
        artifacts=[],
    )


def generate_service_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    class_name = str(payload.get("class_name", "ExampleService"))
    package = str(payload.get("package", "com.example.service"))
    entity_name = str(payload.get("entity_name", "Example"))
    code = f'''package {package};

import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class {class_name} {{

    public List<{entity_name}> list() {{
        return List.of();
    }}

    public {entity_name} getById(Long id) {{
        return new {entity_name}();
    }}

    public {entity_name} create({entity_name} entity) {{
        return entity;
    }}

    public {entity_name} update(Long id, {entity_name} entity) {{
        return entity;
    }}

    public void delete(Long id) {{
        // default stub: no-op
    }}
}}
'''
    return ToolResult.ok_result(
        content=code,
        structured_data={"class_name": class_name, "package": package},
        artifacts=[],
    )


def generate_mapper_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    class_name = str(payload.get("class_name", "ExampleMapper"))
    package = str(payload.get("package", "com.example.mapper"))
    entity_name = str(payload.get("entity_name", "Example"))
    table_name = str(payload.get("table_name", "example"))
    code = f'''package {package};

import org.apache.ibatis.annotations.*;
import java.util.List;

@Mapper
public interface {class_name} {{

    @Select("SELECT * FROM {table_name}")
    List<{entity_name}> list();

    @Select("SELECT * FROM {table_name} WHERE id = #{{id}}")
    {entity_name} getById(Long id);

    @Insert("INSERT INTO {table_name} (...) VALUES (...)")
    void create({entity_name} entity);

    @Update("UPDATE {table_name} SET ... WHERE id = #{{id}}")
    void update({entity_name} entity);

    @Delete("DELETE FROM {table_name} WHERE id = #{{id}}")
    void delete(Long id);
}}
'''
    return ToolResult.ok_result(
        content=code,
        structured_data={"class_name": class_name, "package": package, "table_name": table_name},
        artifacts=[],
    )


def run_unit_tests_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    import subprocess
    test_path = str(payload.get("test_path", ""))
    command = f"mvn test -Dtest={test_path}" if test_path else "mvn test"
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=context.cwd if context.cwd else None,
            capture_output=True,
            text=True,
            timeout=int(payload.get("timeout", 120)),
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
        return ToolResult.error_result(error="test timeout")
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))
