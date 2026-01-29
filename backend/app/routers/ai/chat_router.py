#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/chat_router.py
# 作者：whf
# 日期：2026-01-27
# 描述：AI 对话路由模块 (Router)

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from backend.app.routers.ai.chat_func import ChatRequest, ChatResponse, AIManager
from backend.app.utils.ai_utils import AIUtils
from backend.app.utils.dependencies import get_current_active_user

router = APIRouter()

@router.post("/chat/completions", response_model=ChatResponse, summary="AI 对话 (统一入口)")
async def chat_completions(
    request: ChatRequest,
    current_user = Depends(get_current_active_user)
):
    """
    调用 AI 进行对话 (支持 DeepSeek API 和 本地 ModelScope)
    - **messages**: 消息历史
    - **model**: 模型 (deepseek-chat / Qwen3-VL-4B-Instruct)
    - **temperature**: 温度系数
    """
    return await AIManager.chat_completion(request)

@router.post("/chat/completions/stream", summary="DeepSeek 对话 (流式)")
async def chat_completions_stream(
    request: ChatRequest,
    current_user = Depends(get_current_active_user)
):
    """
    调用 DeepSeek API 进行对话 (流式 SSE)
    - **messages**: 消息历史
    - **model**: 模型 (默认 deepseek-chat)
    - **temperature**: 温度系数
    """
    messages = [msg.model_dump() for msg in request.messages]
    
    async def event_generator():
        full_response = []
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
        
        # TODO: 将完整对话记录存入数据库 (流式持久化)
        complete_text = "".join(full_response)
        # logger.info(f"流式对话结束，完整内容长度: {len(complete_text)}")
        # await save_chat_log(current_user, request, complete_text)

    return StreamingResponse(event_generator(), media_type="text/event-stream")