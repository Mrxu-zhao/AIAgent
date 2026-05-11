# xzmeto_resource 前台+程序端 深度分析报告

> 分析时间: 2026-04-29  
> 项目路径:
> - 前台: `/workspace/self_workspace/projects/xzmeto_resource_front-main/xzmeto_resource_front-main/`
> - 程序端: `/workspace/self_workspace/projects/xzmeto_resource_program-main/xzmeto_resource_program-main/`

---

## 1. 项目概览

| 属性 | 前台 (管理端) | 程序端 (小程序/H5) |
|------|--------------|-------------------|
| 项目名 | xzmetro-ui (pig4cloud) | pigx-app |
| 版本 | 5.9.0 | 5.5.0 |
| 类型 | PC Web管理后台 | 移动端 (uni-app) |
| 许可 | pig4cloud 商业版权 | 未声明 |

---

## 2. 技术栈对比

### 2.1 前台 (xzmetro-ui)

```
核心框架:    Vue 3.5.13 + TypeScript 4.9.5
构建工具:    Vite 4.3.3
UI框架:     Element Plus 2.11.5 + Tailwind CSS 3.4.17
状态管理:    Pinia 2.0.32 + pinia-plugin-persist
路由:       Vue Router 4.1.6
HTTP库:     Axios 1.3.3
国际化:     vue-i18n 9.2.2
样式:       SCSS + PostCSS + Autoprefixer
```

**特色依赖**:
- 加密: crypto-js, sm-crypto (国密SM2/SM4)
- 图表: echarts 5.4.1, vue-echarts 7.0.3
- 编辑器: @wangeditor-next (富文本), json-editor-vue3, codemirror
- 表单: @form-create/element-ui 3.2.16
- 视频: vue3-video-play 1.3.1-beta.6
- PDF/Excel: xlsx, markmap (思维导图)

### 2.2 程序端 (pigx-app)

```
核心框架:    Vue 3.2.47 + TypeScript 4.7.4
跨端框架:    uni-app (DCloud)
状态管理:    Pinia 2.0.36
路由:       uni-app pages (静态路由)
HTTP库:     uni.request (原生) + 自封装
国际化:     vue-i18n 9.2.2
样式:       SCSS + Tailwind CSS 3.1.8 + PostCSS
UI组件库:   vk-uview-ui (uni-app生态)
微信SDK:    weixin-js-sdk 1.6.0
```

---

## 3. 目录结构对比

### 3.1 前台目录结构

```
xzmetro-ui/src/
├── api/                    # API接口层
│   ├── app/               # APP相关接口
│   ├── basicData/         # 基础数据接口
│   ├── contract/          # 合同管理接口
│   ├── daemon/            # 定时任务接口
│   ├── file/              # 文件上传接口
│   ├── gen/               # 代码生成接口
│   ├── mp/                # 微信公众号接口
│   └── pay/               # 支付相关接口
├── assets/                # 静态资源
├── components/            # 公共组件 (47个)
├── directive/             # Vue指令
├── hooks/                 # 组合式函数
├── i18n/                  # 国际化配置
├── layout/                # 布局组件
├── mock/                  # Mock数据
├── router/                # 路由配置
│   ├── index.ts          # 路由主入口
│   ├── route.ts          # 静态路由定义
│   ├── backEnd.ts        # 后端控制路由
│   └── frontEnd.ts       # 前端控制路由
├── stores/                # Pinia状态库
│   ├── index.ts          # Store主入口
│   ├── userInfo.ts       # 用户信息
│   ├── routesList.ts     # 路由列表
│   ├── tagsViewRoutes.ts # 标签页路由
│   ├── keepAliveNames.ts # 缓存组件
│   ├── themeConfig.ts    # 主题配置
│   ├── dict.ts           # 字典数据
│   └── line.ts           # 线路数据
├── styles/               # 全局样式
├── theme/                # Element Plus主题
├── types/                # TypeScript类型定义
├── utils/                # 工具函数
│   ├── request.ts        # Axios实例1 (VITE_API_URL)
│   ├── requestTwo.ts      # Axios实例2 (VITE_API_URL_TWO)
│   ├── requestThree.ts   # Axios实例3
│   ├── apiCrypto.ts      # API加密/解密
│   ├── storage.ts        # LocalStorage/SessionStorage封装
│   └── other.ts          # URL适配工具
└── views/                # 页面组件
    ├── basic-data/       # 基础数据管理
    ├── contract-management/ # 合同管理
    ├── gen/              # 代码生成器
    ├── leadership/       # 领导驾驶舱
    ├── process-config/   # 流程配置
    └── resource-management/ # 资源管理
```

