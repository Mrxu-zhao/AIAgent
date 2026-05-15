# Agent 实际做事能力提升设计文档

> **日期**: 2026-05-15  
> **目标**: 让 14 个 Agent 从"知道怎么做"进化为"能端到端交付"  
> **范围**: 交付契约 + 标准工作流 + 多栈模板 + 质量门禁 + 知识闭环  
> **技术栈**: Java/Go/Python + Vue/React/小程序/鸿蒙 + 多数据库 + DevOps  

---

## 1. 现状与问题

### 1.1 当前能力
- 14 个 Agent 有完整的 SOUL.md、expertise.md、知识库、模板
- 控制平面已有 12 个 builtin tools + 20 个新增工具
- workflow runtime、handoff、tool runtime 已落地
- 253 个测试通过

### 1.2 核心缺口
| 缺口 | 影响 |
|---|---|
| 有工具但无"交付契约" | 产出物质量参差不齐，无法验收 |
| 有模板但无"栈选择" | Java/Go/Python 混用，模板不匹配 |
| 有工作流但无"质量门禁" | 自检环节缺失，缺陷后移 |
| 有经验但无"沉淀闭环" | recent-lessons 为空，无法进化 |

---

## 2. 设计目标

### 2.1 核心原则
- **交付契约先行**: 每个角色明确"输入→输出→验收标准"
- **多栈插件化**: 后端/前端/数据库/移动端按项目选择技术栈
- **质量内建**: 每个工作流必须包含自检/评审/门禁环节
- **知识闭环**: 成功案例自动沉淀到 expertise/templates/recent-lessons

### 2.2 成功标准
- 每个角色有 1 份 Delivery Contract
- 每个角色有 3~5 条标准工作流（覆盖 Web/平台/移动端/鸿蒙）
- 每个栈有独立的模板包和自检命令包
- 新增工作流测试全部通过
- 原有 253 个测试不降级

---

## 3. 总体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent Delivery Capability Layer                   │
├─────────────────────────────────────────────────────────────────────┤
│  Delivery Contracts (14 roles)                                      │
│  ├── 输入定义 | 输出产物 | 验收标准(DoD) | 质量门禁                 │
├─────────────────────────────────────────────────────────────────────┤
│  Role Workflows (14 roles × 3~5 workflows)                          │
│  ├── Web 业务工作流 | 平台工具工作流 | 移动端工作流 | 鸿蒙工作流     │
├─────────────────────────────────────────────────────────────────────┤
│  Stack Plugin System                                                │
│  ├── Backend: Java(Spring) | Go(Gin) | Python(FastAPI)             │
│  ├── Frontend: Vue3 | React | 小程序 | 鸿蒙(ArkTS)                  │
│  ├── Database: MySQL | Postgres | Redis | MongoDB                   │
│  └── Mobile: iOS | Android | 鸿蒙 HarmonyOS                         │
├─────────────────────────────────────────────────────────────────────┤
│  Quality Gates                                                      │
│  ├── 自检清单 | 静态检查 | 测试执行 | 评审模板 | 交接单             │
├─────────────────────────────────────────────────────────────────────┤
│  Knowledge Closed Loop                                              │
│  ├── 推荐→消费→回写→查询→进化                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Existing Tool Runtime (32 tools)                                   │
│  ├── builtin 12 + common 4 + role 16                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. 交付契约设计

### 4.1 通用交付契约模板

```yaml
role: {role_id}
name: {role_name}
delivery_contract:
  inputs:
    - name: 上游交付物
      type: document/code/spec
      required: true
  outputs:
    - name: 核心产物
      type: document/code/config
      template: "templates/{output_template}.md"
  definition_of_done:
    - 自检清单全部通过
    - 静态检查无错误
    - 测试覆盖率达标
    - 评审结论通过
    - 交接单已填写
  quality_gates:
    - gate: 自检
      tool: self_checklist
    - gate: 静态检查
      tool: lint/static_analysis
    - gate: 测试
      tool: test_runner
    - gate: 评审
      tool: review_template
    - gate: 交接
      tool: handoff_form
```

### 4.2 各角色交付契约

#### analyst（需求分析师 - 吴雪梅）
| 输入 | 输出 | DoD |
|---|---|---|
| 访谈记录、业务目标、约束条件 | PRD、用户故事、验收标准、范围边界、风险清单 | 每条需求有验收标准；范围/非范围明确；风险与依赖明确 |

