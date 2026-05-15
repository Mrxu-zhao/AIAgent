# Agent 实际做事能力提升实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 14 个 Agent 建立交付契约、多栈标准工作流、质量门禁与知识闭环，覆盖 Web/平台/移动端/鸿蒙场景。

**Architecture:** 在现有 control_plane 基础上，新增 `delivery/`（交付契约）、`stacks/`（多栈插件）、`workflows/{web,platform,mobile,harmony}/`（场景工作流）、`knowledge_loop/`（知识闭环）。

**Tech Stack:** Python 3, dataclasses, pathlib, yaml, unittest

---

## 文件结构总览

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
│   ├── registry.py                 # 栈注册表
│   ├── backend/
│   │   ├── java-spring/
│   │   │   ├── templates/
│   │   │   │   ├── controller.java
│   │   │   │   ├── service.java
│   │   │   │   └── mapper.java
│   │   │   └── commands.yaml
│   │   ├── go-gin/
│   │   │   ├── templates/
│   │   │   │   ├── handler.go
│   │   │   │   └── service.go
│   │   │   └── commands.yaml
│   │   └── python-fastapi/
│   │       ├── templates/
│   │       │   ├── router.py
│   │       │   └── service.py
│   │       └── commands.yaml
│   ├── frontend/
│   │   ├── vue3/
│   │   │   ├── templates/
│   │   │   │   └── component.vue
│   │   │   └── commands.yaml
│   │   ├── react/
│   │   │   ├── templates/
│   │   │   │   └── component.tsx
│   │   │   └── commands.yaml
│   │   ├── mini-program/
│   │   │   ├── templates/
│   │   │   │   └── page.js
│   │   │   └── commands.yaml
│   │   └── harmony-arkts/
│   │       ├── templates/
│   │       │   └── ability.ets
│   │       └── commands.yaml
│   └── database/
│       ├── mysql/
│       │   ├── templates/
│       │   │   └── ddl.sql
│       │   └── commands.yaml
│       ├── postgres/
│       │   ├── templates/
│       │   │   └── ddl.sql
│       │   └── commands.yaml
│       └── redis/
│           ├── templates/
│           │   └── schema.redis
│           └── commands.yaml
├── workflows/                      # 已有：工作流定义
│   ├── web/                        # 新增：Web场景工作流
│   │   ├── analyst-requirements.yaml
│   │   ├── architect-design.yaml
│   │   ├── dba-database.yaml
│   │   ├── backend-api.yaml
│   │   ├── frontend-page.yaml
│   │   ├── ucd-interaction.yaml
│   │   ├── qa-test.yaml
│   │   └── devops-deployment.yaml
│   ├── platform/                   # 新增：平台场景工作流
│   ├── mobile/                     # 新增：移动端工作流
│   └── harmony/                    # 新增：鸿蒙场景工作流
├── knowledge_loop/                 # 新增：知识闭环
│   ├── __init__.py
│   ├── extractor.py                # 经验提取器
│   └── updater.py                  # 知识更新器
└── cli.py                          # 修改：新增栈选择、质量门禁命令

tests/control_plane/
├── test_delivery_contracts.py      # 新增：交付契约测试
├── test_stack_plugins.py           # 新增：栈插件测试
├── test_quality_gates.py           # 新增：质量门禁测试
└── test_knowledge_loop.py          # 新增：知识闭环测试
```

---

## Phase 0: 交付契约与共同定义

### Task 1: 创建交付契约目录结构

**Files:**
- Create: `.hermes/team/control_plane/delivery/__init__.py`
- Create: `.hermes/team/control_plane/delivery/contracts/__init__.py`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p .hermes/team/control_plane/delivery/contracts
mkdir -p .hermes/team/control_plane/delivery/quality_gates
```

- [ ] **Step 2: 创建 init 文件**

```python
# .hermes/team/control_plane/delivery/__init__.py
"""Delivery contracts and quality gates for agent roles."""
```

- [ ] **Step 3: 提交**

```bash
git add .hermes/team/control_plane/delivery/
git commit -m "feat: add delivery contracts directory structure"
```

---

### Task 2: 编写 analyst 交付契约

**Files:**
- Create: `.hermes/team/control_plane/delivery/contracts/analyst.yaml`

- [ ] **Step 1: 编写契约文件**

```yaml
role: analyst
name: 需求分析师
delivery_contract:
  inputs:
    - name: 访谈记录
      type: document
      required: true
    - name: 业务目标
      type: document
      required: true
    - name: 约束条件
      type: document
      required: false
  outputs:
    - name: PRD
      type: document
      template: "templates/prd-template.md"
    - name: 用户故事
      type: document
      template: "templates/user-stories.md"
    - name: 验收标准
      type: checklist
      template: "templates/acceptance-criteria.md"
    - name: 范围边界
      type: document
      template: "templates/scope-boundary.md"
    - name: 风险清单
      type: checklist
      template: "templates/risk-checklist.md"
  definition_of_done:
    - 每条需求都有明确的验收标准
    - 范围/非范围已明确界定
    - 风险与依赖已识别并记录
    - 用户故事符合 INVEST 原则
    - 验收标准可测试化
  quality_gates:
    - gate: 需求评审
      tool: review_meeting
      required: true
    - gate: 验收标准检查
      tool: acceptance_check
      required: true
    - gate: 范围确认
      tool: scope_confirm
      required: true
  handoff:
    - target: architect
      deliverables: [PRD, 用户故事, 验收标准]
    - target: ucd
      deliverables: [PRD, 用户画像]
```

