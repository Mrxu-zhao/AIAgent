# Agent 实际干活能力增强设计文档

> **日期**: 2026-05-15  
> **目标**: 让 9 个角色 Agent 从"知道怎么做"进化为"能实际执行"  
> **范围**: 工具扩展 + 工作流固化，全部 9 个角色同步推进  

---

## 1. 现状与问题

### 1.1 当前能力
- 9 个角色有完整的 SOUL.md、知识库、SKILL.md
- 控制平面有 8 个 builtin tools（以查询为主）
- workflow runtime、handoff、tool runtime MVP 已落地
- 210 个测试通过，核心路径覆盖率 94%

### 1.2 核心缺口
| 缺口 | 影响 |
|---|---|
| 工具以只读查询为主（6/8） | Agent 能查不能写，无法产出代码 |
| playbooks/common-tasks.md 只有 4 行 | 接到任务不知从何下手 |
| 无代码生成工具 | 无法直接产出 Controller/Service/Mapper |
| 无文件写入工具 | 无法将产出写入项目 |
| 无测试执行工具 | 无法验证代码正确性 |
| 无代码搜索工具 | 无法基于现有代码上下文工作 |
| LEARNING_PLAN 全部"待开始" | 无能力成长轨迹 |

---

## 2. 设计目标

### 2.1 核心原则
- **直接写入**: Agent 生成代码后直接写入文件（效率优先）
- **角色专用**: 每个角色有自己的工具集和工作流
- **渐进增强**: 不破坏现有能力，只做加法
- **可验证**: 每个新增能力都有测试覆盖

### 2.2 成功标准
- 每个角色新增 3-5 个专用工具
- 每个角色有 3-5 个标准工作流定义
- 新增工具测试全部通过
- 工作流执行测试全部通过
- 原有 210 个测试不降级

---

## 3. 方案设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Productivity Layer                  │
├─────────────────────────────────────────────────────────────┤
│  Role-Specific Tools (9 roles × 4 tools)                    │
│  ├── backend-dev:   generate_code | write_file | run_tests  │
│  ├── frontend-dev:  generate_component | write_file | lint  │
│  ├── architect:     generate_design_doc | review_code       │
│  ├── dba:           generate_sql | analyze_query            │
│  ├── qa-functional: generate_test_case | run_tests          │
│  ├── qa-performance: generate_jmeter | analyze_report       │
│  ├── devops:        generate_dockerfile | generate_k8s_yaml │
│  ├── ucd:           generate_mock | write_design_spec       │
│  └── requirements:  generate_prd | analyze_requirement      │
├─────────────────────────────────────────────────────────────┤
│  Standard Workflows (9 roles × 3 workflows)                 │
│  ├── backend-api-dev:  design → generate → test → handoff   │
│  ├── frontend-page:    design → component → test → handoff  │
│  ├── architect-review: analyze → design → review → handoff  │
│  └── ...                                                    │
├─────────────────────────────────────────────────────────────┤
│  Core Tool Runtime (existing)                               │
│  ├── ToolRegistry | ToolExecutor | ToolSpec                 │
│  ├── SessionStore | TranscriptStore                         │
│  └── RBAC | ApprovalGate                                    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 新增通用工具（所有角色共享）

| 工具名 | 作用 | 权限 | 并发安全 |
|---|---|---|---|
| `write_file` | 写入/更新文件 | write | 否 |
| `read_file` | 读取文件（已存在） | read | 是 |
| `search_code` | 代码库搜索 | read | 是 |
| `run_command` | 执行 shell 命令 | execute | 否 |
| `generate_code` | 按模板生成代码 | generate | 否 |

### 3.3 角色专用工具

#### backend-dev
| 工具名 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `generate_controller` | 生成 Spring Boot Controller | api_spec | Java 文件 |
| `generate_service` | 生成 Service 层 | controller_methods | Java 文件 |
| `generate_mapper` | 生成 MyBatis Mapper | entity_name | XML/Java 文件 |
| `run_unit_tests` | 执行 JUnit 测试 | test_path | 测试报告 |