#### architect（架构师 - 张欣怡）
| 输入 | 输出 | DoD |
|---|---|---|
| PRD、非功能需求、现有架构 | 架构设计文档、ADR、接口契约、模块边界、性能指标 | 关键决策可追溯；接口契约可被直接消费；非功能指标可量化 |

#### dba（周嘉诚）
| 输入 | 输出 | DoD |
|---|---|---|
| 数据模型需求、性能要求、容量规划 | 数据模型、DDL、索引方案、SQL Review 结论、容量评估 | 表设计评审通过；关键查询有 explain；索引建议可落地 |

#### backend-*（陈启明/王浩然/赵文杰）
| 输入 | 输出 | DoD |
|---|---|---|
| 接口契约、数据模型、架构设计 | 接口实现、单测、接口文档、变更说明、灰度策略 | 单测覆盖率>80%；代码评审清单过关；接口文档完整 |

#### frontend-*（李思雨/周晓明/林雅婷）
| 输入 | 输出 | DoD |
|---|---|---|
| 设计规范、接口契约、组件规范 | 组件/页面实现、组件规范、联调说明、lint/test 结果 | 组件 API 规范化；性能 checklist 过关；交互符合 UCD |

#### ucd（吴俊杰）
| 输入 | 输出 | DoD |
|---|---|---|
| PRD、用户画像、竞品分析 | 交互说明、设计规范、设计交接单、可用性测试计划 | 关键流程覆盖；边界态齐全；交接信息可直接开发 |

#### qa-functional（郑晓彤）
| 输入 | 输出 | DoD |
|---|---|---|
| PRD、接口文档、设计规范 | 测试用例、回归计划、缺陷报告、测试总结 | 用例覆盖验收标准；缺陷可复现；回归范围明确 |

#### qa-performance（孙美玲）
| 输入 | 输出 | DoD |
|---|---|---|
| 性能需求、架构设计、容量规划 | 压测方案、压测报告、瓶颈分析、优化建议 | 性能指标可量化；瓶颈定位准确；优化建议可落地 |

#### devops（黄志远）
| 输入 | 输出 | DoD |
|---|---|---|
| 部署需求、监控需求、应急预案 | 部署配置、监控配置、应急预案、上线检查清单 | 可回滚；监控/告警齐全；应急演练脚本可执行 |

---

## 5. 多栈插件系统设计

### 5.1 栈注册表

```python
# stacks/registry.py
STACK_REGISTRY = {
    "backend": {
        "java-spring": {
            "templates": "stacks/backend/java-spring/templates/",
            "commands": {"test": "mvn test", "lint": "mvn spotless:check", "build": "mvn package"},
            "file_extensions": [".java", ".xml", ".properties"],
        },
        "go-gin": {
            "templates": "stacks/backend/go-gin/templates/",
            "commands": {"test": "go test ./...", "lint": "golangci-lint run", "build": "go build"},
            "file_extensions": [".go", ".mod"],
        },
        "python-fastapi": {
            "templates": "stacks/backend/python-fastapi/templates/",
            "commands": {"test": "pytest", "lint": "ruff check .", "build": "docker build"},
            "file_extensions": [".py", ".toml"],
        },
    },
    "frontend": {
        "vue3": {
            "templates": "stacks/frontend/vue3/templates/",
            "commands": {"test": "vitest", "lint": "eslint", "build": "vite build"},
            "file_extensions": [".vue", ".ts", ".css"],
        },
        "react": {
            "templates": "stacks/frontend/react/templates/",
            "commands": {"test": "jest", "lint": "eslint", "build": "vite build"},
            "file_extensions": [".tsx", ".css"],
        },
        "mini-program": {
            "templates": "stacks/frontend/mini-program/templates/",
            "commands": {"test": "jest", "lint": "eslint", "build": "npm run build"},
            "file_extensions": [".js", ".wxml", ".wxss"],
        },
        "harmony-arkts": {
            "templates": "stacks/frontend/harmony-arkts/templates/",
            "commands": {"test": "ohpm test", "lint": "arkts-lint", "build": "hvigor build"},
            "file_extensions": [".ets", ".json"],
        },
    },
    "database": {
        "mysql": {
            "templates": "stacks/database/mysql/templates/",
            "commands": {"test": "mysql -e", "lint": "sqlfluff lint", "build": "flyway migrate"},
        },
        "postgres": {
            "templates": "stacks/database/postgres/templates/",
            "commands": {"test": "psql -f", "lint": "sqlfluff lint", "build": "flyway migrate"},
        },
        "redis": {
            "templates": "stacks/database/redis/templates/",
            "commands": {"test": "redis-cli", "lint": "redis-lint", "build": "redis-cli"},
        },
    },
}
```

