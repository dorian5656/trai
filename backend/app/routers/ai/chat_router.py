#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/chat_router.py
# 作者：whf
# 日期：2026-01-27
# 描述：AI 对话路由模块 (Router)

import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from backend.app.routers.ai.chat_func import ChatRequest, ChatResponse, AIManager
from backend.app.utils.ai_utils import AIUtils
from backend.app.utils.dependencies import get_current_active_user
from backend.app.utils.logger import logger
from backend.app.utils.response import ResponseHelper, ResponseModel

router = APIRouter()

@router.post("/chat/completions", response_model=ResponseModel, summary="AI 对话 (统一入口)")
async def chat_completions(
    request: ChatRequest,
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
    request: ChatRequest,
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