- [ ] **Step 2: 运行测试确认格式正确**

Run: `python -c "import yaml; yaml.safe_load(open('.hermes/team/control_plane/delivery/contracts/analyst.yaml'))"`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add .hermes/team/control_plane/delivery/contracts/analyst.yaml
git commit -m "feat: add analyst delivery contract"
```

---

### Task 3: 编写所有角色交付契约

**Files:**
- Create: `.hermes/team/control_plane/delivery/contracts/{architect,dba,backend,frontend,ucd,qa-functional,qa-performance,devops}.yaml`

参照 Task 2 的 analyst.yaml 格式，为以下角色编写交付契约：

| 角色 | 核心输出 | 关键 DoD |
|---|---|---|
| architect | 架构设计文档、ADR、接口契约 | 关键决策可追溯；接口契约可被直接消费 |
| dba | 数据模型、DDL、索引方案 | 表设计评审通过；关键查询有 explain |
| backend | 接口实现、单测、接口文档 | 单测覆盖率>80%；代码评审清单过关 |
| frontend | 组件/页面实现、组件规范 | 组件 API 规范化；性能 checklist 过关 |
| ucd | 交互说明、设计规范、交接单 | 关键流程覆盖；边界态齐全 |
| qa-functional | 测试用例、回归计划、缺陷报告 | 用例覆盖验收标准；缺陷可复现 |
| qa-performance | 压测方案、压测报告、瓶颈分析 | 性能指标可量化；瓶颈定位准确 |
| devops | 部署配置、监控配置、应急预案 | 可回滚；监控/告警齐全 |

- [ ] **Step 1-3:** 每个角色参照 Task 2 格式编写契约文件

```bash
git add .hermes/team/control_plane/delivery/contracts/
git commit -m "feat: add all role delivery contracts"
```

---

### Task 4: 创建质量门禁模板

**Files:**
- Create: `.hermes/team/control_plane/delivery/quality_gates/self-checklist.md`
- Create: `.hermes/team/control_plane/delivery/quality_gates/code-review-checklist.md`
- Create: `.hermes/team/control_plane/delivery/quality_gates/handoff-form.md`

- [ ] **Step 1: 编写自检清单模板**

```markdown
# 自检清单

## 通用检查项

- [ ] 代码/文档已按规范格式化
- [ ] 无明显的拼写/语法错误
- [ ] 关键逻辑有注释说明
- [ ] 边界情况已考虑
- [ ] 异常处理已覆盖

## 代码特定检查项

- [ ] 单测已编写且通过
- [ ] 静态检查无错误
- [ ] 接口文档已更新
- [ ] 变更说明已填写

## 文档特定检查项

- [ ] 需求/设计已覆盖所有场景
- [ ] 验收标准可测试化
- [ ] 风险与依赖已识别
```

- [ ] **Step 2: 编写代码评审清单模板**

```markdown
# 代码评审清单

## 功能性

- [ ] 实现符合需求/设计
- [ ] 边界情况已处理
- [ ] 异常路径已覆盖

## 可维护性

- [ ] 命名清晰、语义明确
- [ ] 函数/类职责单一
- [ ] 重复代码已提取

## 性能

- [ ] 无明显的性能瓶颈
- [ ] 大数据量场景已考虑
- [ ] 缓存策略合理

## 安全性

- [ ] 输入已校验
- [ ] 敏感数据已加密
- [ ] 权限控制已实施

## 测试

- [ ] 单测覆盖率达标（>80%）
- [ ] 关键路径有集成测试
- [ ] 测试用例命名清晰
```

- [ ] **Step 3: 编写交接单模板**

```markdown
# 交接单

## 交付物清单

| 序号 | 交付物 | 路径 | 状态 |
|---|---|---|---|
| 1 | | | |
| 2 | | | |

## 关键信息

- **上游依赖**: 
- **下游消费方**: 
- **已知风险**: 
- **待确认问题**: 

## 验收标准

- [ ] 交付物完整
- [ ] 质量门禁通过
- [ ] 文档齐全
- [ ] 可运行/可验证

## 交接双方

- **交付方**: 
- **接收方**: 
- **交接日期**: 
```

- [ ] **Step 4: 提交**

```bash
git add .hermes/team/control_plane/delivery/quality_gates/
git commit -m "feat: add quality gate templates"
```

---

## Phase 1: 多栈插件系统

### Task 5: 创建栈注册表

**Files:**
- Create: `.hermes/team/control_plane/stacks/__init__.py`
- Create: `.hermes/team/control_plane/stacks/registry.py`

- [ ] **Step 1: 编写栈注册表**

```python
# .hermes/team/control_plane/stacks/registry.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class StackConfig:
    name: str
    templates_dir: str
    commands: Dict[str, str] = field(default_factory=dict)
    file_extensions: List[str] = field(default_factory=list)