### 5.2 栈选择机制

```yaml
# 工作流定义中的栈选择
workflow_id: backend-api-development
name: 后端API开发工作流
role: backend-dev
stack_selection:
  prompt: "请选择技术栈"
  options:
    - java-spring
    - go-gin
    - python-fastapi
  default: java-spring
```

---

## 6. 标准工作流设计（按场景分类）

### 6.1 Web 业务场景工作流

| 角色 | 工作流 | 关键步骤 |
|---|---|---|
| analyst | web-requirements-analysis | 访谈→PRD→用户故事→验收标准→评审→交接 |
| architect | web-architecture-design | 读PRD→技术选型→架构设计→ADR→接口契约→评审→交接 |
| dba | web-database-design | 读需求→数据建模→DDL→索引→SQL Review→交接 |
| backend | web-api-development | 读契约→生成代码→单测→接口文档→自检→交接 |
| frontend | web-page-development | 读设计→生成组件→API对接→联调→自检→交接 |
| ucd | web-interaction-design | 读PRD→交互设计→设计规范→交接单→可用性计划 |
| qa | web-test-design | 读PRD→用例设计→回归计划→缺陷模板→交接 |
| devops | web-deployment | 读部署需求→Docker→K8s→监控→应急预案→上线清单 |

### 6.2 平台工具场景工作流

| 角色 | 工作流 | 关键步骤 |
|---|---|---|
| analyst | platform-requirements-analysis | 工具需求→使用场景→配置规范→验收标准 |
| architect | platform-architecture-design | 插件架构→扩展点设计→配置化方案→评审 |
| backend | platform-service-development | 核心服务→插件机制→配置管理→监控埋点 |
| devops | platform-deployment | 多租户部署→配置中心→灰度发布→运维面板 |

### 6.3 移动端场景工作流

| 角色 | 工作流 | 关键步骤 |
|---|---|---|
| analyst | mobile-requirements-analysis | 移动端特性→屏幕适配→性能指标→离线策略 |
| ucd | mobile-interaction-design | 触屏交互→手势规范→响应式规则→交接 |
| frontend | mobile-page-development | 页面实现→API适配→性能优化→兼容性测试 |
| qa | mobile-test-design | 设备兼容性→网络模拟→性能测试→用户体验测试 |

### 6.4 鸿蒙场景工作流

| 角色 | 工作流 | 关键步骤 |
|---|---|---|
| analyst | harmony-requirements-analysis | 鸿蒙特性→分布式能力→原子化服务→验收标准 |
| architect | harmony-architecture-design | 鸿蒙架构→Ability设计→分布式数据→安全模型 |
| frontend | harmony-ability-development | Ability实现→UI组件→分布式能力→性能优化 |
| qa | harmony-test-design | 鸿蒙设备测试→分布式测试→性能测试→安全测试 |

---

## 7. 质量门禁设计

### 7.1 通用质量门禁

```yaml
quality_gates:
  self_checklist:
    description: "自检清单"
    required: true
    template: "templates/self-checklist.md"
  
  static_analysis:
    description: "静态检查"
    required: true
    commands:
      backend: "{stack.commands.lint}"
      frontend: "{stack.commands.lint}"
    
  test_execution:
    description: "测试执行"
    required: true
    commands:
      backend: "{stack.commands.test}"
      frontend: "{stack.commands.test}"
    coverage_threshold: 80
    
  code_review:
    description: "代码评审"
    required: true
    template: "templates/code-review-checklist.md"
    min_approvers: 1
    
  handoff:
    description: "交接单"
    required: true
    template: "templates/handoff-form.md"
    deliverables_check: true
```

### 7.2 角色专用质量门禁

| 角色 | 额外门禁 |
|---|---|
| analyst | 需求评审会议纪要通过；验收标准可测试化检查 |
| architect | 技术评审通过；ADR 已归档；接口契约已发布 |
| dba | SQL Review 通过；Explain 分析通过；容量评估通过 |
| backend | 单测覆盖率>80%；接口文档完整；变更说明已填写 |
| frontend | 组件规范符合；性能指标达标；交互符合 UCD |
| ucd | 设计评审通过；交接信息完整；可用性计划已制定 |
| qa | 用例覆盖验收标准；回归范围明确；缺陷可复现 |
| devops | 部署脚本可执行；监控告警齐全；应急预案可演练 |

---

## 8. 知识闭环设计

### 8.1 闭环流程

