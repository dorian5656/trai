#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/auth/auth_router.py
# 作者：whf
# 日期：2026-01-27
# 描述：认证模块路由定义

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from backend.app.routers.auth.auth_func import AuthFunc, UserCreate, Token

router = APIRouter()

@router.post("/login", response_model=Token, summary="用户登录")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 兼容的 Token 登录接口
    - **username**: 用户名 (A0001-A9999)
    - **password**: 密码
    """
    return await AuthFunc.login_for_access_token(form_data)

@router.post("/register", summary="用户注册")
async def register(user_in: UserCreate):
    """
    用户注册接口
    - **username**: 必须是 A+4位数字 (如 A0001)
    - **password**: 至少6位
    - **其他信息**: 可选
    - **注意**: 注册后默认为"未激活"状态，需管理员审核
    """
    return await AuthFunc.register_user(user_in)