#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/monitor/ai_models_router.py
# 作者：whf
# 日期：2026-01-26
# 描述：AI 模型状态监控路由 (Router)

from fastapi import APIRouter
from backend.app.utils.response import ResponseHelper
from backend.app.utils.logger import logger
from backend.app.routers.monitor.ai_models_func import ModelManager

router = APIRouter()

@router.post("/models", summary="获取所有模型状态")
async def get_models_status():
    """
    获取系统中所有 AI 模型的状态配置
    """
    try:
        models = await ModelManager.get_all_models()
        return ResponseHelper.success(data=models)
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return ResponseHelper.error(msg=f"获取失败: {str(e)}")
