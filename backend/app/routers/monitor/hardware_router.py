#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/monitor/hardware_router.py
# 作者：whf
# 日期：2026-01-26
# 描述：系统硬件与环境监控路由 (Router)

from fastapi import APIRouter
from backend.app.utils.response import ResponseHelper
from backend.app.utils.logger import logger
from backend.app.routers.monitor.hardware_func import HardwareMonitor

router = APIRouter()

@router.post("/env/gpu", summary="GPU环境检测")
async def check_gpu_env():
    """
    检测系统 GPU 环境 (Torch, Paddle, Nvidia-smi)
    """
    try:
        info = HardwareMonitor.check_gpu_env()
        return ResponseHelper.success(data=info)
    except Exception as e:
        logger.error(f"GPU环境检测失败: {e}")
        return ResponseHelper.error(msg=f"检测失败: {str(e)}")

@router.post("/env/system", summary="系统资源监控")
async def check_system_resources():
    """
    检测系统 CPU、内存、磁盘资源
    """
    try:
        data = HardwareMonitor.check_system_resources()
        return ResponseHelper.success(data=data)
    except Exception as e:
        logger.error(f"系统资源检测失败: {e}")
        return ResponseHelper.error(msg=f"检测失败: {str(e)}")
