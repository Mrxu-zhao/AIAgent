from __future__ import annotations

from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def generate_design_spec_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    feature = str(payload.get("feature", "Example"))
    platform = str(payload.get("platform", "web"))
    
    spec = f'''# {feature} 设计规范

## 1. 概述

- **功能**: {feature}
- **平台**: {platform}
- **优先级**: P0

## 2. 信息架构

```
[页面] → [模块] → [组件]
```

## 3. 交互流程

1. 用户进入页面
2. 系统加载数据
3. 用户执行操作
4. 系统反馈结果

## 4. 视觉规范

| 元素 | 规格 |
|---|---|
| 主色调 | #1890FF |
| 字体 | 14px Regular |
| 按钮高度 | 32px |
| 圆角 | 4px |

## 5. 响应式规则

| 断点 | 布局 |
|---|---|
| >= 1440px | 三栏 |
| >= 1024px | 两栏 |
| < 1024px | 单栏 |

## 6. 无障碍要求

- [ ] 支持键盘导航
- [ ] 支持屏幕阅读器
- [ ] 对比度 >= 4.5:1
'''
    return ToolResult.ok_result(
        content=spec,
        structured_data={"feature": feature, "platform": platform},
        artifacts=[],
    )
