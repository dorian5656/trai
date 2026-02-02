#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/ai_utils.py
# 作者：whf
# 日期：2026-01-27
# 描述：AI 工具箱 (统一管理 AI 调用)

import httpx
import json
from typing import List, Dict, Any, AsyncGenerator, Optional
from backend.app.config import settings
from backend.app.utils.logger import logger

class AIUtils:
    """
    AI 工具箱，封装所有 AI 模型调用逻辑
    """

    @staticmethod
    def scan_local_models() -> List[str]:
        """
        扫描 backend/app/models 目录下的本地模型
        返回模型名称列表 (相对路径)
        """
        from pathlib import Path
        import os
        
        models_dir = Path(__file__).parent.parent / "models"
        if not models_dir.exists():
            return []
            
        found_models = []
        # 遍历所有子目录
        for root, dirs, files in os.walk(models_dir):
            # 1. 检查 Transformer/Diffuser 模型 (目录即模型)
            if "model_index.json" in files or "config.json" in files:
                # 排除根目录
                if Path(root) == models_dir:
                    continue
                
                # 获取相对路径作为模型名称
                rel_path = Path(root).relative_to(models_dir)
                # 转换为字符串并统一分隔符
                model_name = str(rel_path).replace("\\", "/")
                found_models.append(model_name)
                
                # 已找到模型，不再遍历其子目录 (简单剪枝)
                # dirs.clear() # 暂不清除，允许嵌套
                continue

            # 2. 检查单文件模型 (如 YOLO .pt, ONNX .onnx)
            for file in files:
                if file.lower().endswith((".pt", ".pth", ".onnx", ".bin")):
                    # 排除 model_index.json 同级的一些权重文件 (避免重复)
                    # 但由于上面有 continue，这里执行到的通常是不含 config.json 的目录
                    
                    rel_path = Path(root) / file
                    rel_path_from_models = rel_path.relative_to(models_dir)
                    model_name = str(rel_path_from_models).replace("\\", "/")
                    found_models.append(model_name)
                
        return sorted(found_models)

    @staticmethod
    async def chat_completion(
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        AI 对话 (非流式)
        """
        return await AIUtils._request_deepseek(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )

    @staticmethod
    async def chat_completion_stream(
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        AI 对话 (流式)
        """
        async for chunk in AIUtils._request_deepseek_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            yield chunk

    @staticmethod
    async def _request_deepseek(
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        stream: bool
    ) -> Any:
        """
        调用 DeepSeek API (核心逻辑)
        """
        if not settings.AI_API_KEY:
            raise ValueError("AI_API_KEY 未配置")

        url = f"{settings.DEEPSEEK_API_BASE}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.AI_API_KEY}"
        }
        
        # 修正: DeepSeek API 可能不接受 stream 参数为 False，如果非流式直接不传 stream 参数或设为 False (视具体 API 而定)
        # 经查，通常设为 False 没问题，但为了稳妥，如果 stream=False 则不传
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        if stream:
            payload["stream"] = True
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
            
        try:
            # trust_env=False 忽略系统代理
            async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
                logger.info(f"发送 DeepSeek 请求: model={model}, stream={stream}")
                
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code != 200:
                    error_msg = f"API Error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                # logger.info(f"Response Text: {response.text}")
                return response.json()
                
        except Exception as e:
            logger.error(f"DeepSeek API 调用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise e

    @staticmethod
    async def _request_deepseek_stream(
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: Optional[int]
    ) -> AsyncGenerator[str, None]:
        """
        调用 DeepSeek API (流式核心逻辑)
        """
        if not settings.AI_API_KEY:
            raise ValueError("AI_API_KEY 未配置")

        url = f"{settings.DEEPSEEK_API_BASE}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.AI_API_KEY}"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
            
        try:
            async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
                logger.info(f"发送 DeepSeek 流式请求: model={model}")
                
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_content = await response.aread()
                        error_msg = f"API Error {response.status_code}: {error_content.decode()}"
                        logger.error(error_msg)
                        raise Exception(error_msg)
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                json_data = json.loads(data)
                                
                                # 调试日志
                                logger.debug(f"Stream Chunk: {json_data}")
                                
                                choices = json_data.get("choices", [])
                                if not choices:
                                    continue
                                    
                                delta = choices[0].get("delta", {})
                                
                                # 支持 reasoning_content (DeepSeek R1)
                                reasoning_content = delta.get("reasoning_content", "")
                                if reasoning_content:
                                    yield reasoning_content
                                
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            logger.error(f"DeepSeek API 流式调用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise e
