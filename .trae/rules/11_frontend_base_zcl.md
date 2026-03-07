# Trae 前端基础与语言规范
> **前端规则**: 本文件属于 Vue3+TS 规范体系，适用于所有前端开发人员。

## 1. 核心原则
- **三层解耦**：API 层只描述“要什么”，Request 工具负责“怎么拿”，组件只关心“怎么展示”。
- **中文优先**：为了团队协作顺畅，强制使用中文注释和日志。

## 2. 语言与注释 (强制)
- **注释**：解释“为什么”这样做，而不是“做了什么”。必须使用**中文**。
  ```typescript
  // ✅ 获取用户信息，用于权限校验
  const getUserInfo = () => { ... }
  ```
- **日志**：调试打印必须使用**中文**，方便排查。
  ```typescript
  console.log('✅ 用户登录成功:', userInfo);
  console.error('❌ 获取订单列表失败:', error);
  ```
- **系统日志**：如果有上报系统，内容描述也必须是中文。

## 3. TypeScript 规范
- **Strict Mode**：启用 `strict: true`。
- **No Any**：❌ 严禁使用 `any` 或 `@ts-ignore` (特殊情况需通过 Code Review)。
- **Interface**：所有 Props、Emits、API 响应必须定义接口 (Interface)。
- **位置**：类型定义统一放置在 `src/types/` 或组件同级 `types.ts` (若仅组件私有)。

## 4. 文件头规范 (强制)
所有源代码文件（.vue, .ts, .js, .css, .html）顶部必须包含标准注释头。
- **格式**:
  - `文件名`: 相对项目根目录的路径 (如 `frontend/src/views/Home.vue`)
  - `作者`: zcl (或实际作者)
  - `日期`: YYYY-MM-DD
  - `描述`: 文件功能的中文简述

- **示例 (Vue/HTML)**:
  ```html
  <!--
  文件名：frontend/src/views/Home.vue
  作者：zcl
  日期：2026-01-27
  描述：PC端主页组件
  -->
  <script setup lang="ts">
  ```

- **示例 (TS/JS)**:
  ```typescript
  // 文件名：frontend/src/utils/request.ts
  // 作者：zcl
  // 日期：2026-01-27
  // 描述：Axios 网络请求封装
  ```

- **示例 (CSS)**:
  ```css
  /*
  文件名：frontend/src/style.css
  作者：zcl
  日期：2026-01-27
  描述：全局样式文件
  */
  ```

## 5. 样式与单位规范 (强制)
- **响应式单位**：所有布局尺寸、间距、字体大小必须使用相对单位 (`vw`, `vh`, `rem`, `%`)，严禁使用固定 `px` (1px 边框除外)。
  - **推荐**: 
    - 布局容器宽度/高度使用 `vw`/`vh`。
    - 字体大小使用 `rem` (根元素可配合 vw 调整) 或直接 `vw` (需注意最小可读性)。
    - 间距使用 `vh` (垂直) 或 `vw` (水平)。
    - **转换参考**: 默认情况下 1rem = 16px。
- **布局**: 优先使用 Flexbox 和 Grid。

## 6. 日志与提交流程 (强制)
- **前端日志位置**：统一写入 `frontend/CHANGELOG.md`，与后端日志分离。
- **时间戳格式**：三级标题 `### YYYY_MM_DD_HHMM`，按时间倒序排列（最新在最上）。
- **描述规范**：统一使用中文，分类标注为 `前端-内容`，用**英文标点**。
- **提交流程**：
  1. 先更新 `frontend/CHANGELOG.md` 日志。
  2. 使用中文提交信息：示例 `修补(frontend): 调整技能为发票识别`。
  3. 推送到个人/功能分支（如 `zcl` 或 `feature/*`），再由负责人合并。
