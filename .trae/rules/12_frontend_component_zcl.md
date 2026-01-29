# Trae 前端组件开发规范
> **前端规则**: 本文件属于 Vue3+TS 规范体系，适用于所有前端开发人员。

## 1. 组件 (Vue 3)
- **语法**：使用 `<script setup lang="ts">`。
- **命名**：PascalCase (如 `UserCard.vue`)。原子组件加 `Base` 前缀 (如 `BaseButton.vue`)。
- **Props**：必须使用 TypeScript 接口定义。
  ```typescript
  interface Props {
    title: string;
    isActive?: boolean; // 可选
  }
  defineProps<Props>();
  ```
- **样式**：必须使用 `<style scoped>`，避免样式污染。

## 2. 状态管理 (Stores)
- 使用 Pinia。
- 不要在组件中直接修改 Store 的 state，应该通过 Actions 修改。
- 业务逻辑尽量下沉到 Store 或 Composables，组件只负责调用和展示。