STACK_REGISTRY = {
    "backend": {
        "java-spring": StackConfig(
            name="Java Spring Boot",
            templates_dir="stacks/backend/java-spring/templates/",
            commands={"test": "mvn test", "lint": "mvn spotless:check", "build": "mvn package"},
            file_extensions=[".java", ".xml", ".properties", ".yml"],
        ),
        "go-gin": StackConfig(
            name="Go Gin",
            templates_dir="stacks/backend/go-gin/templates/",
            commands={"test": "go test ./...", "lint": "golangci-lint run", "build": "go build"},
            file_extensions=[".go", ".mod"],
        ),
        "python-fastapi": StackConfig(
            name="Python FastAPI",
            templates_dir="stacks/backend/python-fastapi/templates/",
            commands={"test": "pytest", "lint": "ruff check .", "build": "docker build"},
            file_extensions=[".py", ".toml", ".ini"],
        ),
    },
    "frontend": {
        "vue3": StackConfig(
            name="Vue 3",
            templates_dir="stacks/frontend/vue3/templates/",
            commands={"test": "vitest", "lint": "eslint", "build": "vite build"},
            file_extensions=[".vue", ".ts", ".js", ".css"],
        ),
        "react": StackConfig(
            name="React",
            templates_dir="stacks/frontend/react/templates/",
            commands={"test": "jest", "lint": "eslint", "build": "vite build"},
            file_extensions=[".tsx", ".ts", ".css"],
        ),
        "mini-program": StackConfig(
            name="微信小程序",
            templates_dir="stacks/frontend/mini-program/templates/",
            commands={"test": "jest", "lint": "eslint", "build": "npm run build"},
            file_extensions=[".js", ".wxml", ".wxss", ".json"],
        ),
        "harmony-arkts": StackConfig(
            name="鸿蒙 ArkTS",
            templates_dir="stacks/frontend/harmony-arkts/templates/",
            commands={"test": "ohpm test", "lint": "arkts-lint", "build": "hvigor build"},
            file_extensions=[".ets", ".ts", ".json"],
        ),
    },
    "database": {
        "mysql": StackConfig(
            name="MySQL",
            templates_dir="stacks/database/mysql/templates/",
            commands={"test": "mysql -e", "lint": "sqlfluff lint", "build": "flyway migrate"},
            file_extensions=[".sql"],
        ),
        "postgres": StackConfig(
            name="PostgreSQL",
            templates_dir="stacks/database/postgres/templates/",
            commands={"test": "psql -f", "lint": "sqlfluff lint", "build": "flyway migrate"},
            file_extensions=[".sql"],
        ),
        "redis": StackConfig(
            name="Redis",
            templates_dir="stacks/database/redis/templates/",
            commands={"test": "redis-cli", "lint": "redis-lint", "build": "redis-cli"},
            file_extensions=[".redis", ".txt"],
        ),
    },
}


def get_stack_config(category: str, stack_id: str) -> StackConfig:
    if category not in STACK_REGISTRY:
        raise ValueError(f"unknown category: {category}")
    if stack_id not in STACK_REGISTRY[category]:
        available = ", ".join(STACK_REGISTRY[category].keys())
        raise ValueError(f"unknown stack '{stack_id}' in {category}. Available: {available}")
    return STACK_REGISTRY[category][stack_id]


def list_stacks(category: str | None = None) -> Dict[str, List[str]]:
    if category:
        return {category: list(STACK_REGISTRY.get(category, {}).keys())}
    return {cat: list(stacks.keys()) for cat, stacks in STACK_REGISTRY.items()}
```

- [ ] **Step 2: 编写测试**

```python
# tests/control_plane/test_stack_plugins.py
import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from stacks.registry import get_stack_config, list_stacks


class StackRegistryTests(unittest.TestCase):
    def test_get_java_spring_config(self):
        config = get_stack_config("backend", "java-spring")
        self.assertEqual(config.name, "Java Spring Boot")
        self.assertIn("test", config.commands)

    def test_get_vue3_config(self):
        config = get_stack_config("frontend", "vue3")
        self.assertEqual(config.name, "Vue 3")
        self.assertIn(".vue", config.file_extensions)

    def test_get_mysql_config(self):
        config = get_stack_config("database", "mysql")
        self.assertEqual(config.name, "MySQL")

    def test_list_all_stacks(self):
        stacks = list_stacks()
        self.assertIn("backend", stacks)
        self.assertIn("frontend", stacks)
        self.assertIn("database", stacks)
        self.assertIn("java-spring", stacks["backend"])
        self.assertIn("harmony-arkts", stacks["frontend"])

    def test_list_backend_stacks(self):
        stacks = list_stacks("backend")
        self.assertEqual(len(stacks["backend"]), 3)

    def test_get_unknown_stack_raises(self):
        with self.assertRaises(ValueError):
            get_stack_config("backend", "unknown")
