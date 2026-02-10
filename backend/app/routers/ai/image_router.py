#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/image_router.py
# 作者：liuhd
# 日期：2026-01-28
# 描述：AI 图像/多模态路由模块

from fastapi import APIRouter, Depends, Body
from fastapi.responses import StreamingResponse
from backend.app.routers.ai.image_func import (
    ImageChatRequest, ImageChatResponse, ImageManager,
    ImageGenRequest, ImageGenResponse
)
from backend.app.utils.dependencies import get_current_active_user
from backend.app.utils.response import ResponseHelper, ResponseModel

router = APIRouter()

@router.post("/chat/image/stream", summary="多模态对话 (Qwen-VL) - 流式")
async def chat_with_image_stream(
    request: ImageChatRequest = Body(..., description="多模态对话请求"),
    current_user = Depends(get_current_active_user)
):
    """
    多模态对话接口 (流式 SSE)

    Args:
        request (ImageChatRequest): 请求体
        current_user (User): 当前登录用户

    Returns:
        StreamingResponse: SSE 流式响应
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    
    async def event_generator():
        try:
            async for chunk in ImageManager.chat_with_image_stream(request, user_id=str(user_id)):
                # SSE 格式
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/chat/image", response_model=ResponseModel, summary="多模态对话 (Qwen-VL)")
async def chat_with_image(
    request: ImageChatRequest = Body(..., description="多模态对话请求"),
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
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        result = await ImageManager.chat_with_image(request, user_id=str(user_id))
        return ResponseHelper.success(result)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))

@router.post("/generations", response_model=ResponseModel, summary="文生图 (Image Generation)")
async def generate_image(
    request: ImageGenRequest = Body(..., description="文生图请求"),
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

@router.get("/image/history", response_model=ResponseModel, summary="获取文生图历史")
async def get_image_history(
    page: int = 1,
    size: int = 20,
    current_user = Depends(get_current_active_user)
):
    """
    获取文生图历史记录
    
    Args:
        page (int): 页码
        size (int): 每页数量
        current_user (User): 当前登录用户
    
    Returns:
        ResponseModel: 统一响应结构 (data={total, items})
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        result = await ImageManager.get_image_history(str(user_id), page, size)
        return ResponseHelper.success(result)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))

@router.post("/image/history/delete", response_model=ResponseModel, summary="删除文生图记录")
async def delete_image_history(
    image_id: str = Body(..., embed=True, description="图片记录ID"),
    current_user = Depends(get_current_active_user)
):
    """
    删除指定的文生图记录 (软删除)
    
    Args:
        image_id (str): 图片记录ID (通过 JSON Body 传递)
        current_user (User): 当前登录用户
    
    Returns:
        ResponseModel: 成功或失败
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        await ImageManager.delete_image_history(image_id, str(user_id))
        return ResponseHelper.success(msg="删除成功")
    except Exception as e:
        return ResponseHelper.error(msg=str(e))
