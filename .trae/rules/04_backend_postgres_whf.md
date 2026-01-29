# TRAI PostgreSQL 数据库规范
> **后端规则**: 本文件属于python3规范体系, 适用于所有后端开发人员.

## 1. 核心选型
- PG16+ (`pgvector`); `asyncpg`; `SQLAlchemy 2.0+` (AsyncSession).

## 2. 设计规范
- **命名**: 表名复数snake_case (`users`); 字段snake_case; 索引`idx_{tbl}_{col}`.
- **主键**: 推荐 `UUID`/`BigInt Identity`; 禁止 `Serial`.
- **必备**: `created_at` (创建时间); `updated_at` (更新时间); `is_deleted` (是否删除).
- **时间**: 必须使用 `TIMESTAMP(0)` 或 `TIMESTAMPTZ(0)`; 格式强制为 `YYYY-MM-DD HH:MM:SS` (去除毫秒与时区后缀).
- **注释**: 必须含中文注释 (`创建时间`, `更新时间`, `是否删除` 等); 全表/字段必填.
- **元数据**: 必须维护 `table_registry` 总表, 记录所有业务表的名称, 描述, 创建时间等信息, 实现表结构自描述.

## 3. 开发红线
1. **N+1**: 禁止循环SQL, 必须用 `joinedload`/`selectinload`.
2. **SELECT ***: 禁止, 必须指定列.
3. **裸SQL**: 禁止拼接, 必须用 `text()` + `bindparams`.
4. **DDL**: 生产禁手动, 必须用 `Alembic`.
5. **事务**: 写操作必须显式事务.