### 3.2 程序端目录结构

```
pigx-app/src/
├── api/                   # API接口层
│   ├── api.ts            # 主接口文件
│   └── shop.ts           # 商铺相关接口
├── components/           # 公共组件
├── enums/                # 枚举定义
│   └── requestEnums.ts   # 请求状态码枚举
├── hooks/                # 组合式函数
├── pages/                # 页面文件 (uni-app)
│   ├── index/            # 首页
│   ├── login/            # 登录
│   ├── resource/         # 资源
│   └── user/             # 用户中心
├── pages.json            # 页面路由配置
├── plugins/              # 插件
├── router/               # 路由配置
│   ├── index.ts          # 路由拦截器
│   └── routes.ts         # 路由定义
├── static/               # 静态资源
├── stores/               # Pinia状态库
│   ├── app.ts           # 应用状态
│   ├── user.ts          # 用户状态
│   ├── resource.ts      # 资源状态
│   └── approval.ts      # 审批状态
├── styles/               # 全局样式
├── uni.scss              # uni-app全局变量
├── uni_modules/          # uni-app插件
│   └── vk-uview-ui/     # UI组件库
└── utils/                # 工具函数
    ├── request/         # 请求封装
    │   ├── index.ts     # 请求入口
    │   ├── http.ts      # HttpRequest类
    │   ├── cancel.ts    # 请求取消
    │   └── type.d.ts    # 类型定义
    ├── requestTwo.ts    # 备用请求
    ├── auth.ts          # 认证工具
    ├── cache.ts         # 缓存工具
    ├── client.ts        # 客户端判断
    └── wechat.ts        # 微信SDK
```

---

## 4. API对接模式

### 4.1 前台 - 多实例Axios模式

#### 4.1.1 Request实例配置

```typescript
// src/utils/request.ts - 业务API实例
const service = axios.create({
    baseURL: import.meta.env.VITE_API_URL,
    timeout: 50000,
    paramsSerializer: {
        serialize: (params) => qs.stringify(params, { arrayFormat: 'repeat' })
    }
});

// src/utils/requestTwo.ts - 资源API实例
const service2 = axios.create({
    baseURL: import.meta.env.VITE_API_URL_TWO,
    timeout: 50000,
    maxContentLength: 100 * 1024 * 1024  // 100MB大文件
});
```

#### 4.1.2 请求拦截器

```typescript
// 统一处理
service.interceptors.request.use((config) => {
    // 1. 添加Token
    const token = Session.getToken();
    if (token && !config.headers?.skipToken) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    
    // 2. 添加租户ID
    const tenantId = Session.getTenant();
    if (tenantId) {
        config.headers['TENANT-ID'] = tenantId;
    }
    
    // 3. 请求加密 (国密SM4)
    if (config.data && !config.headers['Enc-Flag']) {
        config.data = wrapEncryption(config.data);
    }
    
    // 4. GET参数加密
    if (config.method === 'get' && config.params) {
        config.params = encryptRequestParams(config.params);
    }
    
    return config;
});
```

#### 4.1.3 响应拦截器

```typescript
// 业务码处理
const handleResponse = (response) => {
    if (response.data.code === 1) {
        throw response.data;  // code=1表示业务错误
    }
    
    // 密文解密
    if (response.data.encryption) {
        return decrypt(response.data.encryption);
    }
    
    return response.data;
};

// HTTP状态码特殊处理
service.interceptors.response.use(handleResponse, (error) => {
    if (status === 424) {
        // Token过期，跳转登录
    }
    if (status === 426) {
        // 租户过期
    }
    return Promise.reject(error.response.data);
});
```

#### 4.1.4 API调用示例

