# Trae 前端 API 与工程化规范
> **前端规则**: 本文件属于 Vue3+TS 规范体系，适用于所有前端开发人员。

## 1. API 调用规范
- 必须通过 `@/utils/request` 调用。
- API 文件结构：
  ```typescript
  // src/api/user.ts
  import request from '@/utils/request';
  import type { UserInfo } from '@/types/user';

  // ✅ 仅定义接口
  export const fetchUserInfo = (id: number) => {
    return request.get<UserInfo>(`/api/users/${id}`);
  };
  ```

## 2. 请求工具 (Request)
- ✅ 自动注入 Authorization Token。
- ✅ 统一 BaseURL (`import.meta.env.VITE_APP_MAIN_URL`)。
- ✅ 统一错误拦截 (401 跳登录, 500 提示报错)。
- ✅ 响应自动解包 (直接返回 `data` 字段)。

## 3. 工程化与环境
- **环境变量**：
  - `.env.development`: 开发环境
  - `.env.production`: 生产环境
  - 引用方式: `import.meta.env.VITE_XXX`
- **路径别名**：`@` 指向 `src/`。
- **Lint**：提交前必须通过 ESLint + Prettier 检查。
