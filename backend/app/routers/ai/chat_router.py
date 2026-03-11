#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/chat_router.py
# 作者：whf
# 日期：2026-01-27
# 描述：AI 对话路由模块 (Router)

import uuid
from fastapi import APIRouter, Depends, Query, Body
from fastapi.responses import StreamingResponse
from backend.app.routers.ai.chat_func import ChatRequest, ChatResponse, AIManager
from backend.app.utils.ai_utils import AIUtils
from backend.app.utils.dependencies import get_current_active_user
from backend.app.utils.logger import logger
from backend.app.utils.response import ResponseHelper, ResponseModel

router = APIRouter()

@router.post("/chat/completions", response_model=ResponseModel, summary="AI 对话 (统一入口)")
async def chat_completions(
    request: ChatRequest = Body(..., description="对话请求参数"),
    current_user = Depends(get_current_active_user)
):
    """
    调用 AI 进行对话 (支持 DeepSeek API 和 本地 ModelScope)

    Args:
        request (ChatRequest): 请求体
            - messages (list): 消息历史
            - model (str): 模型名称 (deepseek-chat / Qwen3-VL-4B-Instruct)
            - temperature (float): 温度系数
            - max_tokens (int): 最大生成 Token 数
        current_user (User): 当前登录用户

    Returns:
        ResponseModel: 对话响应 (data=ChatResponse)
    """
    # 假设 current_user 支持属性访问 (根据 dependencies.py 推断)
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        result = await AIManager.chat_completion(request, user_id=str(user_id))
        return ResponseHelper.success(result)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))

@router.post("/chat/completions/stream", summary="DeepSeek 对话 (流式)")
async def chat_completions_stream(
    request: ChatRequest = Body(..., description="对话请求参数"),
    current_user = Depends(get_current_active_user)
):
    """
    调用 DeepSeek API 进行对话 (流式 SSE)

    Args:
        request (ChatRequest): 请求体
            - messages (list): 消息历史
            - model (str): 模型名称 (默认 deepseek-chat)
            - temperature (float): 温度系数
            - session_id (str, optional): 会话 ID (若无则自动生成)
        current_user (User): 当前登录用户

    Returns:
        StreamingResponse: SSE 流式响应 (text/event-stream)
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    session_id = request.session_id or str(uuid.uuid4())
    
    # 记录用户消息
    if request.messages and request.messages[-1].role == 'user':
        await AIManager.save_message(session_id, str(user_id), 'user', request.messages[-1].content, request.model)

    messages = [msg.model_dump() for msg in request.messages]
    
    async def event_generator():
        full_response = []
        try:
            async for chunk in AIUtils.chat_completion_stream(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                full_response.append(chunk)
                # SSE 格式: data: <content>\n\n
                yield f"data: {chunk}\n\n"
            
            yield "data: [DONE]\n\n"
            
            # 将完整对话记录存入数据库 (流式持久化)
            complete_text = "".join(full_response)
            await AIManager.save_message(session_id, str(user_id), 'assistant', complete_text, request.model)
            
        except Exception as e:
            logger.error(f"流式对话失败: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/chat/sessions", response_model=ResponseModel, summary="获取对话会话列表")
async def get_chat_sessions(
    limit: int = Query(20, description="限制返回的会话数量"),
    current_user = Depends(get_current_active_user)
):
    """
    获取当前用户的对话历史会话列表
    
    Args:
        limit (int): 限制数量 (默认20)
        current_user (User): 当前登录用户
    
    Returns:
        ResponseModel: 统一响应结构 (data=[{session_id, last_message, updated_at}, ...])
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        sessions = await AIManager.get_chat_sessions(str(user_id), limit)
        return ResponseHelper.success(sessions)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))

@router.get("/chat/messages", response_model=ResponseModel, summary="获取会话消息")
async def get_session_messages(
    session_id: str = Query(..., description="会话ID"),
    current_user = Depends(get_current_active_user)
):
    """
    获取指定会话的所有消息记录
    
    Args:
        session_id (str): 会话ID
        current_user (User): 当前登录用户
    
    Returns:
        ResponseModel: 统一响应结构 (data=[{role, content, created_at}, ...])
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        messages = await AIManager.get_session_messages(session_id, str(user_id))
        return ResponseHelper.success(messages)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))

@router.post("/chat/sessions/delete", response_model=ResponseModel, summary="删除对话会话")
async def delete_chat_session(
    session_id: str = Body(..., embed=True, description="会话ID"),
    current_user = Depends(get_current_active_user)
):
    """
    删除指定的会话 (及其所有消息)
    
    Args:
        session_id (str): 会话ID (通过 JSON Body 传递)
        current_user (User): 当前登录用户
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        await AIManager.delete_chat_session(session_id, str(user_id))
        return ResponseHelper.success(msg="会话删除成功")
    except Exception as e:
        return ResponseHelper.error(msg=str(e))

@router.post("/chat/messages/delete", response_model=ResponseModel, summary="删除单条消息")
async def delete_chat_message(
    message_id: str = Body(..., embed=True, description="消息ID"),
    current_user = Depends(get_current_active_user)
):
    """
    删除指定的单条消息
    
    Args:
        message_id (str): 消息ID (通过 JSON Body 传递)
        current_user (User): 当前登录用户
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        await AIManager.delete_chat_message(message_id, str(user_id))
        return ResponseHelper.success(msg="消息删除成功")
    except Exception as e:
        return ResponseHelper.error(msg=str(e))

@router.post("/chat/sessions/rename", response_model=ResponseModel, summary="重命名会话")
async def rename_chat_session(
    session_id: str = Body(..., description="会话ID"),
    name: str = Body(..., description="新会话名称"),
    current_user = Depends(get_current_active_user)
):
    """
    重命名指定会话
    
    Args:
        session_id (str): 会话ID
        name (str): 新名称
        current_user (User): 当前登录用户
    """
    user_id = getattr(current_user, "username", None) or current_user["username"]
    try:
        await AIManager.rename_chat_session(session_id, str(user_id), name)
        return ResponseHelper.success(msg="会话重命名成功")
    except Exception as e:
        return ResponseHelper.error(msg=str(e))