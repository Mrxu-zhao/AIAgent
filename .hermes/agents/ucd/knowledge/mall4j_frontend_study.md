# mall4j 四套前端深度分析报告

> 分析时间: 2026-04-29  
> 项目路径:
> - mall4ms: `/workspace/self_workspace/projects/mall4ms-bbc-dev/mall4ms-bbc-dev/` (移动端)
> - mall4vp: `/workspace/self_workspace/projects/mall4vp-bbc-dev/mall4vp-bbc-dev/` (商家后台)
> - mall4vs: `/workspace/self_workspace/projects/mall4vs-bbc-dev/mall4vs-bbc-dev/` (门店系统)
> - mall4uni: `/workspace/self_workspace/projects/mall4uni-bbc-dev/mall4uni-bbc-dev/` (小程序)

---

## 1. 项目概览

| 属性 | mall4ms (移动端) | mall4vp (商家后台) | mall4vs (门店系统) | mall4uni (小程序) |
|------|------------------|-------------------|-------------------|------------------|
| 类型 | 移动端 H5/App | PC Web管理后台 | PC Web门店系统 | 微信小程序/H5 |
| 框架 | uni-app (Vue3) | Vue 3 + Vite | Vue 3 + Vite | uni-app (Vue3) |
| UI框架 | @dcloudio/uni-ui | Element Plus 2.9.3 | Element Plus 2.9.3 | sard-uniapp |
| 状态管理 | Pinia 2.0.36 | Pinia 2.3.0 | Pinia 2.3.0 | Pinia 2.0.36 |
| 路由 | uni-crazy-router | Vue Router 4.5.0 | Vue Router 4.5.0 | uni-app pages.json |

---

## 2. 技术栈横向对比

### 2.1 核心依赖版本对比

| 依赖 | mall4ms | mall4vp | mall4vs | mall4uni |
|------|---------|---------|---------|----------|
| Vue | 3.4.21 | 3.5.13 | 3.5.13 | 3.4.21 |
| 构建工具 | Vite 5.2.8 | Vite 6.0.7 | Vite 6.0.7 | Vite 5.2.8 |
| UI框架 | uni-ui 1.5.5 | Element Plus 2.9.3 | Element Plus 2.9.3 | sard-uniapp |
| 状态管理 | Pinia 2.0.36 | Pinia 2.3.0 | Pinia 2.3.0 | Pinia 2.0.36 |
| 国际化 | vue-i18n 9.1.9 | vue-i18n 11.0.1 | vue-i18n 11.0.1 | vue-i18n 9.1.9 |
| HTTP库 | uni.request | Axios 1.7.9 | Axios 1.7.9 | uni.request |
| 样式预处理 | Sass 1.77.4 | Sass 1.83.4 | Sass 1.83.4 | Sass 1.77.8 |
| 加密 | crypto-js 4.2.0 | crypto-js 4.2.0 | crypto-js 4.2.0 | crypto-js 4.2.0 |

### 2.2 特色依赖对比

**mall4ms / mall4uni (移动端):**
- `uni-crazy-router`: 路由管理
- `wukongimjssdk`: 即时通讯
- `compressorjs`: 图片压缩
- `dayjs`: 日期处理
- `z-paging`: 分页组件
- `qiun-data-charts`: 数据图表

**mall4uni 独有:**
- `flv.js`, `video.js`, `videojs-flvjs-es6`: 视频播放
- `sard-uniapp`: UI组件库
- `unocss`: 原子CSS
- `uni-vite-plugin-h5-prod-effect`: H5优化

**mall4vp / mall4vs (PC端):**
- `echarts 5.6.0`: 数据可视化
- `lodash 4.17.21`: 工具库
- `qs 6.14.0`: 参数序列化
- `moment 2.30.1`: 日期处理
- `vue-cookies 1.8.5`: Cookie管理
- `dompurify 3.2.3`: XSS防护
- `vue-draggable-next`: 拖拽排序

**mall4vs 独有:**
- `pinia-plugin-persistedstate 4.2.0`: 状态持久化
- `qrcode.vue`: 二维码生成
- `html2canvas`: 页面截图
- `element-resize-detector`: 元素监听

### 2.3 开发工具链

