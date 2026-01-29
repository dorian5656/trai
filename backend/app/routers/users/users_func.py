#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/users/users_func.py
# 作者：whf
# 日期：2026-01-27
# 描述：用户管理模块业务逻辑 (审核/修改密码)

from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import text
from pydantic import BaseModel, Field
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.security import verify_password, get_password_hash
from backend.app.utils.logger import logger

# =============================================================================
# Schema 定义 (Users)
# =============================================================================

# 用户基础模型 (复用定义或重新定义，这里为了解耦重新定义)
class UserBase(BaseModel):
    """
    用户基础信息模型
    """
    username: str = Field(..., description="用户名")
    full_name: Optional[str] = Field(None, description="真实姓名")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")
    wecom_userid: Optional[str] = Field(None, description="企业微信 UserID")
    avatar: Optional[str] = Field(None, description="头像 URL")

# 用户响应模型
class UserResponse(UserBase):
    """
    用户响应模型
    包含用户的所有公开信息
    """
    id: str = Field(..., description="用户ID (UUID)")
    is_active: bool = Field(..., description="是否激活")
    is_superuser: bool = Field(..., description="是否超级管理员")
    source: str = Field(..., description="注册来源")
    created_at: str = Field(..., description="创建时间") # 简化为 str，实际可能需要 datetime
    
    class Config:
        from_attributes = True

# 审核请求
class UserAudit(BaseModel):
    """
    用户审核请求模型
    """
    username: str = Field(..., description="待审核用户名")
    is_active: bool = Field(..., description="审核结果 (True:通过, False:拒绝/禁用)")
    remark: Optional[str] = Field(None, description="审核备注")

# 修改密码请求
class PasswordChange(BaseModel):
    """
    修改密码请求模型
    """
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码 (至少6位)")
    reason: str = Field(..., min_length=1, description="修改密码原因")

class UsersFunc:
    """
    用户管理模块业务逻辑
    """
    
    @staticmethod
    async def get_users(skip: int = 0, limit: int = 100) -> List[UserResponse]:
        """
        获取用户列表 (仅管理员)
        """
        engine = PGUtils.get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT * FROM sys_users 
                    ORDER BY created_at DESC 
                    OFFSET :skip LIMIT :limit
                """),
                {"skip": skip, "limit": limit}
            )
            users = result.mappings().all()
            return [UserResponse(**user) for user in users]

    @staticmethod
    async def get_me(current_user: UserResponse) -> UserResponse:
        """
        获取当前用户信息
        """
        return current_user

    @staticmethod
    async def audit_user(audit_data: UserAudit):
        """
        审核用户 (仅管理员)
        """
        engine = PGUtils.get_engine()
        async with engine.begin() as conn:
            # 检查用户是否存在
            result = await conn.execute(
                text("SELECT * FROM sys_users WHERE username = :username"),
                {"username": audit_data.username}
            )
            user = result.mappings().one_or_none()
            
            if not user:
                raise HTTPException(status_code=404, detail="用户不存在")
            
            # 更新状态
            await conn.execute(
                text("""
                    UPDATE sys_users 
                    SET is_active = :is_active, updated_at = NOW()
                    WHERE username = :username
                """),
                {"is_active": audit_data.is_active, "username": audit_data.username}
            )
            
            action = "通过" if audit_data.is_active else "拒绝/禁用"
            logger.info(f"管理员审核用户 {audit_data.username}: {action} (备注: {audit_data.remark})")
            return {"msg": f"用户 {audit_data.username} 审核已{action}"}

    @staticmethod
    async def change_password(current_user, password_data: PasswordChange):
        """
        修改密码
        """
        # 验证旧密码
        if not verify_password(password_data.old_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="旧密码错误")
            
        # 更新新密码
        new_hash = get_password_hash(password_data.new_password)
        
        engine = PGUtils.get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE sys_users 
                    SET password_hash = :password_hash, updated_at = NOW()
                    WHERE username = :username
                """),
                {"password_hash": new_hash, "username": current_user.username}
            )
            
        logger.info(f"用户 {current_user.username} 修改了密码 (原因: {password_data.reason})")
        return {"msg": "密码修改成功"}