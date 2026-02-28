#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/dependencies.py
# 作者：whf
# 日期：2026-01-27
# 描述：FastAPI 依赖项 (Auth) - 迁移自 app/dependencies.py

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy import text

from backend.app.config import settings
from backend.app.utils.pg_utils import PGUtils

# OAuth2 方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    获取当前登录用户
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except (JWTError, ValidationError):
        raise credentials_exception
        
    # 查询数据库获取用户信息
    engine = PGUtils.get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM sys_users WHERE username = :username"),
            {"username": username}
        )
        user = result.mappings().one_or_none()
        
    if user is None:
        raise credentials_exception
        
    return user

async def get_current_active_user(current_user = Depends(get_current_user)):
    """
    获取当前激活用户
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="用户未激活")
    return current_user

async def get_current_superuser(current_user = Depends(get_current_active_user)):
    """
    获取当前超级管理员
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="权限不足"
        )
    return current_user

async def get_db():
    """
    获取数据库会话 (Dependency)
    """
    session_factory = PGUtils.get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
