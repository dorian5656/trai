# Dify 配置管理与迁移方案

## 1. 背景与目标
当前 Dify 的应用配置（如 API Key、App ID）分散在代码或环境变量中，难以动态管理。
目标是将这些配置迁移至数据库表 `sys_dify_apps`，并提供管理接口，实现：
- 动态添加/修改 Dify 应用
- 自动同步 Dify 平台上的应用列表
- 统一管理 API Key

## 2. 数据库设计 (PostgreSQL)

### 表名: `sys_dify_apps`

| 字段名 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | BIGINT | PK, Auto Inc | 主键 |
| `dify_app_id` | VARCHAR(100) | Unique, Not Null | Dify 平台的应用 ID (如 `b5ae82c7...`) |
| `name` | VARCHAR(255) | Not Null | 应用名称 |
| `slug` | VARCHAR(255) | Nullable | 应用标识符 (用于前端路由或代码引用) |
| `api_key` | VARCHAR(255) | Nullable | **[核心]** 该应用的 API Key |
| `mode` | VARCHAR(50) | Default 'chat' | 应用模式 (chat/workflow/advanced-chat) |
| `icon` | VARCHAR(255) | Nullable | 图标 URL 或 Emoji 字符 |
| `icon_background` | VARCHAR(20) | Nullable | 图标背景色 (如 #FFEAD5) |
| `description` | TEXT | Nullable | 应用描述 |
| `is_active` | BOOLEAN | Default True | 是否启用 |
| `sync_source` | VARCHAR(20) | Default 'api' | 同步来源 ('api' / 'manual' / 'db_direct') |
| `created_at` | TIMESTAMP | Not Null | 创建时间 |
| `updated_at` | TIMESTAMP | Not Null | 更新时间 |

## 3. 同步策略

### 方案 A: API 同步 (当前推荐)
- **原理**: 使用用户的 Dify 账号 Token (Session) 调用 Dify 内部 API (`/console/api/apps`) 获取应用列表。
- **优点**: 无需修改 Dify 部署配置，直接通过 HTTP 请求获取。
- **缺点**: 
  - 只能获取应用元数据 (ID, Name, Icon)。
  - **无法获取 API Key** (安全限制，API Key 仅在生成时可见，或需从 Dify 数据库读取)。
- **应对**: API Key 仍需在我们的管理后台手动回填，或采用方案 B。

### 方案 B: 数据库直连 (终极方案)
- **原理**: 开放 Dify PostgreSQL 端口 (`5432`)，直接读取 `api_tokens` 表。
- **配置**: 需修改 Dify `docker-compose.yaml` 映射端口。
- **优点**: 可自动获取所有 API Key，实现 100% 自动化。
- **风险**: 需暴露数据库端口 (可通过防火墙限制 IP)。

## 4. 实施步骤

1.  **[已完成]** 编写 API 测试脚本 (`scripts/test_dify_apps_params.py`) 验证列表获取。
2.  **[待执行]** 创建 `sys_dify_apps` 数据库表。
3.  **[待执行]** 编写同步脚本/接口：
    - 登录 Dify 获取 Token。
    - 拉取应用列表。
    - 存入/更新 `sys_dify_apps`。
4.  **[待执行]** 开发管理后台接口 (更新 API Key)。

## 5. 参考信息
- Dify Host: `192.168.100.119`
- 登录接口: `/console/api/login`
- 列表接口: `/console/api/apps`
