#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/dify/dify_router.py
# 作者：whf
# 日期：2026-01-28
# 描述：Dify 路由接口

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from backend.app.routers.dify.dify_func import DifyFunc, DifyChatRequest
from backend.app.utils.dependencies import get_current_active_user

router = APIRouter()

@router.post("/chat", summary="Dify 对话 (流式)")
async def chat_message(
    request: DifyChatRequest,
    current_user = Depends(get_current_active_user)
):
    """
    调用 Dify API 进行对话 (流式 SSE)
    """
    # 强制使用当前用户的 username 作为 Dify user 标识 (或者可以使用 request.user)
    # 这里为了安全，可以覆盖 request.user，或者允许前端传但做校验
    # 暂时使用 request.user，前端需传入
    
    generator = await DifyFunc.chat_message(request)
    return StreamingResponse(generator, media_type="text/event-stream")

@router.post("/chat/public", summary="Dify 对话 (官网公开/匿名)")
async def chat_message_public(
    request: DifyChatRequest
):
    """
    官网专用公开对话接口 (无 Token 验证)
    - 强制 app_name="guanwang"
    """
    # 强制覆盖 app_name，防止滥用
    request.app_name = "guanwang"
    
    # 允许匿名，如果没有 user 则自动生成一个 session user id 或直接透传
    if not request.user:
        request.user = "anonymous_web_user"
        
    generator = await DifyFunc.chat_message(request)
    return StreamingResponse(generator, media_type="text/event-stream")

@router.get("/conversations", summary="获取会话列表")
async def get_conversations(
    user: str,
    limit: int = 20,
    app_name: str = "guanwang",
    current_user = Depends(get_current_active_user)
):
    """
    获取 Dify 会话列表
    """
    return await DifyFunc.get_conversations(user=user, limit=limit, app_name=app_name)
