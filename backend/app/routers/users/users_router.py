#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/users/users_router.py
# 作者：whf
# 日期：2026-01-27
# 描述：用户管理模块路由定义

from typing import List
from fastapi import APIRouter, Depends
from backend.app.routers.users.users_func import UsersFunc, UserResponse, UserAudit, PasswordChange
from backend.app.utils.dependencies import get_current_user, get_current_active_user, get_current_superuser

router = APIRouter()

@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def read_users_me(current_user = Depends(get_current_active_user)):
    """
    获取当前登录用户的详细信息
    """
    return await UsersFunc.get_me(current_user)

@router.get("/", response_model=List[UserResponse], summary="获取用户列表")
async def read_users(
    skip: int = 0, 
    limit: int = 100, 
    current_user = Depends(get_current_superuser)
):
    """
    获取所有用户列表 (仅超级管理员)
    """
    return await UsersFunc.get_users(skip, limit)

@router.post("/audit", summary="审核用户")
async def audit_user(
    audit_data: UserAudit, 
    current_user = Depends(get_current_superuser)
):
    """
    审核用户注册申请 (仅超级管理员)
    - **is_active=True**: 通过
    - **is_active=False**: 拒绝/禁用
    """
    return await UsersFunc.audit_user(audit_data)

@router.post("/change-password", summary="修改密码")
async def change_password(
    password_data: PasswordChange,
    current_user = Depends(get_current_active_user)
):
    """
    修改当前用户密码
    - 需要提供旧密码验证
    - 需要填写修改理由
    """
    return await UsersFunc.change_password(current_user, password_data)