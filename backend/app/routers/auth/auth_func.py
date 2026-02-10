#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/auth/auth_func.py
# 作者：whf
# 日期：2026-01-27
# 描述：认证模块业务逻辑 (注册/登录)

from datetime import timedelta, datetime
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import text
from pydantic import BaseModel, Field, field_validator
import re
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.security import verify_password, get_password_hash, create_access_token
from backend.app.utils.logger import logger
from backend.app.config import settings

# =============================================================================
# Schema 定义 (Auth)
# =============================================================================

# 用户基础模型
class UserBase(BaseModel):
    """
    用户基础信息模型
    用于定义用户通用的属性字段
    """
    username: str = Field(..., description="用户名", examples=["A8888"])
    full_name: Optional[str] = Field(None, description="真实姓名", examples=["张三"])
    email: Optional[str] = Field(None, description="邮箱", examples=["zhangsan@example.com"])
    phone: Optional[str] = Field(None, description="手机号", examples=["13800138000"])
    wecom_userid: Optional[str] = Field(None, description="企业微信 UserID", examples=["zhangsan"])
    avatar: Optional[str] = Field(None, description="头像 URL", examples=["https://example.com/avatar.jpg"])

# 用户注册请求
class UserCreate(UserBase):
    """
    用户注册请求模型
    """
    password: str = Field(..., min_length=6, description="密码", examples=["123456"])
    
    @field_validator('username')
    def validate_username(cls, v):
        """
        校验用户名格式
        必须是 A 开头，后接 4 位数字 (A0001 - A9999)
        """
        # 用户名必须是 A 开头，后接 4 位数字 (A0001 - A9999)
        # 正则: ^A\d{4}$
        if not re.match(r'^A\d{4}$', v):
            raise ValueError('用户名格式必须为 A 加 4 位数字 (例如: A0001)')
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "A8888",
                "full_name": "张三",
                "email": "zhangsan@example.com",
                "phone": "13800138000",
                "password": "secretpassword"
            }
        }
    }

# Token 响应
class Token(BaseModel):
    """
    JWT Token 响应模型
    """
    access_token: str = Field(..., description="访问令牌", examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."])
    token_type: str = Field(..., description="令牌类型 (Bearer)", examples=["bearer"])

class AuthFunc:
    """
    认证模块业务逻辑
    """
    
    @staticmethod
    async def login_for_access_token(form_data) -> Token:
        """
        用户登录获取 Token
        """
        engine = PGUtils.get_engine()
        async with engine.connect() as conn:
            # 1. 查询用户
            result = await conn.execute(
                text("SELECT * FROM sys_users WHERE username = :username"),
                {"username": form_data.username}
            )
            user = result.mappings().one_or_none()
            
            # 2. 验证用户和密码
            if not user or not verify_password(form_data.password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户名或密码错误",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # 3. 验证是否激活
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="账户未激活，请联系管理员审核"
                )
                
            # 4. 生成 Token
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.username}, expires_delta=access_token_expires
            )
            
            logger.info(f"用户登录成功: {user.username}")
            
            # 发送飞书通知
            try:
                from backend.app.utils.feishu_utils import feishu_bot
                feishu_bot.send_webhook_message(f"👤 **用户登录通知**\n用户: {user.username}\n姓名: {user.full_name or '未知'}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                pass

            return Token(access_token=access_token, token_type="bearer")

    @staticmethod
    async def login_by_wecom_code(code: str) -> Token:
        """
        企业微信静默登录
        """
        from backend.app.utils.wecom_utils import wecom_app
        
        # 1. 用 code 换取 UserId
        try:
            wecom_userid = wecom_app.get_user_id_by_code(code)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"企业微信授权失败: {str(e)}")
            
        if not wecom_userid:
            raise HTTPException(status_code=401, detail="未获取到有效的企业成员信息")
            
        # 2. 查库
        engine = PGUtils.get_engine()
        async with engine.connect() as conn:
            # 优先匹配 wecom_userid
            result = await conn.execute(
                text("SELECT * FROM sys_users WHERE wecom_userid = :uid AND is_active = TRUE"),
                {"uid": wecom_userid}
            )
            user = result.mappings().one_or_none()
            
            if not user:
                # 尝试匹配 username (兼容旧数据)
                result = await conn.execute(
                    text("SELECT * FROM sys_users WHERE username = :uid AND is_active = TRUE"),
                    {"uid": wecom_userid}
                )
                user = result.mappings().one_or_none()
            
            if not user:
                logger.warning(f"企微用户尝试登录但未同步: {wecom_userid}")
                raise HTTPException(
                    status_code=401, 
                    detail="用户未同步或无权限，请联系管理员同步通讯录"
                )
                
            # 3. 生成 Token
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.username}, expires_delta=access_token_expires
            )
            
            logger.info(f"企业微信静默登录成功: {user.username} ({wecom_userid})")
            return Token(access_token=access_token, token_type="bearer")

    @staticmethod
    async def register_user(user_in: UserCreate):
        """
        用户注册
        """
        engine = PGUtils.get_engine()
        async with engine.begin() as conn:
            # 1. 检查用户名是否存在
            exists = await conn.execute(
                text("SELECT 1 FROM sys_users WHERE username = :username"),
                {"username": user_in.username}
            )
            if exists.scalar():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="用户名已存在"
                )
            
            # 2. 创建用户 (默认未激活)
            password_hash = get_password_hash(user_in.password)
            
            # 插入数据
            await conn.execute(
                text("""
                    INSERT INTO sys_users (
                        username, password_hash, full_name, email, phone, 
                        wecom_userid, avatar, source, is_active, is_superuser, 
                        created_at, updated_at
                    ) VALUES (
                        :username, :password_hash, :full_name, :email, :phone,
                        :wecom_userid, :avatar, 'local', FALSE, FALSE,
                        NOW(), NOW()
                    )
                """),
                {
                    "username": user_in.username,
                    "password_hash": password_hash,
                    "full_name": user_in.full_name,
                    "email": user_in.email,
                    "phone": user_in.phone,
                    "wecom_userid": user_in.wecom_userid,
                    "avatar": user_in.avatar
                }
            )
            
            logger.info(f"新用户注册成功: {user_in.username} (待审核)")
            return {"msg": "注册成功，请等待管理员审核", "username": user_in.username}