```typescript
// src/api/contract/index.ts
import request from '/@/utils/requestTwo';

export function getContractList(data?: any) {
    return request({
        url: `/api/contract/both/page`,
        method: 'post',
        data,
    });
}

export function getContractDetail(id?: any) {
    return request({
        url: `/api/contract/both/queryDetail`,
        method: 'get',
        params: { id },
    });
}
```

### 4.2 程序端 - uni.request封装模式

#### 4.2.1 请求工具类

```typescript
// src/utils/request/http.ts - HttpRequest类
export default class HttpRequest {
    constructor(options: HttpRequestOptions) {
        this.options = options;
    }
    
    get<T>(options: RequestOptions, config?: RequestConfig): Promise<T> {
        return this.request({ ...options, method: 'GET' }, config);
    }
    
    post<T>(options: RequestOptions, config?: RequestConfig): Promise<T> {
        return this.request({ ...options, method: 'POST' }, config);
    }
    
    uploadFile(options: UploadFileOption): Promise<any> {
        return new Promise((resolve, reject) => {
            uni.uploadFile({
                ...options,
                success: (response) => {
                    // 处理上传响应
                }
            });
        });
    }
}
```

#### 4.2.2 请求Hooks配置

```typescript
// src/utils/request/index.ts
const requestHooks: RequestHooks = {
    requestInterceptorsHook(options, config) {
        // URL适配
        options.url = `${adaptationUrl(options.url)}`;
        
        // 添加Token
        const token = getToken();
        if (withToken && token) {
            options.header.Authorization = `Bearer ${token}`;
        }
        
        // 添加租户ID
        if (cache.getTenant()) {
            options.header['TENANT-ID'] = cache.getTenant();
        }
        
        return options;
    },
    
    responseInterceptorsHook(response) {
        switch (statusCode) {
            case RequestCodeEnum.SUCCESS:
                return response.data;
            case RequestCodeEnum.REQUEST_424_ERROR:
                uni.navigateTo({ url: '/pages/login/login' });
                return Promise.reject();
        }
    }
};
```

#### 4.2.3 简单封装模式

```typescript
// src/utils/requestTwo.ts - 简化封装
const request = (url: string, method: any = 'GET', data: any = {}) => {
    const fullUrl = baseConfig.baseUrl + url;
    
    return new Promise((resolve, reject) => {
        uni.request({
            url: fullUrl,
            method,
            data,
            header: {
                authorization: `Bearer ${token}`
            },
            success: (res) => {
                if (res.data.success || res.data.ok) {
                    resolve(res.data.data || res);
                } else {
                    reject(res);
                }
            },
            fail: (err) => reject(err)
        });
    });
};

export default request;
```

#### 4.2.4 API调用示例

```typescript
// src/api/api.ts
import request from '@/utils/requestTwo';

export const login = (data: any) => request('/miniapp/login', 'POST', data);
export const register = (data: any) => request('/miniapp/register', 'POST', data);
export const getLoginUserInfo = (data: any) => request('/appuser/infoByOpenid', 'GET', data);
export const getFavoriteResourceList = (data: any) => 
    request(`/userfavorites/page/resource`, 'GET', data);
export const addFavorite = (data: any) => request(`/userfavorites`, 'POST', data);
export const createApply = (data: any) => request(`/apply/create`, 'POST', data);
export const myResourceList = (data: any) => 
    request(`/resource/room/owner/details?current=${data.current}&size=${data.size}`, 'POST', data);

// src/api/shop.ts
import request from '@/utils/requestTwo';

export function getHotShopList(data: any) {
    let url = '/resource/room/hot/details';
    if (data?.current && data?.size) {
        url += `?current=${data.current}&size=${data.size}`;
    }
    return request(url, 'POST', data);
}

export function getShopList(data: any) {
    let url = '/resource/room/details/page';
    if (data?.current && data?.size) {
        url += `?current=${data.current}&size=${data.size}`;
    }
    return request(url, 'POST', data);
}
```

---

## 5. 鉴权机制

### 5.1 前台鉴权

```typescript
// src/router/index.ts - 路由守卫
router.beforeEach(async (to, from, next) => {
    const token = Session.getToken();
    
    if (to.meta.isAuth === false) {
        next();  // 不需要认证的路由
    } else {
        if (!token) {
            next(`/login?redirect=${to.path}`);
        } else if (token && to.path === '/login') {
            next('/home');
        } else {
            // 后端控制路由：从后端获取路由权限
            await initBackEndControlRoutes();
            next();
        }
    }
});
```