| 工具 | mall4ms | mall4vp | mall4vs | mall4uni |
|------|---------|---------|---------|----------|
| ESLint | 8.56.0 | 8.57.0 | 8.57.0 | 8.56.0 |
| Husky | 8.0.3 | 9.1.7 | 9.1.7 | 8.0.3 |
| lint-staged | 15.2.5 | 15.3.0 | 15.3.0 | 15.2.5 |
| 包管理器 | pnpm >=7 | pnpm >=7 | pnpm >=7 | pnpm >=7 |
| Node版本 | >=18.12.0 | >=18.12.0 | >=18.12.0 | >=18.12.0 |

---

## 3. 目录结构对比

### 3.1 mall4vp / mall4vs (PC端) 目录结构

```
src/
├── api/                   # API接口 (注: 使用组件目录下的独立模块)
├── assets/               # 静态资源
├── common/
│   └── enum/             # 枚举定义
├── components/           # 公共组件 (~32个 mall4vp, ~38个 mall4vs)
│   ├── sku/              # SKU相关组件
│   ├── product-details/  # 商品详情
│   ├── video-box/        # 视频组件
│   └── ...
├── directive/            # Vue指令
│   ├── drag/
│   ├── input-rule/
│   └── rich/
├── icons/                # SVG图标
│   └── svg/
├── lang/                 # 国际化语言包
├── layout/               # 布局组件
├── router/               # 路由配置
│   └── index.js
├── stores/               # Pinia状态库
│   ├── common.js         # 通用状态
│   ├── user.js           # 用户状态
│   └── router.js         # 路由状态
├── styles/               # 全局样式
├── utils/                # 工具函数
│   ├── http.js           # Axios封装
│   ├── crypto.js         # 加密工具
│   ├── validate.js       # 表单验证
│   ├── datetime.js       # 日期处理
│   └── ...
└── views/
    ├── common/           # 公共页面
    │   ├── login/
    │   ├── home/
    │   ├── error-page/
    │   └── message-box/
    └── modules/          # 业务模块
        ├── data/         # 数据分析
        ├── finance/      # 财务管理
        ├── fitment/      # 店铺装修
        ├── marketing/    # 营销管理
        ├── member/      # 会员管理
        ├── order/       # 订单管理
        ├── prod/        # 商品管理
        ├── sys/         # 系统设置
        └── (mall4vs独有多: customer, shop, stock, user)
```

### 3.2 mall4uni (小程序) 目录结构

```
src/
├── api/                   # API接口 (分散在各package中)
├── hybrid/                # 原生混合开发
│   └── html/
├── js_sdk/                # JS SDK封装
├── lang/                  # 国际化
├── pages/                 # 主包页面 (~11个)
│   ├── index/             # 首页
│   ├── user/             # 用户中心
│   ├── basket/           # 购物车
│   ├── category/         # 分类
│   └── ...
├── stores/               # Pinia状态库
│   ├── cart-count.js
│   ├── tabbar.js
│   └── theme.js
├── uni_modules/          # uni-app插件
│   ├── uni-icons/
│   ├── z-paging/          # 分页组件
│   ├── qiun-data-charts/ # 图表
│   └── ...
├── utils/                # 工具函数
│   ├── http.js           # 请求封装
│   ├── httpParamVerify.js
│   ├── login.js
│   └── jwx/              # 微信SDK
├── package-shop/         # 商铺模块分包
├── package-user/        # 用户模块分包 (~46个页面)
├── package-prod/        # 商品模块分包
├── package-activities/  # 活动模块分包
├── package-distribution/# 分销模块分包
├── package-member-integral/ # 会员积分分包
└── package-refund/      # 退款模块分包
```

**mall4uni 分包策略:**
- 主包: 首页、用户中心、购物车、分类等核心页面
- package-user: 用户相关 (~46个页面)
- package-prod: 商品相关
- package-activities: 活动 (优惠券、秒杀、直播等)
- package-shop: 商铺相关
- package-distribution: 分销
- package-member-integral: 会员积分

### 3.3 mall4ms 目录结构

与 mall4uni 类似，采用 uni-app 架构：
- `package-order/`: 订单模块
- `package-settings/`: 设置模块
- `uni_modules/`: 公共组件
- `stores/`: 状态管理

---

