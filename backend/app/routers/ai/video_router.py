#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/video_router.py
# 作者：liuhd
# 日期：2026-02-06
# 描述：AI 视频生成路由模块

from fastapi import APIRouter, Depends, Body
from backend.app.routers.ai.video_func import (
    VideoGenRequest, VideoGenResponse, VideoManager
)
from backend.app.utils.dependencies import get_current_active_user
from backend.app.utils.response import ResponseHelper, ResponseModel

router = APIRouter()

@router.post("/generations", response_model=ResponseModel, summary="文生视频 (Wan2.1)")
async def generate_video(
    request: VideoGenRequest,  # 直接使用 Pydantic 模型作为 Body
    # current_user = Depends(get_current_active_user) # 开启鉴权
):
    """
    文生视频接口 (Wan2.1-T2V-1.3B)
    
    Args:
        request (VideoGenRequest): 请求体
            - prompt (str): 提示词
            - sampling_steps (int): 采样步数
            - guide_scale (float): 引导系数
    
    Returns:
        ResponseModel: 统一响应结构 (data=VideoGenResponse)
    """
    try:
        result = await VideoManager.generate_video(request)
        return ResponseHelper.success(result)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))
