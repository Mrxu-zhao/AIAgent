from __future__ import annotations

from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def generate_test_cases_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    requirement = str(payload.get("requirement", ""))
    feature = str(payload.get("feature", "Example"))
    doc = f'''# {feature} 测试用例

## 功能测试

### TC-001: 正常流程
| 步骤 | 操作 | 预期结果 |
|---|---|---|
| 1 | 输入有效数据 | 系统接受输入 |
| 2 | 点击提交 | 操作成功提示 |
| 3 | 查询记录 | 数据正确保存 |

### TC-002: 异常流程 - 空值校验
| 步骤 | 操作 | 预期结果 |
|---|---|---|
| 1 | 必填字段留空 | 提示"不能为空" |
| 2 | 点击提交 | 阻止提交 |

### TC-003: 异常流程 - 边界值
| 步骤 | 操作 | 预期结果 |
|---|---|---|
| 1 | 输入最大值+1 | 提示"超出范围" |
| 2 | 输入最小值-1 | 提示"超出范围" |

## 非功能测试

### TC-004: 性能测试
- 并发用户数: 100
- 响应时间要求: < 500ms
- 通过率要求: > 99%

### TC-005: 兼容性测试
- 浏览器: Chrome, Firefox, Safari
- 分辨率: 1920x1080, 1366x768

## 需求来源

{requirement}
'''
    return ToolResult.ok_result(
        content=doc,
        structured_data={"feature": feature, "test_cases": 5},
        artifacts=[],
    )


def run_api_tests_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    import subprocess
    collection = str(payload.get("collection", ""))
    command = f"newman run {collection}" if collection else "echo 'no collection specified'"
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
        return ToolResult.error_result(error="api test timeout")
    except Exception as exc:
        return ToolResult.error_result(error=str(exc))
