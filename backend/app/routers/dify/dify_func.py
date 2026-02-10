#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/dify/dify_func.py
# 作者：whf
# 日期：2026-01-28
# 描述：Dify 业务逻辑封装

from typing import Dict, Any, AsyncGenerator, Optional, List
from fastapi import HTTPException
from pydantic import BaseModel, Field
from backend.app.utils.dify_utils import DifyApp
from backend.app.utils.logger import logger

class DifyChatRequest(BaseModel):
    query: str = Field(..., description="用户输入", examples=["你好，请介绍一下自己"])
    user: str = Field(..., description="用户标识", examples=["user-123"])
    conversation_id: Optional[str] = Field(None, description="会话ID", examples=["uuid-string"])
    inputs: Dict[str, Any] = Field({}, description="变量输入", examples=[{"key": "value"}])
    files: Optional[List[Dict[str, Any]]] = Field(None, description="上传文件", examples=[])
    app_name: str = Field("guanwang", description="应用名称", examples=["guanwang"])
    api_key: Optional[str] = Field(None, description="API Key (可选)", examples=["app-xxx"])
    mode: str = Field("chat", description="模式 (chat/workflow/completion)", examples=["chat"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Hello",
                "user": "test-user",
                "inputs": {},
                "app_name": "guanwang",
                "mode": "chat"
            }
        }
    }

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
    async def get_conversations(user: str, last_id: Optional[str] = None, limit: int = 20, app_name: str = "guanwang", api_key: Optional[str] = None):
        """
        获取会话列表
        """
        try:
            return await DifyApp.get_conversations(user=user, last_id=last_id, limit=limit, app_name=app_name, api_key=api_key)
        except Exception as e:
            logger.error(f"获取 Dify 会话列表失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_conversation_messages(conversation_id: str, user: str, first_id: Optional[str] = None, limit: int = 20, app_name: str = "guanwang", api_key: Optional[str] = None):
        """
        获取会话历史消息
        """
        try:
            return await DifyApp.get_conversation_messages(conversation_id=conversation_id, user=user, first_id=first_id, limit=limit, app_name=app_name, api_key=api_key)
        except Exception as e:
            logger.error(f"获取 Dify 会话消息失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def rename_conversation(conversation_id: str, user: str, name: Optional[str] = None, auto_generate: bool = False, app_name: str = "guanwang", api_key: Optional[str] = None):
        """
        会话重命名
        """
        try:
            return await DifyApp.rename_conversation(conversation_id=conversation_id, user=user, name=name, auto_generate=auto_generate, app_name=app_name, api_key=api_key)
        except Exception as e:
            logger.error(f"Dify 会话重命名失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def delete_conversation(conversation_id: str, user: str, app_name: str = "guanwang", api_key: Optional[str] = None):
        """
        删除会话
        """
        try:
            return await DifyApp.delete_conversation(conversation_id=conversation_id, user=user, app_name=app_name, api_key=api_key)
        except Exception as e:
            logger.error(f"删除 Dify 会话失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
