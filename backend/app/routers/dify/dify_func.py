#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/dify/dify_func.py
# 作者：whf
# 日期：2026-01-28
# 描述：Dify 业务逻辑封装

from typing import Dict, Any, AsyncGenerator, Optional, List
from fastapi import HTTPException
from pydantic import BaseModel
from backend.app.utils.dify_utils import DifyApp
from backend.app.utils.logger import logger

class DifyChatRequest(BaseModel):
    query: str
    user: str
    conversation_id: Optional[str] = None
    inputs: Dict[str, Any] = {}
    files: Optional[List[Dict[str, Any]]] = None
    app_name: str = "guanwang" # 默认使用官网助手
    api_key: Optional[str] = None # 显式传入 Key
    mode: str = "chat" # chat (聊天助手) / workflow (工作流) / completion (文本补全)

class DifyFunc:
    """
    Dify 业务逻辑
    """
    
    @staticmethod
    async def chat_message(request: DifyChatRequest):
        """
        发送对话消息 (流式)
        """
        try:
            return await DifyApp.chat_messages(
                query=request.query,
                user=request.user,
                conversation_id=request.conversation_id,
                inputs=request.inputs,
                files=request.files,
                app_name=request.app_name,
                api_key=request.api_key,
                mode=request.mode,
                response_mode="streaming"
            )
        except Exception as e:
            logger.error(f"Dify 对话失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
            
    @staticmethod
    async def get_conversations(user: str, limit: int = 20, app_name: str = "guanwang"):
        """
        获取会话列表
        """
        try:
            return await DifyApp.get_conversations(user=user, limit=limit, app_name=app_name)
        except Exception as e:
            logger.error(f"获取 Dify 会话列表失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
