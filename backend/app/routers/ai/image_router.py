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

router = APIRouter()

@router.post("/chat/image", response_model=ImageChatResponse, summary="多模态对话 (Qwen-VL)")
async def chat_with_image(
    request: ImageChatRequest,
    current_user = Depends(get_current_active_user)
):
    """
    多模态对话接口 (支持图文对话)
    - **messages**: 消息列表 (支持 image_url)
    - **model**: 模型 (默认 Qwen3-VL-8B-Instruct)
    """
    return await ImageManager.chat_with_image(request)

@router.post("/generations", response_model=ImageGenResponse, summary="文生图 (Image Generation)")
async def generate_image(
    request: ImageGenRequest,
    current_user = Depends(get_current_active_user)
):
    """
    文生图接口
    - **prompt**: 提示词
    - **model**: 模型 (默认 FLUX.2-dev)
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    return await ImageManager.generate_image(request, user_id=str(user_id))
