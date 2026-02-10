# Trae 前端规范索引
> **前端规则**: 本文件属于 Vue3+TS 规范体系，适用于所有前端开发人员。

## 目录
1. **[10_Structure](./10_frontend_structure_zcl.md)**: 目录/分层
2. **[11_Base](./11_frontend_base_zcl.md)**: 基础/语言/TS
3. **[12_Component](./12_frontend_component_zcl.md)**: 组件/Store
4. **[13_API](./13_frontend_api_zcl.md)**: 接口/工程化

## 核心摘要
- **中文强制**: 注释、日志必须用中文。
- **严禁 Any**: TS 强类型。
- **解耦**: API - Request - Component 分离。

## 强制规则
- 变更日志: 每次前端改动必须更新 `frontend/CHANGELOG.md`。
- 时间戳: 使用三级标题 `### YYYY_MM_DD_HHMM`, 倒序排列 (最新在最上)。
- 描述: 统一中文, 分类标注为 `前端-内容`, 使用英文标点。
- Lint: 提交前必须通过 ESLint + Prettier 检查。
- 文件头: 所有源文件必须包含标准注释头 (文件名, 作者, 日期, 描述)。
- TypeScript: 启用 strict 模式; 禁止 `any` 与 `@ts-ignore` (特殊情况需 Code Review)。
- 组件与样式: 使用 Vue3 `<script setup lang="ts">`; Props 定义 Interface; 样式使用 `<style scoped>`。
- 请求与 API: 统一通过 `src/utils/request` 调用; 自动注入 Token; 统一错误拦截; 响应自动解包。
