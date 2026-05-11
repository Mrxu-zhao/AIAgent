# 表单设计最佳实践

## 一、表单设计原则

### 1. 用户友好
- 减少认知负担，一次只问一个问题
- 使用用户熟悉的语言和术语
- 默认值应该是最常见的选项

### 2. 效率优先
- 必填项最小化
- 自动格式化（手机号、银行卡）
- 支持 Tab 键顺序切换

### 3. 容错设计
- 实时校验，错误及时提示
- 不强制要求格式（如手机号中间加空格）
- 防止重复提交

## 二、字段布局规范

### 单列布局
适用于字段较少或需要专注填写的场景：
```
┌──────────────────────────────┐
│ 字段标签                     │
│ ┌──────────────────────────┐ │
│ │ 输入框                    │ │
│ └──────────────────────────┘ │
│ 辅助说明文字                  │
└──────────────────────────────┘
```

### 双列布局
适用于字段较多，需要提高效率的场景：
```
┌────────────────┬────────────────┐
│ 字段1          │ 字段2          │
│ ┌────────────┐ │ ┌────────────┐ │
│ │            │ │ │            │ │
│ └────────────┘ │ └────────────┘ │
└────────────────┴────────────────┘
```

### 栅格布局
```
间距：16px（列之间）/ 24px（行之间）
标签宽度：120px
输入框宽度：与标签对齐或略窄
```

## 三、字段类型选择

### 文本输入
```vue
<!-- 单行文本 -->
<el-input v-model="form.name" placeholder="请输入姓名" maxlength="50" />

<!-- 多行文本 -->
<el-input type="textarea" v-model="form.remark" :rows="3" maxlength="200" show-word-limit />
```

### 数字输入
```vue
<!-- 普通数字 -->
<el-input-number v-model="form.count" :min="1" :max="100" />

<!-- 金额（保留2位小数） -->
<el-input-number v-model="form.amount" :precision="2" :min="0" :step="0.01" />
```

### 选择输入
| 场景 | 组件 | 规范 |
|------|------|------|
| 选项 < 7 个 | Radio 单选框 | 水平或垂直排列 |
| 选项 7-15 个 | Select 单选 | 下拉选择 |
| 多选场景 | Checkbox/Select | 多选模式 |
| 级联选择 | Cascader | 最多3级 |

### 日期选择
```vue
<!-- 日期 -->
<el-date-picker type="date" v-model="form.date" format="YYYY-MM-DD" />

<!-- 日期范围 -->
<el-date-picker type="daterange" v-model="form.dateRange" />

<!-- 日期时间 -->
<el-date-picker type="datetime" v-model="form.datetime" />
```

## 四、校验规则设计

### 常用校验规则
```javascript
const rules = {
  // 必填
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  
  // 长度限制
  desc: [
    { required: true, message: '请输入描述', trigger: 'blur' },
    { min: 10, message: '至少10个字符', trigger: 'blur' }
  ],
  
  // 格式校验
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' }
  ],
  
  // 邮箱
  email: [
    { type: 'email', message: '请输入正确的邮箱', trigger: ['blur', 'change'] }
  ],
  
  // 自定义校验
  password: [
    { validator: validatePassword, trigger: 'blur' }
  ]
}
```

### 校验时机
| 时机 | 适用场景 |
|------|----------|
| blur 失焦 | 大多数文本输入 |
| change 变更 | 下拉选择、日期选择 |
| blur+change | 需要严格校验的字段 |

### 校验提示规范
- 错误提示在输入框下方
- 红色文字提示
- 清晰说明错误原因
- 不要只说「格式错误」，要说「请输入11位手机号」

## 五、字段辅助说明

### 占位符提示
```
用途：引导用户输入格式
示例：手机号 - 占位符填写「13800000000」
注意：不要用占位符替代标签
```

### 辅助文字
```
用途：解释复杂字段或特殊要求
位置：输入框下方
示例：「密码至少8位，包含字母和数字」
```

### 气泡提示
```
用途：解释性信息
触发：鼠标悬停
示例：❓ 图标 + 详细说明
```

## 六、提交反馈设计

### 提交按钮
```vue
<el-button type="primary" :loading="submitting" @click="handleSubmit">
  {{ submitting ? '提交中...' : '提交' }}
</el-button>
```

### 成功反馈
```
1. 显示成功 Toast 提示
2. 关闭当前弹窗/跳转列表页
3. 刷新列表数据
示例：「保存成功」
```

### 失败反馈
```
1. 显示错误提示（表单顶部或字段下方）
2. 滚动到第一个错误处
3. 高亮错误字段
4. 不关闭弹窗/留在当前页
```

### 重复提交防护
```javascript
// 使用节流或 loading 状态防止
const submitting = ref(false)

async function handleSubmit() {
  if (submitting.value) return
  submitting.value = true
  try {
    await api.submit(form)
    ElMessage.success('提交成功')
  } finally {
    submitting.value = false
  }
}
```

## 七、表单设计模式

### 模式1：基础信息表单
```
适用：用户资料、简单配置
布局：单列，卡片分组
示例：用户信息编辑
```

### 模式2：分步表单
```
适用：复杂流程（注册、入职）
步骤：进度指示器 + 单步验证
示例：多步骤向导
```

### 模式3：行内编辑
```
适用：表格内快速修改
交互：点击切换编辑/显示
示例：列表页直接修改状态
```

### 模式4：高级筛选
```
适用：列表页筛选
特点：条件折叠展开
示例：多条件组合查询
```

## 八、常见问题处理

### 1. 长文本处理
- 限制最大输入长度
- 显示字数统计
- 超长时滚动而非换行

### 2. 特殊字符
- 敏感字符转义
- emoji 表情处理
- 富文本编辑器安全

### 3. 表单联动
```javascript
// 级联联动
watch(() => form.province, (newVal) => {
  if (newVal) {
    loadCities(newVal)
    form.city = ''
  }
})

// 动态显示隐藏
<el-form-item label="发票类型" v-if="form.hasInvoice" />
```

### 4. 数据回显
```javascript
// 编辑时回显
onMounted(async () => {
  const data = await api.getDetail(id)
  Object.assign(form, data)
})
```
