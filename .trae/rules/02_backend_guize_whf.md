# TRAI 后端基础规范
> **后端规则**: 本文件属于python3规范体系, 适用于所有后端开发人员.

## 1. 通用规范
- **环境**: Py3.10.14; `trai_31014_whf`; UTF-8; 绝对导入; 类型注解; Google docstring.
- **命名**: 文件/函数/变量 `snake_case` (单单词全小写如 `response.py`, 多单词下划线如 `pg_utils.py`); 类 `PascalCase`; 常量 `UPPER_CASE`.
- **注释**: 类/函数/路由必须有中文说明和注释; 关键逻辑需行内注释.
- **日志**: 必须使用中文记录日志, 便于排查问题.
- **核心**: `backend.app.utils.logger` (封装 loguru); 尽可能多的日志; Env隔离; Pydantic校验; 统一异常; `pathlib`; PS禁用`&&`.
- **封装**: 脚本/工具必须使用类(`class`)封装, 禁止裸跑函数, 确保明确的职责和上下文(如数据库名).
- **红线**: 禁`print`, 相对导入, 裸SQL, 无类型/无注释(类/函数/路由必填), 返回原始对象.
- **限制**: 单个py文件禁止超过1000行, 若超标需拆分为多个文件调用.
- **结构**: 路由包必须包含 `_router.py` (仅路由定义) 和 `_func.py` (业务逻辑/脚本), 实现路由与逻辑分离.
- **推荐**: 异步优先(`async/await`); `asyncpg`连接池.
- **端口管理**: 启动服务前必须手动检查并 Kill 占用端口 (尤其是 Windows 环境: `netstat -ano | findstr :<PORT>` -> `taskkill /PID <PID> /F`; PORT 详见 `.env`)。
- **测试规范**: 发起 API 请求测试 (尤其是 AI 对话等耗时接口) 时，超时时间必须设置为 **至少 100秒**，防止因服务端处理慢导致的客户端误报超时。

## 2. 环境与依赖
- **命令**: `conda create -n trai_31014_whf python=3.10.14 && conda activate trai_31014_whf`
- **Pip**: `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 3. 文件头模板
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: {文件名} 
# 作者: whf
# 日期: {yyyy-MM-dd HH:mm:ss}
# 描述: {功能描述}
```