## 4. API对接模式对比

### 4.1 mall4vp / mall4vs - Axios封装模式

```javascript
// src/utils/http.js
import axios from 'axios'
import qs from 'qs'
import cookie from 'vue-cookies'

const http = axios.create({
  timeout: 1000 * 30,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json; charset=utf-8'
  }
})

// 请求拦截
http.interceptors.request.use(config => {
  config.headers.Authorization = cookie.get('bbcAuthorization_vp') // mall4vp
  // 或 cookie.get('bbcAuthorization_vs') // mall4vs
  config.headers.timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
  config.headers.locale = localStorage.getItem('bbcLang') || 'zh_CN'
  
  // GET参数序列化
  if (config.method === 'get') {
    config.paramsSerializer = {
      serialize: params => qs.stringify(params, { arrayFormat: 'repeat' })
    }
  }
  return config
})

// 响应拦截
http.interceptors.response.use(response => {
  // Blob格式处理
  if (response.request.responseType === 'blob') return response
  
  const res = response.data
  if (res.code === '00000' || res.code === 'A00002') {
    return res
  }
  // A00001 业务错误
  if (res.code === 'A00001') { /* 错误提示 */ }
  // A00004 未授权
  if (res.code === 'A00004') { clearLoginInfo() }
  // A00005 服务器异常
  if (res.code === 'A00005') { /* 异常处理 */ }
  return Promise.reject(res)
})

// 辅助方法
http.adornUrl = actionName => import.meta.env.VITE_APP_BASE_API + actionName
http.adornParams = (params = {}, openDefultParams = true) => {
  const defaults = { t: Date.now() }
  return openDefultParams ? merge(defaults, params) : params
}
http.adornData = (data = {}, openDefultdata = true, contentType = 'json') => {
  const defaults = { t: Date.now() }
  data = openDefultdata ? merge(defaults, data) : data
  return contentType === 'json' ? JSON.stringify(data) : qs.stringify(data)
}
```

**API调用示例:**
```javascript
// src/stores/xxx.js
import http from '@/utils/http'

export function getProdList(data) {
  return http({
    url: http.adornUrl('/prod/page'),
    method: 'POST',
    data: http.adornData(data)
  })
}
```

### 4.2 mall4uni / mall4ms - uni.request封装模式

```javascript
// src/utils/http.js
const http = {
  request: (params) => {
    return new Promise((resolve, reject) => {
      uni.request({
        dataType: 'json',
        responseType: params.responseType == undefined ? 'text' : params.responseType,
        header: {
          Authorization: uni.getStorageSync('bbcToken'),
          locale: uni.getStorageSync('bbcLang') || 'zh_CN',
          timeZone: timezone.name()
        },
        url: (params.domain ? params.domain : import.meta.env.VITE_APP_BASE_API) + params.url,
        data: params.data,
        method: params.method == undefined ? 'POST' : params.method,
        success: (res) => {
          const responseData = res.data
          if (responseData.code === '00000' || responseData.code === 'A00002') {
            resolve(responseData)
          }
          if (responseData.code === 'A00004') {
            // 未授权处理
            uni.navigateTo({ url: '/package-user/pages/user-login/user-login' })
          }
          if (responseData.code === 'A00005') {
            // 服务器异常
          }
          reject(responseData)
        }
      })
    })
  },
  
  upload: (params) => {
    uni.uploadFile({
      url: import.meta.env.VITE_APP_BASE_API + params.url,
      filePath: params.filePath,
      name: params.name || 'file',
      header: {
        Authorization: params.login ? undefined : uni.getStorageSync('bbcToken')
      }
    })
  }
}
```

### 4.3 统一业务码规范

| 响应码 | 含义 | mall4处理 |
|--------|------|----------|
| 00000 | 成功 | 直接返回数据 |
| A00001 | 业务错误 | 显示错误消息 |
| A00002 | 系统成功 | 返回数据 |
| A00004 | 未授权 | 跳转登录页 |
| A00005 | 服务器异常 | 显示"服务器小差" |

---

## 5. 路由与鉴权对比

### 5.1 mall4vp / mall4vs - 动态路由模式