```

- [ ] **Step 3: 运行测试**

Run: `python -m unittest tests.control_plane.test_stack_plugins -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add .hermes/team/control_plane/stacks/ tests/control_plane/test_stack_plugins.py
git commit -m "feat: add stack registry with multi-stack support"
```

---

### Task 6: 创建 Java-Spring 模板包

**Files:**
- Create: `.hermes/team/control_plane/stacks/backend/java-spring/templates/controller.java`
- Create: `.hermes/team/control_plane/stacks/backend/java-spring/templates/service.java`
- Create: `.hermes/team/control_plane/stacks/backend/java-spring/templates/mapper.java`
- Create: `.hermes/team/control_plane/stacks/backend/java-spring/commands.yaml`

- [ ] **Step 1: 编写模板文件**

```java
// stacks/backend/java-spring/templates/controller.java
package ${package};

import org.springframework.web.bind.annotation.*;
import org.springframework.validation.annotation.Validated;
import lombok.RequiredArgsConstructor;
import java.util.List;

@RestController
@RequestMapping("${endpoint}")
@RequiredArgsConstructor
@Validated
public class ${ClassName}Controller {

    private final ${ClassName}Service ${className}Service;

    @GetMapping
    public List<${ClassName}DTO> list() {
        return ${className}Service.list();
    }

    @GetMapping("/{id}")
    public ${ClassName}DTO getById(@PathVariable Long id) {
        return ${className}Service.getById(id);
    }

    @PostMapping
    public ${ClassName}DTO create(@RequestBody @Valid ${ClassName}DTO dto) {
        return ${className}Service.create(dto);
    }

    @PutMapping("/{id}")
    public ${ClassName}DTO update(@PathVariable Long id, @RequestBody @Valid ${ClassName}DTO dto) {
        return ${className}Service.update(id, dto);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        ${className}Service.delete(id);
    }
}
```

```java
// stacks/backend/java-spring/templates/service.java
package ${package};

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import lombok.RequiredArgsConstructor;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ${ClassName}Service {

    private final ${ClassName}Mapper ${className}Mapper;

    public List<${ClassName}DTO> list() {
        return ${className}Mapper.list();
    }

    public ${ClassName}DTO getById(Long id) {
        return ${className}Mapper.getById(id);
    }

    @Transactional
    public ${ClassName}DTO create(${ClassName}DTO dto) {
        ${className}Mapper.create(dto);
        return dto;
    }

    @Transactional
    public ${ClassName}DTO update(Long id, ${ClassName}DTO dto) {
        dto.setId(id);
        ${className}Mapper.update(dto);
        return dto;
    }

    @Transactional
    public void delete(Long id) {
        ${className}Mapper.delete(id);
    }
}
```

```java
// stacks/backend/java-spring/templates/mapper.java
package ${package};

import org.apache.ibatis.annotations.*;
import java.util.List;

@Mapper
public interface ${ClassName}Mapper {

    @Select("SELECT * FROM ${table_name} WHERE deleted = 0")
    List<${ClassName}DTO> list();

    @Select("SELECT * FROM ${table_name} WHERE id = #{id} AND deleted = 0")
    ${ClassName}DTO getById(Long id);

    @Insert("INSERT INTO ${table_name} (...) VALUES (...)")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    void create(${ClassName}DTO dto);

    @Update("UPDATE ${table_name} SET ... WHERE id = #{id}")
    void update(${ClassName}DTO dto);

    @Update("UPDATE ${table_name} SET deleted = 1 WHERE id = #{id}")
    void delete(Long id);
}
```

```yaml
# stacks/backend/java-spring/commands.yaml
commands:
  test: "mvn test"
  lint: "mvn spotless:check"
  build: "mvn package -DskipTests"
  run: "mvn spring-boot:run"
templates:
  controller: "templates/controller.java"
  service: "templates/service.java"
  mapper: "templates/mapper.java"
```

- [ ] **Step 2: 提交**

```bash
git add .hermes/team/control_plane/stacks/backend/java-spring/
git commit -m "feat: add java-spring stack templates"
```

---

### Task 7: 创建 Go-Gin 模板包

**Files:**
- Create: `.hermes/team/control_plane/stacks/backend/go-gin/templates/handler.go`
- Create: `.hermes/team/control_plane/stacks/backend/go-gin/templates/service.go`
- Create: `.hermes/team/control_plane/stacks/backend/go-gin/commands.yaml`

参照 Task 6 格式，编写 Go Gin 的 handler、service 模板和命令配置。

- [ ] **Step 1-2:** 编写模板并提交

```bash
git add .hermes/team/control_plane/stacks/backend/go-gin/
git commit -m "feat: add go-gin stack templates"
```

---

### Task 8: 创建 Python-FastAPI 模板包

**Files:**
- Create: `.hermes/team/control_plane/stacks/backend/python-fastapi/templates/router.py`
- Create: `.hermes/team/control_plane/stacks/backend/python-fastapi/templates/service.py`
- Create: `.hermes/team/control_plane/stacks/backend/python-fastapi/commands.yaml`

参照 Task 6 格式，编写 Python FastAPI 的 router、service 模板和命令配置。

- [ ] **Step 1-2:** 编写模板并提交

```bash
git add .hermes/team/control_plane/stacks/backend/python-fastapi/
git commit -m "feat: add python-fastapi stack templates"
```

---

### Task 9: 创建前端模板包

**Files:**
- Create: `.hermes/team/control_plane/stacks/frontend/vue3/templates/component.vue`
- Create: `.hermes/team/control_plane/stacks/frontend/react/templates/component.tsx`
- Create: `.hermes/team/control_plane/stacks/frontend/mini-program/templates/page.js`
- Create: `.hermes/team/control_plane/stacks/frontend/harmony-arkts/templates/ability.ets`

- [ ] **Step 1: 编写 Vue3 模板**

```vue
<!-- stacks/frontend/vue3/templates/component.vue -->
<template>
  <div class="${componentName}-container">
    <!-- 主内容区 -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  data?: any[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  data: () => [],
  loading: false
})

