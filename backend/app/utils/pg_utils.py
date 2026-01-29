#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/pg_utils.py
# 作者：whf
# 日期：2026-01-26
# 描述：PostgreSQL 数据库工具类

from typing import Any, List, Dict, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from backend.app.config import settings
from backend.app.utils.logger import logger

class PGUtils:
    """
    PostgreSQL 工具类
    用于管理数据库连接引擎和会话工厂，以及提供通用的增删改查方法
    """
    _engine = None
    _session_factory = None

    @classmethod
    def get_engine(cls):
        """
        获取数据库引擎单例
        :return: AsyncEngine
        """
        if cls._engine is None:
            logger.info(f"正在初始化数据库连接: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
            cls._engine = create_async_engine(
                settings.SQLALCHEMY_DATABASE_URI,
                echo=False,
                future=True,
                pool_pre_ping=True
            )
        return cls._engine

    @classmethod
    def get_session_factory(cls):
        """
        获取会话工厂单例
        :return: async_sessionmaker
        """
        if cls._session_factory is None:
            engine = cls.get_engine()
            cls._session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        return cls._session_factory

    @classmethod
    async def get_db_version(cls) -> str:
        """
        获取数据库版本
        :return: 版本字符串
        """
        session_factory = cls.get_session_factory()
        async with session_factory() as session:
            try:
                result = await session.execute(text("SELECT version();"))
                version = result.scalar()
                return version
            except Exception as e:
                logger.error(f"获取数据库版本失败: {e}")
                raise e

    @classmethod
    async def execute_ddl(cls, sql: str, params: Dict[str, Any] = None) -> bool:
        """
        执行 DDL 语句 (建表/删表等)
        :param sql: SQL 语句
        :param params: 参数字典
        :return: 是否成功
        """
        session_factory = cls.get_session_factory()
        async with session_factory() as session:
            try:
                async with session.begin():
                    logger.info(f"正在执行 DDL 语句: {sql}")
                    await session.execute(text(sql), params)
                return True
            except Exception as e:
                logger.error(f"DDL 执行失败: {e}")
                raise e

    @classmethod
    async def fetch_all(cls, sql: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        执行查询，返回所有结果
        :param sql: SQL 语句
        :param params: 参数字典
        :return: 结果列表
        """
        session_factory = cls.get_session_factory()
        async with session_factory() as session:
            try:
                logger.debug(f"正在执行查询: {sql}, 参数: {params}")
                result = await session.execute(text(sql), params)
                # 使用 mappings() 获取字典结果
                return [dict(row) for row in result.mappings()]
            except Exception as e:
                logger.error(f"查询失败: {e}")
                raise e

    @classmethod
    async def fetch_one(cls, sql: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        执行查询，返回单条结果
        :param sql: SQL 语句
        :param params: 参数字典
        :return: 结果字典或 None
        """
        rows = await cls.fetch_all(sql, params)
        if rows:
            return rows[0]
        return None

    @classmethod
    async def execute_update(cls, sql: str, params: Dict[str, Any] = None) -> int:
        """
        执行增删改操作
        :param sql: SQL 语句
        :param params: 参数字典
        :return: 影响行数
        """
        session_factory = cls.get_session_factory()
        async with session_factory() as session:
            try:
                async with session.begin():
                    logger.info(f"正在执行更新: {sql}, 参数: {params}")
                    result = await session.execute(text(sql), params)
                    return result.rowcount
            except Exception as e:
                logger.error(f"更新失败: {e}")
                raise e

    @classmethod
    async def create_database(cls, db_name: str) -> bool:
        """
        创建新数据库
        注意: 需要连接到 postgres 默认数据库执行，且不能在事务中运行
        :param db_name: 数据库名称
        :return: 是否成功
        """
        # 构建连接到默认 postgres 数据库的 URI
        default_db_uri = settings.SQLALCHEMY_DATABASE_URI.replace(f"/{settings.POSTGRES_DB}", "/postgres")
        
        engine = create_async_engine(
            default_db_uri,
            isolation_level="AUTOCOMMIT",
            echo=False
        )
        
        try:
            async with engine.connect() as conn:
                # 检查数据库是否存在
                result = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
                if result.scalar():
                    logger.warning(f"数据库 {db_name} 已存在")
                    return False
                
                logger.info(f"正在创建数据库: {db_name}")
                await conn.execute(text(f"CREATE DATABASE {db_name}"))
                return True
        except Exception as e:
            logger.error(f"创建数据库 {db_name} 失败: {e}")
            raise e
    @classmethod
    def get_base(cls):
        """获取 SQLAlchemy Base"""
        if not hasattr(cls, "_Base"):
             from sqlalchemy.orm import declarative_base
             cls._Base = declarative_base()
        return cls._Base

# 全局 Base 实例
Base = PGUtils.get_base()

# FastAPI Dependency
async def get_db():
    """
    FastAPI 依赖，用于获取数据库会话
    """
    session_factory = PGUtils.get_session_factory()
    async with session_factory() as session:
        yield session