```javascript
// src/router/index.js
const router = createRouter({
  history: createWebHistory(),
  routes: globalRoutes.concat(mainRoutes),
  isAddDynamicMenuRoutes: false
})

router.beforeEach((to, from, next) => {
  if (router.options.isAddDynamicMenuRoutes || fnCurrentRouteType(to, globalRoutes) === 'global') {
    next()
  } else {
    if (!cookie.get('bbcAuthorization_vp')) {  // 或 bbcAuthorization_vs
      router.push({ name: 'login' })
      return
    }
    // 从后端获取菜单权限
    http({
      url: http.adornUrl('/sys/menu/nav'),  // mall4vp
      // 或 http.adornUrl('/sys/shopMenu/nav')  // mall4vs
      method: 'get'
    }).then(({ data }) => {
      fnAddDynamicMenuRoutes(data.menuList)
      router.options.isAddDynamicMenuRoutes = true
      next({ ...to, replace: true })
    })
  }
})

// 动态添加路由
function fnAddDynamicMenuRoutes(menuList = [], routes = []) {
  const modules = import.meta.glob('../views/modules/**/**.vue')
  menuList.forEach(item => {
    if (item.url) {
      routes.push({
        path: item.url,
        component: modules[`../views/modules/${item.url}.vue`],
        meta: { menuId: item.menuId, title: item.name }
      })
    }
  })
  router.addRoute(mainRoutes)
}
```

### 5.2 mall4uni - 静态分包路由

```json
// pages.json
{
  "pages": [
    { "path": "pages/index/index" },
    { "path": "pages/user/user" },
    { "path": "pages/basket/basket" }
  ],
  "subPackages": [
    {
      "root": "package-user",
      "pages": [
        { "path": "pages/user-login/user-login" },
        { "path": "pages/order-list/order-list" }
      ]
    }
  ],
  "tabBar": {
    "list": [
      { "pagePath": "pages/index/index" },
      { "pagePath": "pages/category/category" },
      { "pagePath": "pages/basket/basket" },
      { "pagePath": "pages/user/user" }
    ]
  }
}
```

**鉴权处理:**
- Token存储: `uni.setStorageSync('bbcToken')`
- 路由拦截: 在请求封装中检查 token
- 登录跳转: 未授权时跳转 `/package-user/pages/user-login/user-login`

### 5.3 路由模式对比

| 特性 | mall4vp/vs | mall4uni/ms |
|------|-----------|-------------|
| 路由类型 | 动态路由 (后端控制) | 静态路由 (pages.json) |
| 路由来源 | 后端返回菜单 | 前端预定义 |
| 权限控制 | 后端菜单权限 | 前端白名单 |
| Token存储 | vue-cookies | uni.setStorageSync |
| 守卫方式 | Vue Router Guard | 请求拦截器 |

---

## 6. 状态管理对比

### 6.1 mall4vp / mall4vs - Pinia Store

```javascript
// stores/common.js
export const useCommonStore = defineStore('common', {
  state: () => ({
    documentClientHeight: 0,
    sidebarFold: true,
    menuList: [],
    mainTabs: [],
    routeList: [],
    selectLeftId: '',
    selectRightId: ''
  }),
  actions: {
    updateSidebarFold(fold) { this.sidebarFold = fold },
    updateRouteList(list) { this.routeList = list }
  }
})

// stores/user.js
export const useUserStore = defineStore('user', {
  state: () => ({
    id: 0,
    name: '',
    userId: '',
    shopId: '',
    mobile: '',
    channelId: ''
  }),
  actions: {
    updateMobile(mobile) { this.mobile = mobile }
  }
})
```

### 6.2 mall4uni - 轻量级Store

```javascript
// stores/cart-count.js
export const useCartCountStore = defineStore('cartCount', {
  state: () => ({
    cartCount: 0
  }),
  actions: {
    updateCartCount() { /* 获取购物车数量 */ }
  }
})

// stores/theme.js
export const useThemeStore = defineStore('theme', {
  state: () => ({
    isDark: false
  })
})
```

### 6.3 状态管理对比

| 特性 | mall4vp/vs | mall4uni/ms |
|------|-----------|-------------|
| Store数量 | 3个 (common, user, router) | 4个 (cart-count, tabbar, theme, web-config) |
| 持久化 | 无 (刷新重置) | 可选持久化 |
| 模块化 | 完整 | 轻量简化 |
| Tab页缓存 | 支持 | 不需要 |

