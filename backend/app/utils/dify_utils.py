#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/dify_utils.py
# 作者：whf
# 日期：2026-01-28
# 描述：Dify AI 平台工具类

import httpx
import json
from typing import Dict, Any, AsyncGenerator, Optional, List, Union
from backend.app.config import settings
from backend.app.utils.logger import logger

class DifyApp:
    """
    Dify 应用 API 封装
    """
    
    @staticmethod
    def _get_headers(app_name: str = "guanwang", api_key: Optional[str] = None) -> Dict[str, str]:
        """
        获取请求头
        """
        if not api_key:
            # 从配置中获取对应 App 的 Key
            api_key = settings.DIFY_APPS.get(app_name, "")
            if not api_key:
                # 尝试回退到默认 Key (兼容旧逻辑)
                api_key = settings.DIFY_API_KEY
                if not api_key:
                    logger.warning(f"未找到应用 '{app_name}' 的 API Key 配置")
                
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def _get_base_url() -> str:
        """
        获取基础 URL (去除末尾斜杠)
        """
        # 注意：根据用户提供的文档，API Base URL 应该是 http://192.168.100.119/v1，不带端口 8098
        # 如果 settings 中配置了 8098，可能需要修正，或者优先使用 settings 配置
        return settings.DIFY_API_BASE_URL.rstrip("/")

    @staticmethod
    async def chat_messages(
        query: str,
        user: str,
        inputs: Dict[str, Any] = {},
        response_mode: str = "streaming",
        conversation_id: Optional[str] = None,
        files: Optional[List[Dict[str, Any]]] = None,
        timeout: int = 100,
        app_name: str = "guanwang",
        api_key: Optional[str] = None,
        mode: str = "chat"
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        发送对话消息
        
        :param query: 用户输入/提问内容
        :param user: 用户标识，用于定义终端用户的身份
        :param inputs: 允许传入 App 定义的各变量值
        :param response_mode: streaming (流式) 或 blocking (阻塞)
        :param conversation_id: 会话 ID
        :param files: 上传的文件列表
        :param timeout: 超时时间 (秒)
        :param app_name: 应用名称 (用于获取对应的 API Key)
        :param api_key: 显式指定 API Key (覆盖 app_name 配置)
        :param mode: 接口模式 (chat: /chat-messages, workflow: /workflows/run, completion: /completion-messages)
        :return: 阻塞模式返回 Dict, 流式模式返回 AsyncGenerator
        """
        if mode == "workflow":
            url = f"{DifyApp._get_base_url()}/workflows/run"
        elif mode == "completion":
            url = f"{DifyApp._get_base_url()}/completion-messages"
        else:
            url = f"{DifyApp._get_base_url()}/chat-messages"
        
        payload = {
            "query": query,
            "inputs": inputs,
            "response_mode": response_mode,
            "user": user,
            "auto_generate_name": True
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
            
        if files:
            payload["files"] = files

        headers = DifyApp._get_headers(app_name, api_key)
        
        try:
            if response_mode == "blocking":
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    return response.json()
            
            elif response_mode == "streaming":
                return DifyApp._stream_generator(url, payload, headers, timeout)
            
            else:
                raise ValueError(f"不支持的 response_mode: {response_mode}")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Dify API 请求失败: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Dify API 调用异常: {e}")
            raise

    @staticmethod
    async def _stream_generator(url: str, payload: Dict, headers: Dict, timeout: int) -> AsyncGenerator[str, None]:
        """
        流式响应生成器
        """
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield line

    @staticmethod
    async def get_conversations(
        user: str,
        last_id: Optional[str] = None,
        limit: int = 20,
        sort_by: str = "-updated_at",
        app_name: str = "guanwang"
    ) -> Dict[str, Any]:
        """
        获取会话列表
        """
        url = f"{DifyApp._get_base_url()}/conversations"
        params = {
            "user": user,
            "limit": limit,
            "sort_by": sort_by
        }
        if last_id:
            params["last_id"] = last_id
            
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=DifyApp._get_headers(app_name))
            response.raise_for_status()
            return response.json()
