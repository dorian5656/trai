#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/chat_func.py
# 作者：whf
# 日期：2026-01-27
# 描述：AI 模块业务逻辑 (DeepSeek API)

import httpx
import os
import uuid
import json
from sqlalchemy import text
from backend.app.utils.pg_utils import PGUtils
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.modelscope_utils import ModelScopeUtils

# =============================================================================
# Schema 定义 (AI)
# =============================================================================

class Message(BaseModel):
    """
    对话消息模型
    """
    role: str = Field(..., description="角色 (user/assistant/system)", examples=["user"])
    content: Union[str, List[Dict[str, Any]]] = Field(..., description="消息内容 (文本或多模态列表)", examples=["Hello, how are you?"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "role": "user",
                "content": "Hello, how are you?"
            }
        }
    }

class ChatRequest(BaseModel):
    """
    AI 对话请求模型
    """
    messages: List[Message] = Field(..., description="历史消息列表")
    model: str = Field("deepseek-chat", description="模型名称 (deepseek-chat/Qwen3-VL-4B-Instruct)", examples=["deepseek-chat"])
    temperature: float = Field(0.7, description="温度系数 (0-2)", examples=[0.7])
    max_tokens: int = Field(512, description="最大 Token 数", examples=[512])
    session_id: Optional[str] = Field(None, description="会话ID (若不传则自动生成)", examples=["uuid-v4-string"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Tell me a joke."}
                ],
                "model": "deepseek-chat",
                "temperature": 0.7,
                "max_tokens": 512
            }
        }
    }

class ChatResponse(BaseModel):
    """
    AI 对话响应模型
    """
    reply: str = Field(..., description="AI 回复内容")
    model: str = Field(..., description="使用的模型")
    usage: Dict[str, Any] = Field({}, description="Token 使用统计")
    session_id: Optional[str] = Field(None, description="会话ID")

class AIManager:
    """
    AI 模块业务逻辑管理器
    """
    
    @staticmethod
    async def save_message(session_id: str, user_id: str, role: str, content: Union[str, List[Dict[str, Any]]], model: str = None):
        """保存对话消息到数据库"""
        try:
            # 如果 content 是列表 (多模态)，序列化为 JSON 字符串
            if isinstance(content, list):
                content_str = json.dumps(content, ensure_ascii=False)
            else:
                content_str = str(content)

            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                await conn.execute(
                    text("""
                        INSERT INTO chat_messages (session_id, user_id, role, content, model)
                        VALUES (:session_id, :user_id, :role, :content, :model)
                    """),
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "role": role,
                        "content": content_str,
                        "model": model
                    }
                )
        except Exception as e:
            logger.error(f"❌ 保存对话消息失败: {e}")

    @staticmethod
    async def chat_completion(request: ChatRequest, user_id: str = "anonymous") -> ChatResponse:
        """
        统一对话入口 (支持 DeepSeek API 和 本地 ModelScope 模型)
        """
        session_id = request.session_id or str(uuid.uuid4())
        
        # 记录用户消息 (只记录最后一条 user 消息)
        if request.messages and request.messages[-1].role == 'user':
            await AIManager.save_message(session_id, user_id, 'user', request.messages[-1].content, request.model)

        reply = ""
        usage = {}

        # 1. 检查是否为本地 ModelScope 模型
        if ModelScopeUtils.check_model_exists(request.model):
            try:
                logger.info(f"路由到本地 ModelScope 模型: {request.model}")
                # 转换消息格式
                messages = [msg.model_dump() for msg in request.messages]
                
                reply = await ModelScopeUtils.chat_completion(
                    messages=messages,
                    model_name=request.model,
                    max_new_tokens=request.max_tokens or 512
                )
                usage = {"local_inference": True}
                
            except Exception as e:
                logger.error(f"本地模型推理失败: {e}")
                raise ValueError(f"Local model inference failed: {e}")

        # 2. 否则走 DeepSeek API (默认)
        else:
            if not settings.DEEPSEEK_API_KEY:
                raise ValueError("DeepSeek API Key not configured")
                
            url = f"{settings.DEEPSEEK_API_BASE}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"
            }
            
            payload = {
                "model": request.model,
                "messages": [msg.model_dump() for msg in request.messages],
                "temperature": request.temperature,
                "stream": False
            }
            
            if request.max_tokens:
                payload["max_tokens"] = request.max_tokens
                
            try:
                # 使用 trust_env=False 忽略系统代理设置，防止 500 错误
                async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                    logger.info(f"发送 DeepSeek 请求: model={request.model}, msg_count={len(request.messages)}")
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    reply = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    logger.info(f"DeepSeek 响应成功: usage={usage}")
                    
            except Exception as e:
                logger.error(f"DeepSeek API 请求失败: {e}")
                raise ValueError(f"DeepSeek API failed: {e}")

        # 记录 AI 回复
        await AIManager.save_message(session_id, user_id, 'assistant', reply, request.model)

        return ChatResponse(
            reply=reply,
            model=request.model,
            usage=usage,
            session_id=session_id
        )
