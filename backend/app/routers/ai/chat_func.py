#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/chat_func.py
# 作者：whf
# 日期：2026-01-27
# 描述：AI 模块业务逻辑 (DeepSeek API)

import httpx
import os
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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
    role: str = Field(..., description="角色 (user/assistant/system)")
    content: str = Field(..., description="消息内容")

class ChatRequest(BaseModel):
    """
    AI 对话请求模型
    """
    messages: List[Message] = Field(..., description="历史消息列表")
    model: str = Field("deepseek-chat", description="模型名称 (deepseek-chat/Qwen3-VL-4B-Instruct)")
    temperature: float = Field(0.7, description="温度系数 (0-2)")
    max_tokens: int = Field(512, description="最大 Token 数")

class ChatResponse(BaseModel):
    """
    AI 对话响应模型
    """
    reply: str = Field(..., description="AI 回复内容")
    model: str = Field(..., description="使用的模型")
    usage: Dict[str, Any] = Field({}, description="Token 使用统计")

class AIManager:
    """
    AI 模块业务逻辑管理器
    """
    
    @staticmethod
    async def chat_completion(request: ChatRequest) -> ChatResponse:
        """
        统一对话入口 (支持 DeepSeek API 和 本地 ModelScope 模型)
        """
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
                
                return ChatResponse(
                    reply=reply,
                    model=request.model,
                    usage={"local_inference": True} # 本地推理暂无精确 token 统计
                )
            except Exception as e:
                logger.error(f"本地模型推理失败: {e}")
                raise ValueError(f"Local model inference failed: {e}")

        # 2. 否则走 DeepSeek API (默认)
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
                
                if response.status_code != 200:
                    error_msg = f"API Error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
                data = response.json()
                
                # 解析响应
                reply_content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                
                logger.info(f"DeepSeek 响应成功: usage={usage}")
                
                return ChatResponse(
                    reply=reply_content,
                    model=data["model"],
                    usage=usage
                )
        except Exception as e:
            logger.error(f"DeepSeek API 请求失败: {e}")
            raise e
                
        except Exception as e:
            logger.error(f"DeepSeek API 调用失败: {e}")
            raise e