#### frontend-dev
| 工具名 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `generate_vue_component` | 生成 Vue3 组件 | component_spec | .vue 文件 |
| `generate_api_client` | 生成 API 调用层 | api_spec | TS 文件 |
| `run_linter` | 执行 ESLint | file_path | Lint 报告 |

#### architect
| 工具名 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `generate_architecture_doc` | 生成架构设计文档 | requirements | Markdown |
| `review_api_design` | 评审接口设计 | api_spec | 评审意见 |

#### dba
| 工具名 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `generate_ddl` | 生成建表 SQL | table_spec | SQL 文件 |
| `analyze_slow_query` | 分析慢查询 | sql + explain | 优化建议 |

#### qa-functional
| 工具名 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `generate_test_cases` | 生成测试用例 | requirement | Markdown |
| `run_api_tests` | 执行接口测试 | test_collection | 测试报告 |

#### qa-performance
| 工具名 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `generate_jmeter_script` | 生成 JMeter 脚本 | scenario | .jmx 文件 |
| `analyze_performance_report` | 分析性能报告 | jtl_file | 分析报告 |

#### devops
| 工具名 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `generate_dockerfile` | 生成 Dockerfile | app_type | Dockerfile |
| `generate_k8s_manifests` | 生成 K8s 配置 | service_name | YAML 文件 |

#### ucd
| 工具名 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `generate_design_spec` | 生成设计规范 | requirement | Markdown |

#### requirements-analyst
| 工具名 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `generate_prd` | 生成需求文档 | interview_notes | Markdown |

---

## 4. 工作流设计

### 4.1 工作流定义格式

沿用现有 workflow 定义格式，新增 `tools` 字段声明每个 step 使用的工具：

```yaml
# .hermes/team/control_plane/workflows/backend-api-development.yaml
workflow_id: backend-api-development
name: 后端 API 开发工作流
description: 从接口设计到测试通过的完整流程
role: backend-dev
steps:
  - step_id: read_requirement
    name: 读取需求
    tool: read_knowledge
    input:
      paths: ["requirements/{feature}.md"]

  - step_id: design_api
    name: 设计接口
    tool: generate_controller
    input:
      api_spec: "${requirement.api_spec}"
    output:
      file: "src/main/java/com/example/controller/{Feature}Controller.java"

  - step_id: implement_service
    name: 实现业务层
    tool: generate_service
    input:
      controller_methods: "${design_api.methods}"
    output:
      file: "src/main/java/com/example/service/{Feature}Service.java"

  - step_id: write_tests
    name: 编写测试
    tool: generate_code
    input:
      template: "junit_test"
      target: "${implement_service.class_name}"
    output:
      file: "src/test/java/com/example/service/{Feature}ServiceTest.java"

  - step_id: run_tests
    name: 执行测试
    tool: run_unit_tests
    input:
      test_path: "src/test/java/com/example/service/{Feature}ServiceTest.java"
    condition:
      - if: "${run_tests.failed_count} > 0"
        then: retry
        max_retries: 3

  - step_id: handoff
    name: 交接给测试
    tool: dispatch_task
    input:
      agent_id: "qa-functional"
      task: "请测试 {feature} 接口"
```

### 4.2 各角色标准工作流

| 角色 | 工作流 1 | 工作流 2 | 工作流 3 |
|---|---|---|---|
| backend-dev | API 开发 | Bug 修复 | 数据库迁移 |
| frontend-dev | 页面开发 | 组件封装 | API 对接 |
| architect | 架构设计 | 技术评审 | 性能优化方案 |
| dba | 表设计 | 索引优化 | 数据迁移 |
| qa-functional | 测试用例设计 | 回归测试 | Bug 验证 |
| qa-performance | 压测方案 | 性能分析 | 容量规划 |
| devops | 部署配置 | 监控配置 | 流水线配置 |
| ucd | 交互设计 | 视觉规范 | 设计评审 |
| requirements | 需求分析 | 用户故事 | 需求评审 |

---

## 5. 文件结构