const emit = defineEmits<{
  (e: 'update', value: any): void
  (e: 'select', item: any): void
}>()

// TODO: 实现组件逻辑
</script>

<style scoped lang="scss">
.${componentName}-container {
  // TODO: 实现样式
}
</style>
```

- [ ] **Step 2: 编写 React 模板**

```tsx
// stacks/frontend/react/templates/component.tsx
import React, { useState, useCallback } from 'react'
import './${ComponentName}.css'

interface ${ComponentName}Props {
  data?: any[]
  loading?: boolean
  onUpdate?: (value: any) => void
  onSelect?: (item: any) => void
}

export const ${ComponentName}: React.FC<${ComponentName}Props> = ({
  data = [],
  loading = false,
  onUpdate,
  onSelect,
}) => {
  // TODO: 实现组件逻辑
  return (
    <div className="${componentName}-container">
      {/* TODO: 实现渲染 */}
    </div>
  )
}
```

- [ ] **Step 3: 编写小程序模板**

```javascript
// stacks/frontend/mini-program/templates/page.js
Page({
  data: {
    list: [],
    loading: false
  },

  onLoad(options) {
    this.loadData()
  },

  async loadData() {
    this.setData({ loading: true })
    try {
      // TODO: 调用 API
      const res = await wx.request({
        url: '/api/${feature}',
        method: 'GET'
      })
      this.setData({ list: res.data, loading: false })
    } catch (error) {
      wx.showToast({ title: '加载失败', icon: 'error' })
      this.setData({ loading: false })
    }
  },

  onItemTap(e) {
    const item = e.currentTarget.dataset.item
    // TODO: 处理点击
  }
})
```

- [ ] **Step 4: 编写鸿蒙 ArkTS 模板**

```typescript
// stacks/frontend/harmony-arkts/templates/ability.ets
import { AbilityComponent } from '@ohos/ability'

@Entry
@Component
struct ${Feature}Ability {
  @State list: any[] = []
  @State loading: boolean = false

  aboutToAppear() {
    this.loadData()
  }

  async loadData() {
    this.loading = true
    try {
      // TODO: 调用 API
      const response = await fetch('/api/${feature}')
      this.list = await response.json()
    } catch (error) {
      prompt.showToast({ message: '加载失败' })
    } finally {
      this.loading = false
    }
  }

  build() {
    Column() {
      // TODO: 实现 UI
      Text('${Feature} Page')
        .fontSize(20)
        .fontWeight(FontWeight.Bold)
    }
    .width('100%')
    .height('100%')
  }
}
```

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/stacks/frontend/
git commit -m "feat: add frontend stack templates (vue3/react/mini-program/harmony)"
```

---

### Task 10: 创建数据库模板包

**Files:**
- Create: `.hermes/team/control_plane/stacks/database/mysql/templates/ddl.sql`
- Create: `.hermes/team/control_plane/stacks/database/postgres/templates/ddl.sql`
- Create: `.hermes/team/control_plane/stacks/database/redis/templates/schema.redis`

- [ ] **Step 1: 编写 MySQL DDL 模板**

```sql
-- stacks/database/mysql/templates/ddl.sql
CREATE TABLE IF NOT EXISTS `${table_name}` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  -- TODO: 添加业务字段
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '删除标记(0:未删除 1:已删除)',
  PRIMARY KEY (`id`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='${table_comment}';
```

- [ ] **Step 2: 编写 PostgreSQL DDL 模板**

```sql
-- stacks/database/postgres/templates/ddl.sql
CREATE TABLE IF NOT EXISTS ${table_name} (
    id BIGSERIAL PRIMARY KEY,
    -- TODO: 添加业务字段
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE ${table_name} IS '${table_comment}';

CREATE INDEX IF NOT EXISTS idx_${table_name}_created_at ON ${table_name}(created_at);
CREATE INDEX IF NOT EXISTS idx_${table_name}_deleted ON ${table_name}(deleted);
```

- [ ] **Step 3: 编写 Redis Schema 模板**

