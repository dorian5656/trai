#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/auth/auth_router.py
# 作者：whf
# 日期：2026-01-27
# 描述：认证模块路由定义

from fastapi import APIRouter, Depends, Body
from fastapi.security import OAuth2PasswordRequestForm
from backend.app.routers.auth.auth_func import AuthFunc, UserCreate, Token

router = APIRouter()

@router.post("/login", response_model=Token, summary="用户登录")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 兼容的 Token 登录接口 (Content-Type: application/x-www-form-urlencoded)

    Args:
        form_data (OAuth2PasswordRequestForm): 表单数据
            - username (str): 用户名 (A0001-A9999)
            - password (str): 密码

    Returns:
        Token: 访问令牌
            - access_token (str): JWT Token
            - token_type (str): Bearer
    """
    return await AuthFunc.login_for_access_token(form_data)

class LoginRequest(UserCreate):
    pass

@router.post("/login/json", response_model=Token, summary="用户登录 (JSON)")
async def login_json(user_in: LoginRequest):
    """
    JSON 格式的 Token 登录接口 (Content-Type: application/json)

    Args:
        user_in (LoginRequest): 登录数据
            - username (str): 用户名
            - password (str): 密码

    Returns:
        Token: 访问令牌
    """
    # 构造 OAuth2PasswordRequestForm 兼容对象
    class MockForm:
        def __init__(self, username, password):
            self.username = username
            self.password = password
            
    form_data = MockForm(username=user_in.username, password=user_in.password)
    return await AuthFunc.login_for_access_token(form_data)

@router.post("/wecom-login", response_model=Token, summary="企业微信静默登录")
async def wecom_login(code: str = Body(..., embed=True)):
    """
    企业微信 Code 换 Token

    Args:
        code (str): OAuth2 授权回调的 code

    Returns:
        Token: 访问令牌
            - access_token (str): JWT Token
            - token_type (str): Bearer
    """
    return await AuthFunc.login_by_wecom_code(code)

@router.post("/register", summary="用户注册")
async def register(user_in: UserCreate):
    """
    用户注册接口

    Args:
        user_in (UserCreate): 用户注册信息
            - username (str): 必须是 A+4位数字 (如 A0001)
            - password (str): 至少6位
            - email (str, optional): 邮箱
            - full_name (str, optional): 全名

    Note:
        注册后默认为"未激活"状态，需管理员审核

    Returns:
        User: 注册成功的用户信息
    """
    return await AuthFunc.register_user(user_in)