```
.hermes/team/control_plane/
├── tools/
│   ├── builtin.py              # 现有 8 个工具
│   ├── role_tools/             # 新增：角色专用工具
│   │   ├── __init__.py
│   │   ├── backend_tools.py    # backend-dev 4 个工具
│   │   ├── frontend_tools.py   # frontend-dev 3 个工具
│   │   ├── architect_tools.py  # architect 2 个工具
│   │   ├── dba_tools.py        # dba 2 个工具
│   │   ├── qa_tools.py         # qa 2 个工具
│   │   ├── devops_tools.py     # devops 2 个工具
│   │   ├── ucd_tools.py        # ucd 1 个工具
│   │   └── requirements_tools.py  # requirements 1 个工具
│   └── common_tools.py         # 新增：通用工具（write_file, search_code, run_command）
├── workflows/                  # 新增：标准工作流定义
│   ├── backend-api-development.yaml
│   ├── frontend-page-development.yaml
│   ├── architect-design-review.yaml
│   ├── dba-table-design.yaml
│   ├── qa-test-case-design.yaml
│   ├── devops-deployment.yaml
│   ├── ucd-interaction-design.yaml
│   └── requirements-analysis.yaml
└── cli.py                      # 修改：注册新工具和工作流

tests/control_plane/
├── test_role_tools/            # 新增：角色工具测试
│   ├── test_backend_tools.py
│   ├── test_frontend_tools.py
│   └── ...
├── test_common_tools.py        # 新增：通用工具测试
└── test_workflows.py           # 新增：工作流测试
```

---

## 6. 安全与权限

### 6.1 文件写入安全
- `write_file` 限制在仓库根目录内
- 禁止写入 `.git/`、`node_modules/` 等敏感目录
- 关键文件（如 `pom.xml`、`package.json`）修改需审批

### 6.2 命令执行安全
- `run_command` 白名单模式，只允许 `mvn test`、`npm run lint` 等安全命令
- 禁止 `rm -rf /`、`curl | bash` 等危险操作

### 6.3 RBAC 配置
```python
# governance/tool_permissions.py 新增
ROLE_TOOL_PERMISSIONS = {
    "backend-dev": ["generate_controller", "generate_service", "generate_mapper", "run_unit_tests", "write_file"],
    "frontend-dev": ["generate_vue_component", "generate_api_client", "run_linter", "write_file"],
    "architect": ["generate_architecture_doc", "review_api_design", "write_file"],
    # ...
}
```

---

## 7. 实施计划

### Phase 1: 通用工具（2 天）
1. 实现 `write_file` 工具
2. 实现 `search_code` 工具
3. 实现 `run_command` 工具（安全白名单）
4. 实现 `generate_code` 通用模板引擎
5. 测试覆盖

### Phase 2: 角色专用工具（3 天）
1. backend-dev 工具（4 个）
2. frontend-dev 工具（3 个）
3. 其他角色工具（各 1-2 个）
4. 测试覆盖

### Phase 3: 工作流定义（2 天）
1. 定义 9 个角色的标准工作流
2. 工作流解析与执行
3. 测试覆盖

### Phase 4: 集成与验证（1 天）
1. CLI 注册新工具和工作流
2. 全量回归测试
3. 文档更新

---

## 8. 风险评估

| 风险 | 缓解措施 |
|---|---|
| 工具生成代码质量不稳定 | 模板化生成 + 人工 review 环节 |
| 文件写入误操作 | 路径校验 + 备份机制 |
| 工作流过于僵化 | 支持条件分支和人工干预点 |
| 测试覆盖不足 | 每个工具至少 3 个测试用例 |

---

## 9. 完成定义

- [ ] 9 个角色各新增 3-5 个工具
- [ ] 9 个角色各新增 3 个标准工作流
- [ ] 新增工具测试全部通过
- [ ] 原有 210 个测试全部通过
- [ ] CLI 支持 `tool-run` 调用所有新工具
- [ ] CLI 支持 `workflow` 执行新工作流
- [ ] 文档更新完成