---

## 7. 业务模块对比

### 7.1 mall4vp (商家后台) 模块

```
views/modules/
├── data/          # 数据分析
│   ├── analysis/  # 数据分析
│   └── report/    # 报表
├── finance/       # 财务管理
│   ├── billing-details/
│   ├── fina-details/
│   ├── reconciliation-details/
│   ├── shop-withdraw-cash/
│   └── wallet-log/
├── fitment/       # 店铺装修
├── marketing/     # 营销管理
│   ├── discount/
│   ├── distribution-*/
│   └── group-activity/
├── member/       # 会员管理
├── order/        # 订单管理
├── platform/     # 平台管理
├── prod/         # 商品管理
│   ├── category/
│   ├── brand/
│   └── spec/
└── sys/          # 系统设置
```

### 7.2 mall4vs (门店系统) 模块

```
views/modules/
├── customer/     # 客户管理 (独有)
├── data/        # 数据分析
├── finance/     # 财务管理
├── fitment/     # 店铺装修
├── marketing/   # 营销管理
├── order/       # 订单管理
├── prod/        # 商品管理
├── shop/        # 店铺管理 (独有)
├── shop-process/# 开店流程 (独有)
├── stock/       # 库存管理 (独有)
├── sys/         # 系统设置
└── user/        # 用户管理 (独有)
```

### 7.3 mall4uni (小程序) 分包

```
主包:
├── pages/index/       # 首页
├── pages/user/        # 用户中心
├── pages/basket/      # 购物车
└── pages/category/   # 分类

package-user:          # 用户相关 (~46个页面)
├── user-login/
├── order-list/
├── order-detail/
├── personal-information/
├── my-wallet/
├── recharge-balance/
└── ...

package-prod:         # 商品相关
├── prod/
├── search-prod-show/
└── submit-order/

package-activities:   # 活动
├── coupon-center/
├── my-coupon/
├── snap-up-list/
├── spell-group-details/
├── live-room/
└── wx-player/

package-shop:         # 商铺
├── shop-page/
├── shop-prods/
└── station-search/
```

### 7.4 业务模块差异

| 业务模块 | mall4vp | mall4vs | mall4uni |
|----------|---------|---------|----------|
| 数据分析 | data/ | data/ | 图表组件 |
| 财务管理 | finance/ | finance/ | 我的钱包 |
| 营销管理 | marketing/ | marketing/ | 活动 |
| 会员管理 | member/ | customer/ | 会员积分 |
| 订单管理 | order/ | order/ | 订单列表 |
| 商品管理 | prod/ | prod/ | 商品详情 |
| 店铺装修 | fitment/ | fitment/ | - |
| 系统设置 | sys/ | sys/ | 账号设置 |
| 库存管理 | - | stock/ | - |
| 店铺管理 | - | shop/ | 门店页面 |
| 客户管理 | - | customer/ | - |
| 用户管理 | - | user/ | 用户中心 |
| 开店流程 | - | shop-process/ | - |

---

## 8. 与 xzmeto 前端框架对比

### 8.1 技术栈对比

| 特性 | mall4j前端 | xzmeto前端 |
|------|-----------|-----------|
| **核心框架** | Vue 3 (3.4-3.5) | Vue 3 (3.5) |
| **构建工具** | Vite 5-6 | Vite 4 |
| **UI框架** | Element Plus / uni-ui | Element Plus + Tailwind CSS |
| **状态管理** | Pinia | Pinia + pinia-plugin-persist |
| **国际化** | vue-i18n | vue-i18n |
| **HTTP库** | Axios / uni.request | Axios |
| **样式** | SCSS | SCSS + PostCSS |

### 8.2 依赖管理对比

| 依赖 | mall4j | xzmeto |
|------|--------|--------|
| Vue | 3.4-3.5 | 3.5.13 |
| Vite | 5-6 | 4.3.3 |
| Element Plus | 2.9.3 | 2.11.5 |
| Pinia | 2.0-2.3 | 2.0.32 |
| vue-i18n | 9-11 | 9.2.2 |
| Axios | 1.7.9 | 1.3.3 |
| ECharts | 5.6 | 5.4.1 |
| Tailwind CSS | - | 3.4.17 |