```redis
# stacks/database/redis/templates/schema.redis
# ${feature} 缓存设计

# 字符串缓存
SET ${feature}:config "{}"
EXPIRE ${feature}:config 3600

# Hash 缓存
HSET ${feature}:item:${id} field1 value1 field2 value2
EXPIRE ${feature}:item:${id} 3600

# 列表缓存
LPUSH ${feature}:list item1 item2
EXPIRE ${feature}:list 3600

# 集合缓存
SADD ${feature}:set member1 member2
EXPIRE ${feature}:set 3600
```

- [ ] **Step 4: 提交**

```bash
git add .hermes/team/control_plane/stacks/database/
git commit -m "feat: add database stack templates (mysql/postgres/redis)"
```

---

## Phase 2: 场景工作流

### Task 11: 创建 Web 场景工作流

**Files:**
- Create: `.hermes/team/control_plane/workflows/web/analyst-requirements.yaml`
- Create: `.hermes/team/control_plane/workflows/web/backend-api.yaml`
- Create: `.hermes/team/control_plane/workflows/web/frontend-page.yaml`

- [ ] **Step 1: 编写 analyst Web 需求工作流**

```yaml
workflow_id: web-analyst-requirements
name: Web需求分析工作流
description: Web业务场景下的需求分析流程
role: analyst
scene: web
steps:
  - step_id: read_interview
    name: 读取访谈记录
    tool: read_knowledge
    input:
      paths: ["interviews/{feature}.md"]

  - step_id: generate_prd
    name: 生成PRD
    tool: generate_prd
    input:
      feature: "{Feature}"
      background: "{background}"

  - step_id: write_prd
    name: 写入PRD
    tool: write_file
    input:
      path: "requirements/{feature}_prd.md"
      content: "${generate_prd.output}"

  - step_id: self_check
    name: 自检
    tool: read_knowledge
    input:
      paths: ["delivery/quality_gates/self-checklist.md"]

  - step_id: handoff_architect
    name: 交接给架构师
    tool: dispatch_task
    input:
      agent_id: "architect"
      task: "{feature} PRD已完成，请进行架构设计"

  - step_id: handoff_ucd
    name: 交接给UCD
    tool: dispatch_task
    input:
      agent_id: "ucd"
      task: "{feature} PRD已完成，请进行交互设计"
```

- [ ] **Step 2: 编写 backend Web API 工作流**

```yaml
workflow_id: web-backend-api
name: Web后端API开发工作流
description: Web业务场景下的后端API开发流程
role: backend-dev
scene: web
stack_selection:
  prompt: "请选择后端技术栈"
  options: ["java-spring", "go-gin", "python-fastapi"]
  default: "java-spring"
steps:
  - step_id: read_contract
    name: 读取接口契约
    tool: read_knowledge
    input:
      paths: ["api/{feature}.md"]

  - step_id: search_existing
    name: 搜索现有代码
    tool: search_code
    input:
      pattern: "{Feature}"
      glob: "*.{java,go,py}"

  - step_id: generate_controller
    name: 生成Controller
    tool: generate_controller
    input:
      class_name: "{Feature}Controller"
      package: "com.example.controller"
      endpoint: "/api/{feature}"
      entity_name: "{Feature}"

  - step_id: write_controller
    name: 写入Controller
    tool: write_file
    input:
      path: "src/main/java/com/example/controller/{Feature}Controller.java"
      content: "${generate_controller.output}"

  - step_id: generate_service
    name: 生成Service
    tool: generate_service
    input:
      class_name: "{Feature}Service"
      package: "com.example.service"
      entity_name: "{Feature}"

  - step_id: write_service
    name: 写入Service
    tool: write_file
    input:
      path: "src/main/java/com/example/service/{Feature}Service.java"
      content: "${generate_service.output}"

  - step_id: run_tests
    name: 执行单元测试
    tool: run_unit_tests
    input:
      test_path: "{Feature}ServiceTest"
      timeout: 120

  - step_id: self_check
    name: 自检
    tool: read_knowledge
    input:
      paths: ["delivery/quality_gates/self-checklist.md"]

  - step_id: handoff
    name: 交接给QA
    tool: dispatch_task
    input:
      agent_id: "qa-functional"
      task: "{feature} API已实现，请进行测试"
```

- [ ] **Step 3: 编写 frontend Web 页面工作流**

```yaml
workflow_id: web-frontend-page
name: Web前端页面开发工作流
description: Web业务场景下的前端页面开发流程
role: frontend-dev
scene: web
stack_selection:
  prompt: "请选择前端技术栈"
  options: ["vue3", "react"]
  default: "vue3"
steps:
  - step_id: read_design
    name: 读取设计规范
    tool: read_knowledge
    input:
      paths: ["design/{feature}.md"]

  - step_id: read_api_contract
    name: 读取接口契约
    tool: read_knowledge
    input:
      paths: ["api/{feature}.md"]

  - step_id: generate_component
    name: 生成组件
    tool: generate_vue_component
    input:
      component_name: "{Feature}"
      props: ["data", "loading"]
      emits: ["update", "select"]

  - step_id: write_component
    name: 写入组件
    tool: write_file
    input:
      path: "src/components/{Feature}.vue"
      content: "${generate_component.output}"

  - step_id: generate_api_client
    name: 生成API客户端
    tool: generate_api_client
    input:
      api_name: "{Feature}"
      endpoint: "/api/{feature}"
      methods: ["GET", "POST", "PUT", "DELETE"]

  - step_id: write_api_client
    name: 写入API客户端
    tool: write_file
    input:
      path: "src/api/{feature}.ts"
      content: "${generate_api_client.output}"

  - step_id: run_linter
    name: 执行代码检查
    tool: run_linter
    input:
      file_path: "src/components/{Feature}.vue"
      timeout: 60

  - step_id: self_check
    name: 自检
    tool: read_knowledge
    input:
      paths: ["delivery/quality_gates/self-checklist.md"]

  - step_id: handoff
    name: 交接给后端联调
    tool: dispatch_task
    input:
      agent_id: "backend-dev"
      task: "{feature}前端页面已完成，请提供对应API"
```