**存储方式**:
- Token: SessionStorage
- 租户ID: LocalStorage
- 用户信息: Pinia持久化

### 5.2 程序端鉴权

```typescript
// src/router/index.ts - 路由拦截器
const whiteList = ['register', 'login', 'forget_pwd'];
uni.addInterceptor('navigateTo', {
    invoke(e) {
        const url = e.url.split('?')[0];
        const currentRoute = routes.find(item => url === item.path);
        
        // 需要登录且没有token
        if (currentRoute?.auth && !getToken()) {
            uni.navigateTo({ url: '/pages/login/login' });
            return false;
        }
        return e;
    }
});
```

**存储方式**:
- Token: uni.setStorageSync('token')
- 缓存: 自定义cache工具类

---

## 6. 路由模式对比

| 特性 | 前台 | 程序端 |
|------|------|--------|
| 路由类型 | 动态路由 (后端控制) | 静态路由 (pages.json) |
| 路由数量 | 无限 | 需预定义 |
| 权限控制 | 后端返回菜单 | 前端白名单 |
| 守卫方式 | Vue Router Guard | uni.addInterceptor |

---

## 7. 状态管理对比

### 前台 (Pinia + 插件持久化)

```typescript
// stores/userInfo.ts
export const useUserInfo = defineStore('userInfo', {
    state: () => ({
        userInfo: {},
        permissions: [],
        roles: []
    }),
    actions: {
        setUserInfo(info) {
            this.userInfo = info;
        }
    }
});
```

### 程序端 (Pinia)

```typescript
// stores/user.ts
export const useUserStore = defineStore('userStore', {
    state: (): UserSate => ({
        userInfo: {},
        token: cache.get(TOKEN_KEY) || null,
        temToken: null
    }),
    getters: {
        isLogin: (state) => !!state.token
    },
    actions: {
        login(token: string) {
            this.token = token;
            cache.set(TOKEN_KEY, token);
        },
        logout() {
            this.token = '';
            this.userInfo = {};
            cache.remove(TOKEN_KEY);
        }
    }
});
```

---

## 8. 核心业务模块

### 前台业务模块
```
├── 合同管理 (contract-management)
│   ├── 合同台账 (contractLedger)
│   ├── 支付记录 (paymentRecord)
│   ├── 计量记录 (measurementRecord)
│   ├── 审批记录 (approvalRecord)
│   └── 移交认领 (handoverClaim)
├── 资源管理 (resource-management)
│   ├── 资源列表 (resourceList)
│   ├── 租赁管理 (leaseManagement)
│   ├── 招商管理 (Investment)
│   └── 销售管理 (salesManagement)
├── 基础数据 (basic-data)
└── 代码生成 (gen)
```

### 程序端业务模块
```
├── 首页 (index)
├── 登录 (login)
├── 资源浏览 (resource)
│   ├── 商铺详情
│   ├── 站点线路
│   └── 收藏
├── 我的 (user)
│   ├── 我的资源
│   ├── 申请记录
│   └── 消息通知
└── 装修申请 (decoration)
```

---

## 9. 总结

### 技术选型差异

| 维度 | 前台 | 程序端 |
|------|------|--------|
| 平台 | PC浏览器 | 移动端(微信/支付宝/H5/App) |
| 框架 | Vue3 + Vite | uni-app + Vue3 |
| UI | Element Plus | vk-uview-ui |
| HTTP | Axios | uni.request |
| 安全 | 国密SM4加密 | 基础Token认证 |
| 路由 | 动态路由 | 静态路由 |
| 状态 | Pinia持久化 | Pinia |

### API模式特点

1. **前台**: 采用多Axios实例区分业务域，支持请求加密、参数加密、租户隔离
2. **程序端**: 封装uni.request，支持H5/小程序/App多端适配，路由拦截器实现权限控制

### 建议改进

1. 程序端可考虑升级为uni.request的类Axios封装，与前台保持一致
2. 鉴权Token建议添加刷新机制
3. 可抽取公共API调用规范到独立模块
