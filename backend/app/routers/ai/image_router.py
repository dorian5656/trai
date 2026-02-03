#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/image_router.py
# 作者：liuhd
# 日期：2026-01-28
# 描述：AI 图像/多模态路由模块

from fastapi import APIRouter, Depends
from backend.app.routers.ai.image_func import (
    ImageChatRequest, ImageChatResponse, ImageManager,
    ImageGenRequest, ImageGenResponse
)
from backend.app.utils.dependencies import get_current_active_user
from backend.app.utils.response import ResponseHelper, ResponseModel

router = APIRouter()

@router.post("/chat/image", response_model=ResponseModel, summary="多模态对话 (Qwen-VL)")
async def chat_with_image(
    request: ImageChatRequest,
    current_user = Depends(get_current_active_user)
):
    """
    多模态对话接口 (支持图文对话)

    Args:
        request (ImageChatRequest): 请求体
            - messages (list): 消息列表 (支持 image_url)
            - model (str): 模型名称 (默认 Qwen3-VL-8B-Instruct)
            - temperature (float): 温度系数
        current_user (User): 当前登录用户

    Returns:
        ResponseModel: 统一响应结构 (data=ImageChatResponse)
    """
    try:
        result = await ImageManager.chat_with_image(request)
        return ResponseHelper.success(result)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))

@router.post("/generations", response_model=ResponseModel, summary="文生图 (Image Generation)")
async def generate_image(
    request: ImageGenRequest,
    current_user = Depends(get_current_active_user)
):
    """
    文生图接口

    Args:
        request (ImageGenRequest): 请求体
            - prompt (str): 提示词
            - model (str): 模型名称 (默认 Z-Image)
            - size (str): 图片尺寸
            - n (int): 生成数量
        current_user (User): 当前登录用户

    Returns:
        ResponseModel: 统一响应结构 (data=ImageGenResponse)
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        result = await ImageManager.generate_image(request, user_id=str(user_id))
        return ResponseHelper.success(result)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))
