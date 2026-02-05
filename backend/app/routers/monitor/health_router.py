#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/monitor/health_router.py
# 作者：whf
# 日期：2026-02-05
# 描述：系统健康检查路由

from fastapi import APIRouter
from backend.app.utils.response import ResponseHelper, ResponseModel
from backend.app.routers.monitor.health_func import HealthManager

router = APIRouter()

@router.get("/health", response_model=ResponseModel, summary="系统健康检查")
async def health_check():
    """
    全面检查系统健康状态
    
    包括:
    - 数据库连接及关键表
    - 本地 AI 模型状态
    - 存储系统状态
    
    Returns:
        ResponseModel: 详细状态信息
    """
    try:
        status = await HealthManager.check_system_status()
        return ResponseHelper.success(status)
    except Exception as e:
        return ResponseHelper.error(msg=f"Health check failed: {e}")