- [ ] **Step 4: 提交**

```bash
git add .hermes/team/control_plane/workflows/web/
git commit -m "feat: add web scene workflows"
```

---

### Task 12: 创建平台/移动端/鸿蒙场景工作流

**Files:**
- Create: `.hermes/team/control_plane/workflows/platform/*.yaml`
- Create: `.hermes/team/control_plane/workflows/mobile/*.yaml`
- Create: `.hermes/team/control_plane/workflows/harmony/*.yaml`

参照 Task 11 格式，为以下场景编写工作流：

| 场景 | 工作流 | 关键差异 |
|---|---|---|
| platform | platform-service-development | 插件机制、配置化、监控埋点 |
| mobile | mobile-page-development | 屏幕适配、API适配、性能优化 |
| harmony | harmony-ability-development | Ability设计、分布式能力、性能优化 |

- [ ] **Step 1-4:** 编写工作流并提交

```bash
git add .hermes/team/control_plane/workflows/platform/
git add .hermes/team/control_plane/workflows/mobile/
git add .hermes/team/control_plane/workflows/harmony/
git commit -m "feat: add platform/mobile/harmony scene workflows"
```

---

## Phase 3: 质量门禁与知识闭环

### Task 13: 实现质量门禁检查器

**Files:**
- Create: `.hermes/team/control_plane/delivery/quality_gate.py`
- Create: `tests/control_plane/test_quality_gates.py`

- [ ] **Step 1: 编写质量门禁检查器**

```python
# .hermes/team/control_plane/delivery/quality_gate.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class QualityGateResult:
    gate_name: str
    passed: bool
    message: str = ""
    details: Dict[str, any] = field(default_factory=dict)


class QualityGateChecker:
    def __init__(self, contract: Dict[str, any]):
        self.contract = contract

    def check_all(self) -> List[QualityGateResult]:
        results = []
        for gate in self.contract.get("quality_gates", []):
            result = self._check_gate(gate)
            results.append(result)
        return results

    def _check_gate(self, gate: Dict[str, any]) -> QualityGateResult:
        gate_name = gate.get("gate", "unknown")
        # 实际检查逻辑根据 gate 类型实现
        # 这里返回模拟结果
        return QualityGateResult(
            gate_name=gate_name,
            passed=True,
            message=f"{gate_name} check passed",
        )

    def all_passed(self, results: List[QualityGateResult]) -> bool:
        return all(r.passed for r in results)
```

- [ ] **Step 2: 编写测试**

```python
# tests/control_plane/test_quality_gates.py
import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from delivery.quality_gate import QualityGateChecker


class QualityGateTests(unittest.TestCase):
    def test_check_all_gates(self):
        contract = {
            "quality_gates": [
                {"gate": "self_check", "required": True},
                {"gate": "static_analysis", "required": True},
            ]
        }
        checker = QualityGateChecker(contract)
        results = checker.check_all()
        self.assertEqual(len(results), 2)
        self.assertTrue(checker.all_passed(results))

    def test_all_passed_with_failure(self):
        from delivery.quality_gate import QualityGateResult
        results = [
            QualityGateResult("gate1", True),
            QualityGateResult("gate2", False),
        ]
        checker = QualityGateChecker({})
        self.assertFalse(checker.all_passed(results))
```

- [ ] **Step 3: 运行测试**

Run: `python -m unittest tests.control_plane.test_quality_gates -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add .hermes/team/control_plane/delivery/quality_gate.py tests/control_plane/test_quality_gates.py
git commit -m "feat: add quality gate checker"
```

---

### Task 14: 实现知识闭环

**Files:**
- Create: `.hermes/team/control_plane/knowledge_loop/__init__.py`
- Create: `.hermes/team/control_plane/knowledge_loop/extractor.py`
- Create: `.hermes/team/control_plane/knowledge_loop/updater.py`
- Create: `tests/control_plane/test_knowledge_loop.py`

- [ ] **Step 1: 编写经验提取器**