### 8.3 目录结构对比

**xzmeto (xzmetro-ui):**
```
src/
├── api/           # 按模块划分
├── assets/
├── components/    # 47个公共组件
├── directive/
├── hooks/
├── i18n/
├── layout/
├── mock/
├── router/        # 多路由配置
├── stores/       # 9个Store模块
├── styles/
├── theme/
├── types/
├── utils/         # 多请求实例
└── views/        # 按业务模块
```

**mall4j (PC端):**
```
src/
├── components/   # 组件直接放一起
├── directive/
├── icons/
├── lang/
├── layout/
├── router/
├── stores/        # 3个Store模块
├── styles/
├── utils/         # 单请求封装
└── views/
    ├── common/
    └── modules/  # 按业务大模块
```

**mall4j (小程序):**
```
src/
├── pages/         # 主包页面
├── stores/        # 轻量Store
├── uni_modules/   # 插件
├── utils/
└── package-*/    # 分包模式
```

### 8.4 API对接模式对比

**xzmeto - 多实例Axios:**
```javascript
// 三个Axios实例
request.ts    -> VITE_API_URL
requestTwo.ts -> VITE_API_URL_TWO
requestThree.ts
```

**mall4j - 单实例Axios:**
```javascript
// 单Axios实例
http.js -> VITE_APP_BASE_API
```

### 8.5 路由模式对比

| 模式 | mall4j | xzmeto |
|------|--------|--------|
| PC端路由 | 动态路由 (后端控制) | 动态路由 (后端控制) |
| 移动端路由 | 静态路由 (pages.json) | 静态路由 |
| 路由守卫 | Vue Router Guard | Vue Router Guard |
| 权限获取 | 登录后请求菜单 | 登录后请求菜单 |

### 8.6 安全特性对比

| 特性 | mall4j | xzmeto |
|------|--------|--------|
| 国密SM4 | crypto-js | sm-crypto + crypto-js |
| XSS防护 | dompurify | - |
| 参数加密 | - | GET参数加密 |
| 响应解密 | - | 支持 |

### 8.7 代码组织对比

| 特性 | mall4j | xzmeto |
|------|--------|--------|
| API组织 | 分散在store中 | 统一api/目录 |
| TypeScript | 部分使用 | 完整TypeScript |
| Mock数据 | - | 有mock/目录 |
| Hooks | - | 有hooks/目录 |
| 枚举定义 | common/enum/ | 有enums/目录 |

---

## 9. 总结与建议

### 9.1 mall4j前端特点

**优势:**
1. 完善的四端解决方案 (管理后台、商家后台、门店系统、小程序)
2. 统一的技术栈 (Vue 3 + Pinia)
3. 移动端采用uni-app实现跨平台
4. PC端采用Element Plus，生态成熟
5. 请求封装统一，业务码规范一致

**不足:**
1. 小程序未使用TypeScript
2. API未集中管理，分散在各模块
3. 缺少完整的类型定义
4. 未使用Tailwind CSS等现代CSS方案
5. 安全功能 (国密) 未完整实现

### 9.2 与xzmeto对比总结

| 对比维度 | mall4j | xzmeto | 建议 |
|----------|--------|--------|------|
| 技术栈 | Vue3+Vite | Vue3+Vite+TS | 两者相近 |
| UI框架 | Element Plus | Element Plus+Tailwind | xzmeto更灵活 |
| 代码规范 | ESLint | ESLint | 一致 |
| API管理 | 分散 | 集中 | xzmeto更规范 |
| 类型安全 | 部分TS | 完整TS | xzmeto更优 |
| 状态持久化 | 无 | 有pinia-plugin-persist | xzmeto更好 |
| 多实例请求 | 无 | 有 | xzmeto更灵活 |

### 9.3 架构优化建议

1. **统一API层**: 将分散的API调用集中到api/目录
2. **增加TypeScript**: 对mall4uni增加完整类型定义
3. **状态持久化**: 对关键状态增加持久化支持
4. **安全增强**: 增加XSS防护和国密加密
5. **代码复用**: 四套前端抽取公共组件
6. **统一配置**: 统一各端的环境变量和API地址管理
