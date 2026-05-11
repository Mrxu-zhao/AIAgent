# Element Plus 组件设计理念

## 一、设计理念

Element Plus 是基于 Vue 3 的组件库，遵循以下设计理念：

### 1. 一致性 (Consistency)
- 与现实世界一致：隐喻真实世界的操作
- 操作可逆：提供撤销功能
- 反馈及时：每个操作都有明确反馈

### 2. 效率 (Efficiency)
- 简化流程：减少操作步骤
- 容错性：帮助用户从错误中恢复
- 定制化：支持灵活配置

### 3. 可控 (Controllability)
- 用户主导：用户决定操作顺序
- 可中断：支持取消正在进行的操作
- 可见性：展示系统状态

## 二、核心组件使用规范

### 1. Button 按钮

#### 类型
| 类型 | 场景 | 色值 |
|------|------|------|
| primary | 主要操作，每个区域一个 | #409EFF |
| success | 正向操作，通过、成功 | #67C23A |
| warning | 警告操作，待审核 | #E6A23C |
| danger | 危险操作，删除、禁用 | #F56C6C |
| info | 默认操作 | #909399 |
| text | 辅助操作、链接 | 无背景 |

#### 尺寸
| 尺寸 | 高度 | 字号 | 适用场景 |
|------|------|------|----------|
| large | 40px | 14px | 表单提交 |
| default | 32px | 14px | 默认 |
| small | 24px | 12px | 紧凑表格 |

#### 状态
- 默认态：正常可点击
- Hover：轻微加深背景
- Active：进一步加深
- Disabled：50% 透明度，禁止点击
- Loading：显示加载图标，禁止点击

### 2. Table 表格

#### 基础用法
```vue
<el-table :data="tableData" stripe border>
  <el-table-column prop="name" label="姓名" />
  <el-table-column prop="status" label="状态">
    <template #default="{ row }">
      <el-tag :type="getStatusType(row.status)">
        {{ getStatusText(row.status) }}
      </el-tag>
    </template>
  </el-table-column>
</el-table>
```

#### 列配置规范
| 列类型 | 宽度建议 | 对齐方式 |
|--------|----------|----------|
| 复选框 | 40px | 居中 |
| 序号 | 60px | 居中 |
| 操作按钮 | 160px | 居中 |
| 文字 | 自适应，最小 80px | 左对齐 |
| 数字/金额 | 120px | 右对齐 |
| 时间 | 160px | 居中 |

#### 交互规范
- 行 Hover：背景色 #F5F7FA
- 行选中：背景色 #ECF5FF
- 排序图标：右侧显示
- 可编辑单元格：双击进入编辑

### 3. Form 表单

#### 布局模式
```vue
<!-- 行内表单 -->
<el-form :inline="true">
  <el-form-item label="审批人">
    <el-input v-model="form.user" />
  </el-form-item>
</el-form>

<!-- 栅格表单 -->
<el-form label-position="right" label-width="120px">
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="名称">
        <el-input v-model="form.name" />
      </el-form-item>
    </el-col>
  </el-row>
</el-form>
```

#### 校验规则
```javascript
const rules = {
  name: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { min: 2, max: 20, message: '长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱', trigger: ['blur', 'change'] }
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ]
}
```

#### 校验触发时机
| 触发方式 | 适用场景 |
|----------|----------|
| blur | 输入完成离开 |
| change | 值变化时（适合选择器） |
| blur,change | 严格校验（适合手机号等） |

### 4. Dialog 对话框

#### 尺寸规范
| 尺寸 | 宽度 | 适用场景 |
|------|------|----------|
| small | 400px | 确认操作 |
| default | 500px | 表单编辑 |
| large | 800px | 复杂表单 |
| full | 90vw | 全屏查看 |

#### 结构规范
```
┌──────────────────────────────────┐
│ 标题                    [X 关闭]│
├──────────────────────────────────┤
│                                  │
│         内容区域                  │
│                                  │
├──────────────────────────────────┤
│              [取消]  [确定]      │
└──────────────────────────────────┘
```

### 5. Select 选择器

#### 单选 vs 多选
| 类型 | 属性 | 使用场景 |
|------|------|----------|
| 单选 | `multiple={false}` | 性别、状态 |
| 多选 | `multiple={true}` | 角色、标签 |

#### 分页加载
```vue
<el-select
  v-model="value"
  filterable
  remote
  :remote-method="searchMethod"
  :loading="loading"
  placeholder="请输入关键词搜索"
>
  <el-option
    v-for="item in options"
    :key="item.id"
    :label="item.name"
    :value="item.id"
  />
</el-select>
```

### 6. DatePicker 日期选择器

#### 格式规范
| 类型 | 格式 | 示例 |
|------|------|------|
| 日期 | YYYY-MM-DD | 2024-01-15 |
| 日期时间 | YYYY-MM-DD HH:mm:ss | 2024-01-15 14:30:00 |
| 年月 | YYYY-MM | 2024-01 |
| 日期范围 | YYYY-MM-DD - YYYY-MM-DD | 2024-01-01 - 2024-01-31 |

### 7. Pagination 分页

#### 经典布局
```vue
<el-pagination
  v-model:current-page="currentPage"
  v-model:page-size="pageSize"
  :total="total"
  :page-sizes="[10, 20, 50, 100]"
  layout="total, sizes, prev, pager, next, jumper"
  @size-change="handleSizeChange"
  @current-change="handleCurrentChange"
/>
```

#### 分页配置
- 默认每页 10 条
- 可选：[10, 20, 50, 100]
- 显示总数、页码、跳页

## 三、组件组合模式

### 筛选 + 表格 + 分页
```vue
<template>
  <!-- 筛选区 -->
  <div class="filter-bar">
    <el-form :inline="true" :model="queryParams">
      <el-form-item label="状态">
        <el-select v-model="queryParams.status">
          <el-option label="全部" value="" />
          <el-option label="启用" value="1" />
          <el-option label="禁用" value="0" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="queryParams.keyword" clearable />
      </el-form-item>
      <el-form-item>
        <el-button @click="handleReset">重置</el-button>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
      </el-form-item>
    </el-form>
  </div>

  <!-- 表格区 -->
  <el-table :data="tableData" v-loading="loading">
    <!-- 列定义... -->
  </el-table>

  <!-- 分页区 -->
  <el-pagination
    v-model:current-page="pagination.page"
    v-model:page-size="pagination.size"
    :total="pagination.total"
    @current-change="fetchData"
  />
</template>
```

## 四、自定义组件封装

### 基础封装原则
1. 继承 Element Plus 组件属性
2. 暴露 Events 和 Slots
3. 统一样式风格
4. 提供 TypeScript 类型定义

### 示例：SearchForm
```vue
<!-- components/SearchForm.vue -->
<template>
  <el-form :inline="true" :model="modelValue" v-bind="$attrs">
    <slot />
    <el-form-item>
      <el-button @click="handleReset">重置</el-button>
      <el-button type="primary" @click="handleSearch">搜索</el-button>
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: Record<string, any>
}>()
const emit = defineEmits(['update:modelValue', 'search', 'reset'])

// 封装通用逻辑
</script>
```

## 五、注意事项

1. **避免过度封装**：保持组件的灵活性
2. **保持一致性**：统一使用 Element Plus 样式
3. **响应式适配**：考虑不同屏幕尺寸
4. **无障碍支持**：关注 a11y 特性
5. **性能优化**：大表格使用虚拟滚动
