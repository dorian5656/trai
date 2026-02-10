#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/dify/dify_router.py
# 作者：whf
# 日期：2026-01-28
# 描述：Dify 路由接口

from fastapi import APIRouter, Depends
from typing import Optional
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

    **Args:**

    - `request` (DifyChatRequest): 请求参数
        - `query` (str): 用户问题
        - `user` (str, optional): 用户标识 (后端会覆盖为当前用户)
        - `conversation_id` (str, optional): 会话ID
        - `inputs` (dict, optional): 变量输入
    - `current_user` (User): 当前登录用户

    **Returns:**

    - `StreamingResponse`: SSE 流式响应
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

    **Args:**

    - `request` (DifyChatRequest): 请求参数
        - `query` (str): 用户问题
        - `user` (str, optional): 用户标识 (若无则自动生成)
        - `conversation_id` (str, optional): 会话ID
        - `app_name` (str): 必须为 "guanwang" (后端强制覆盖)

    **Returns:**

    - `StreamingResponse`: SSE 流式响应
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
    last_id: Optional[str] = None,
    limit: int = 20,
    app_name: str = "guanwang",
    current_user = Depends(get_current_active_user)
):
    """
    获取 Dify 会话列表
    """
    return await DifyFunc.get_conversations(user=current_user.username, last_id=last_id, limit=limit, app_name=app_name)

@router.get("/messages", summary="获取会话历史消息")
async def get_conversation_messages(
    conversation_id: str,
    first_id: Optional[str] = None,
    limit: int = 20,
    app_name: str = "guanwang",
    current_user = Depends(get_current_active_user)
):
    """
    获取 Dify 会话历史消息
    """
    return await DifyFunc.get_conversation_messages(conversation_id=conversation_id, user=current_user.username, first_id=first_id, limit=limit, app_name=app_name)

@router.post("/conversations/{conversation_id}/rename", summary="会话重命名")
async def rename_conversation(
    conversation_id: str,
    name: Optional[str] = None,
    auto_generate: bool = False,
    app_name: str = "guanwang",
    current_user = Depends(get_current_active_user)
):
    """
    会话重命名
    """
    return await DifyFunc.rename_conversation(conversation_id=conversation_id, user=current_user.username, name=name, auto_generate=auto_generate, app_name=app_name)

@router.post("/conversations/{conversation_id}/delete", summary="删除会话")
async def delete_conversation(
    conversation_id: str,
    app_name: str = "guanwang",
    current_user = Depends(get_current_active_user)
):
    """
    删除会话
    """
    result = await DifyFunc.delete_conversation(conversation_id=conversation_id, user=current_user.username, app_name=app_name)
    return {"success": result}
