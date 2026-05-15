from __future__ import annotations

from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def generate_prd_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    feature = str(payload.get("feature", "Example"))
    background = str(payload.get("background", ""))
    
    prd = f'''# {feature} 产品需求文档

## 1. 背景

{background}

## 2. 目标

- 提升用户体验
- 降低操作成本
- 提高系统稳定性

## 3. 用户故事

### US-001
**作为** 用户  
**我希望** 能够快速完成任务  
**以便** 节省时间

### US-002
**作为** 管理员  
**我希望** 能够查看统计数据  
**以便** 做出决策

## 4. 功能需求

### FR-001: 核心功能
- 输入: 用户数据
- 处理: 业务逻辑
- 输出: 结果展示

### FR-002: 辅助功能
- 数据导出
- 批量操作
- 历史记录

## 5. 非功能需求

| 类型 | 要求 |
|---|---|
| 性能 | 页面加载 < 2s |
| 可用性 | 99.9% |
| 安全 | 数据加密传输 |

## 6. 验收标准

- [ ] 功能完整实现
- [ ] 测试用例全部通过
- [ ] 文档更新完成
'''
    return ToolResult.ok_result(
        content=prd,
        structured_data={"feature": feature, "user_stories": 2, "requirements": 2},
        artifacts=[],
    )