```
任务执行 → 产物生成 → 质量门禁 → 交接完成 → 经验提取 → 知识回写 → 模板更新
```

### 8.2 回写目标

| 来源 | 目标文件 | 内容 |
|---|---|---|
| 成功案例 | `.hermes/team/agents/{role}/knowledge/recent-lessons.md` | 经验总结、最佳实践 |
| 常用模板 | `.hermes/agents/{role}/knowledge/templates/*.md` | 新增/优化模板 |
| 跨角色规则 | `.hermes/team/knowledge/*.md` | 共性规则、标准更新 |
| 栈特定规则 | `stacks/{stack}/knowledge/*.md` | 栈特定最佳实践 |

### 8.3 自动化触发

```yaml
knowledge_feedback:
  trigger: "任务完成且质量门禁全部通过"
  actions:
    - extract_patterns: "从产物中提取可复用模式"
    - update_templates: "更新模板文件"
    - append_lessons: "追加到 recent-lessons"
    - notify_team: "通知团队知识更新"
```

---

## 9. 文件结构

```
.hermes/team/control_plane/
├── delivery/                       # 新增：交付契约
│   ├── contracts/                  # 角色交付契约
│   │   ├── analyst.yaml
│   │   ├── architect.yaml
│   │   ├── dba.yaml
│   │   ├── backend.yaml
│   │   ├── frontend.yaml
│   │   ├── ucd.yaml
│   │   ├── qa-functional.yaml
│   │   ├── qa-performance.yaml
│   │   └── devops.yaml
│   └── quality_gates/              # 质量门禁定义
│       ├── self-checklist.md
│       ├── code-review-checklist.md
│       └── handoff-form.md
├── stacks/                         # 新增：多栈插件
│   ├── backend/
│   │   ├── java-spring/
│   │   │   ├── templates/
│   │   │   └── commands.yaml
│   │   ├── go-gin/
│   │   └── python-fastapi/
│   ├── frontend/
│   │   ├── vue3/
│   │   ├── react/
│   │   ├── mini-program/
│   │   └── harmony-arkts/
│   └── database/
│       ├── mysql/
│       ├── postgres/
│       └── redis/
├── workflows/                      # 已有：工作流定义
│   ├── web/                        # 新增：Web场景工作流
│   ├── platform/                   # 新增：平台场景工作流
│   ├── mobile/                     # 新增：移动端工作流
│   └── harmony/                    # 新增：鸿蒙场景工作流
└── knowledge_loop/                 # 新增：知识闭环
    ├── extractor.py                # 经验提取器
    └── updater.py                  # 知识更新器

tests/control_plane/
├── test_delivery_contracts.py      # 新增：交付契约测试
├── test_stack_plugins.py           # 新增：栈插件测试
├── test_quality_gates.py           # 新增：质量门禁测试
└── test_knowledge_loop.py          # 新增：知识闭环测试
```

---

## 10. 实施计划

### Phase 0: 交付契约与共同定义（1 周）
- [ ] 为 9 个角色编写 Delivery Contract YAML
- [ ] 定义通用质量门禁模板
- [ ] 定义多栈注册表结构
- [ ] 评审并确认交付契约

### Phase 1: 核心工作流（2 周）
- [ ] 实现 Web 场景 8 条标准工作流
- [ ] 实现栈选择机制
- [ ] 为 Java-Spring + Vue3 补齐模板包
- [ ] 工作流测试覆盖

### Phase 2: 多栈扩展（2 周）
- [ ] 补齐 Go-Gin + Python-FastAPI 模板
- [ ] 补齐 React + 小程序 + 鸿蒙 ArkTS 模板
- [ ] 补齐 Postgres + Redis 模板
- [ ] 平台场景工作流
- [ ] 移动端场景工作流
- [ ] 鸿蒙场景工作流

### Phase 3: 质量门禁与知识闭环（1 周）
- [ ] 实现质量门禁检查器
- [ ] 实现知识闭环自动回写
- [ ] 全量回归测试
- [ ] 文档更新

---

## 11. 完成定义

- [ ] 9 个角色各有一份 Delivery Contract
- [ ] 每个角色有 3~5 条标准工作流（覆盖 Web/平台/移动端/鸿蒙）
- [ ] 多栈插件系统支持 Java/Go/Python + Vue/React/小程序/鸿蒙
- [ ] 质量门禁自动检查（自检→静态检查→测试→评审→交接）
- [ ] 知识闭环自动回写（recent-lessons/templates/team-knowledge）
- [ ] 新增测试全部通过
- [ ] 原有 253 个测试全部通过