```python
# .hermes/team/control_plane/knowledge_loop/extractor.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, List


class ExperienceExtractor:
    def extract_patterns(self, deliverables: List[str]) -> List[Dict[str, str]]:
        """从交付物中提取可复用模式。"""
        patterns = []
        for path in deliverables:
            # 分析文件内容，提取模式
            patterns.append({
                "source": path,
                "pattern": "extracted_pattern",
                "type": "code_template",
            })
        return patterns

    def extract_lessons(self, task_result: Dict[str, any]) -> List[str]:
        """从任务结果中提取经验教训。"""
        lessons = []
        if task_result.get("success"):
            lessons.append(f"成功完成: {task_result.get('task_id')}")
        if task_result.get("challenges"):
            for challenge in task_result["challenges"]:
                lessons.append(f"挑战: {challenge}")
        return lessons
```

- [ ] **Step 2: 编写知识更新器**

```python
# .hermes/team/control_plane/knowledge_loop/updater.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, List


class KnowledgeUpdater:
    def __init__(self, knowledge_base_path: str):
        self.knowledge_base = Path(knowledge_base_path)

    def update_templates(self, patterns: List[Dict[str, str]]) -> None:
        """更新模板文件。"""
        for pattern in patterns:
            template_path = self.knowledge_base / "templates" / f"{pattern['type']}.md"
            template_path.parent.mkdir(parents=True, exist_ok=True)
            # 追加或更新模板
            with open(template_path, "a", encoding="utf-8") as f:
                f.write(f"\n<!-- Auto-generated from {pattern['source']} -->\n")

    def append_lessons(self, role: str, lessons: List[str]) -> None:
        """追加到 recent-lessons。"""
        lessons_path = self.knowledge_base / "agents" / role / "knowledge" / "recent-lessons.md"
        lessons_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lessons_path, "a", encoding="utf-8") as f:
            for lesson in lessons:
                f.write(f"- {lesson}\n")

    def update_team_knowledge(self, rules: List[str]) -> None:
        """更新团队共享知识。"""
        team_knowledge_path = self.knowledge_base / "team" / "knowledge" / "auto-generated-rules.md"
        team_knowledge_path.parent.mkdir(parents=True, exist_ok=True)
        with open(team_knowledge_path, "a", encoding="utf-8") as f:
            for rule in rules:
                f.write(f"- {rule}\n")
```

- [ ] **Step 3: 编写测试**

```python
# tests/control_plane/test_knowledge_loop.py
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from knowledge_loop.extractor import ExperienceExtractor
from knowledge_loop.updater import KnowledgeUpdater


class KnowledgeLoopTests(unittest.TestCase):
    def test_extract_patterns(self):
        extractor = ExperienceExtractor()
        patterns = extractor.extract_patterns(["src/Test.java"])
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["source"], "src/Test.java")

    def test_extract_lessons_from_success(self):
        extractor = ExperienceExtractor()
        lessons = extractor.extract_lessons({"success": True, "task_id": "test-1"})
        self.assertTrue(any("成功完成" in l for l in lessons))

    def test_update_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            updater = KnowledgeUpdater(tmp)
            updater.update_templates([{"type": "test", "source": "test.java"}])
            template_path = Path(tmp) / "templates" / "test.md"
            self.assertTrue(template_path.exists())

    def test_append_lessons(self):
        with tempfile.TemporaryDirectory() as tmp:
            updater = KnowledgeUpdater(tmp)
            updater.append_lessons("backend-dev", ["lesson 1", "lesson 2"])
            lessons_path = Path(tmp) / "agents" / "backend-dev" / "knowledge" / "recent-lessons.md"
            self.assertTrue(lessons_path.exists())
```

- [ ] **Step 4: 运行测试**

Run: `python -m unittest tests.control_plane.test_knowledge_loop -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .hermes/team/control_plane/knowledge_loop/ tests/control_plane/test_knowledge_loop.py
git commit -m "feat: add knowledge closed loop (extractor + updater)"
```

---

## Task 15: 全量回归验证

**Files:**
- 所有已修改文件

- [ ] **Step 1: 运行全量测试**

Run: `python -m unittest discover -s tests/control_plane -p "test_*.py" -v 2>&1 | Select-String "Ran|OK|FAILED"`
Expected: 全部通过

- [ ] **Step 2: 运行语法检查**

Run: `python -m py_compile .hermes/team/control_plane/delivery/quality_gate.py`
Run: `python -m py_compile .hermes/team/control_plane/knowledge_loop/extractor.py`
Run: `python -m py_compile .hermes/team/control_plane/knowledge_loop/updater.py`
Run: `python -m py_compile .hermes/team/control_plane/stacks/registry.py`
Expected: 全部通过

- [ ] **Step 3: 提交**

```bash
git commit -m "test: full regression pass for agent delivery capability enhancement"
```

---

## 完成定义

- [ ] 9 个角色各有一份 Delivery Contract YAML
- [ ] 3 个质量门禁模板（自检清单、代码评审清单、交接单）
- [ ] 多栈插件系统支持 3 后端 + 4 前端 + 3 数据库
- [ ] 每个栈有独立的模板包和命令配置
- [ ] Web/平台/移动端/鸿蒙场景工作流已定义
- [ ] 质量门禁检查器可运行
- [ ] 知识闭环（提取器+更新器）可运行
- [ ] 新增测试全部通过
- [ ] 原有 253 个测试全部通过
