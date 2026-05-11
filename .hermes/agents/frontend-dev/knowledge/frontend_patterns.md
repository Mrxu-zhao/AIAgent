# 前端框架模式库

> 从项目中提炼的前端框架和最佳实践

## 模式1: Vue3 管理端框架（PC Web）

- **分类**: PC端管理后台
- **来源**: xzmetro-ui (最规范) + mall4vp/mall4vs (参考)
- **适用场景**: 企业管理系统、运营后台、数据管理后台
- **技术栈组合**:

```json
{
  "core": "Vue 3.5 + TypeScript 4.9 + Vite 4.3",
  "ui": "Element Plus 2.x",
  "style": "Tailwind CSS 3.x",
  "state": "Pinia 2.x + pinia-plugin-persist",
  "router": "Vue Router 4.x (动态路由)",
  "http": "Axios (多实例)",
  "build": "Vite + ESLint + Prettier"
}
```

### 目录结构规范

```
src/
├── api/           # 接口层，按业务域划分 (如 api/product/, api/order/)
├── assets/        # 静态资源
├── components/    # 公共组件
│   ├── common/    # 通用组件
│   └── business/  # 业务组件
├── composables/   # 组合式函数 (useXxx)
├── directives/    # 自定义指令
├── layout/        # 布局组件
├── router/        # 路由配置
│   └── index.ts   # 动态路由加载
├── stores/        # Pinia 状态管理
├── types/         # TypeScript 类型定义
├── utils/         # 工具函数
└── views/         # 页面，按业务模块组织
```

### Axios 多实例封装

```typescript
// 3个实例分域管理
request.ts     // 基础请求实例（通用）
requestTwo.ts  // 认证相关（登录、刷新Token）
requestThree.ts // 第三方服务

// 通用封装特性:
config.timeout = 10000
请求拦截: Token注入、租户ID、参数SM4加密
响应拦截: code==0成功、424 token过期、426 租户过期
```

### 动态路由模式

```typescript
// 路由由后端返回菜单，前端渲染
// router/index.ts
{
  path: '/xxx',
  component: () => import('@/views/xxx/index.vue'),
  meta: { title: '菜单名称', icon: 'xxx' }
}
```

## 模式2: uni-app 移动端框架

- **分类**: 移动端 (小程序/H5/App)
- **来源**: xzmetro-app (vk-uview-ui) + mall4ms/mall4uni (sard-uniapp)
- **适用场景**: 微信小程序、H5移动端、跨平台App
- **技术栈组合**:

```json
{
  "core": "uni-app + Vue 3",
  "ui": "vk-uview-ui | sard-uniapp",
  "http": "uni.request (封装)",
  "state": "Pinia (PC端用)",
  "routing": "pages.json 静态路由"
}
```

### 目录结构规范 (uni-app)

```
src/
├── api/           # 接口层
├── components/    # uni-app 组件
├── pages/         # 页面 (对应 pages.json)
├── static/        # 静态资源
├── store/         # Pinia 状态 (如用)
├── styles/        # 样式
├── utils/         # 工具函数
└── wxcomponents/  # 微信小程序原生组件
```

### 请求封装

```typescript
// 自封装 HttpRequest 类
class HttpRequest {
  baseURL: string
  timeout: number
  
  request(options) {
    // uni.request 封装
    // Token 注入
    // 统一响应处理
  }
}
```

## 模式3: 多端 API 规范对比

- **分类**: API 设计规范
- **来源**: mall4j + xzmeto 前端对比
- **适用场景**: 多端配套项目

| 规范 | mall4j | xzmeto |
|------|--------|--------|
| 成功码 | `code: 0` 或 `code: 00000` | `code: 0` |
| 错误码 | A00001/A00004/A00005 等 | 自定义业务码 |
| Token | 放 Header | 放 Header |
| 租户ID | 未体现 | 放 Header (426处理) |
| 加密 | 无 | SM4参数加密 |
| 持久化 | 无 | pinia-plugin-persist |

## 待积累

- [ ] React 项目模式
- [ ] Electron 桌面端模式
- [ ] 低代码平台集成模式
