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

    Returns:
        dict: GPU 环境信息
            - torch (dict): PyTorch 版本及 CUDA 状态
            - paddle (dict): PaddlePaddle 版本及 GPU 状态
            - nvidia_smi (dict): 显卡详细信息
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

    Returns:
        dict: 系统资源使用情况
            - cpu (float): CPU 使用率
            - memory (dict): 内存总量与使用情况
            - disk (dict): 磁盘总量与使用情况
    """
    try:
        data = HardwareMonitor.check_system_resources()
        return ResponseHelper.success(data=data)
    except Exception as e:
        logger.error(f"系统资源检测失败: {e}")
        return ResponseHelper.error(msg=f"检测失败: {str(e)}")
