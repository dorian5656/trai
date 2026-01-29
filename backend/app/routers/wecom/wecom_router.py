#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/app/routers/wecom/wecom_router.py
# 作者: whf
# 日期: 2026-01-27
# 描述: 企业微信路由定义

from fastapi import APIRouter, Query
from backend.app.utils.response import ResponseHelper
from backend.app.routers.wecom.wecom_func import wecom_service

router = APIRouter()

@router.get("/user", summary="获取企业微信用户信息")
async def get_wecom_user(user_id: str = Query(..., description="企业微信用户ID")):
    try:
        data = await wecom_service.get_user_info(user_id)
        return ResponseHelper.success(data=data)
    except Exception as e:
        return ResponseHelper.error(msg=f"获取用户信息失败: {str(e)}")

@router.get("/departments", summary="获取企业微信部门列表")
async def get_wecom_departments(id: int = Query(None, description="部门ID")):
    try:
        data = await wecom_service.get_departments(id)
        return ResponseHelper.success(data=data)
    except Exception as e:
        return ResponseHelper.error(msg=f"获取部门列表失败: {str(e)}")

@router.post("/sync", summary="同步企业微信数据到数据库")
async def sync_wecom_data():
    """
    同步企业微信的部门和用户数据到本地数据库 (sys_departments, sys_users)
    """
    try:
        data = await wecom_service.sync_data()
        return ResponseHelper.success(data=data, msg="同步成功")
    except Exception as e:
        return ResponseHelper.error(msg=f"同步失败: {str(e)}")
