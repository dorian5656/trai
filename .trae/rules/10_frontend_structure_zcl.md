# Trae 前端目录与分层规范
> **前端规则**: 本文件属于 Vue3+TS 规范体系，适用于所有前端开发人员。

## 1. 推荐目录结构
```
src/
├── api/                # 业务接口定义（只调用 request）
├── assets/             # 静态资源 (images, styles)
├── components/         # 组件
│   ├── base/           # 原子组件 (BaseButton, BaseInput) - 业务无关
│   ├── ui/             # 通用 UI 组件 (Modal, Drawer) - 结合 UI 库
│   └── business/       # 业务组件 (UserCard, OrderList) - 业务相关
├── composables/        # 组合式函数 (useUser, useAuth)
├── stores/             # Pinia 状态管理
├── types/              # 全局 TypeScript 类型定义
├── utils/              # 工具库
│   ├── request.ts      # ✅ 核心请求工具
│   ├── auth.ts         # Token 管理
│   └── tools.ts        # 通用工具函数
├── views/              # 页面级组件 (路由视图)
├── router/             # 路由配置
├── App.vue             # 根组件
└── main.ts             # 入口文件
```

## 2. 逻辑分层与职责
| 层级 | 职责 | ✅ 推荐做法 | ❌ 禁止行为 |
| :--- | :--- | :--- | :--- |
| **API 层** | 定义接口 | 仅定义 URL、Method、Params、Return Type | 不处理错误、不写 Axios 配置 |
| **Request** | 网络请求 | 统一拦截器、Token 注入、错误处理 | 不包含跳转路由等具体业务逻辑 |
| **Composables** | 逻辑复用 | 封装状态逻辑、副作用 | 不直接操作 DOM (尽量) |
| **Components** | UI 渲染 | 接收 Props, Emit 事件, 展示数据 | 不直接调用 API (通过 Store 或 Composable) |
| **Views** | 页面组装 | 布局, 路由参数处理, 组合 Components | 不写复杂逻辑 (抽离到 Composable) |
| **Stores** | 全局状态 | 跨组件数据共享 (User, Permissions) | 不直接在 Component 修改 State (用 Actions) |
