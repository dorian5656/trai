#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/image_func.py
# 作者：liuhd
# 日期：2026-01-28
# 描述：AI 图像处理与多模态业务逻辑

import httpx
import os
import time
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.modelscope_utils import ModelScopeUtils

# 全局缓存模型 pipeline
_z_image_pipeline = None


# =============================================================================
# Schema 定义 (Image/Multimodal)
# =============================================================================

class ImageContent(BaseModel):
    """
    多模态消息内容
    """
    type: str = Field(..., description="类型 (text/image)")
    text: Optional[str] = Field(None, description="文本内容")
    image: Optional[str] = Field(None, description="图片链接或Base64") # 改名 image 以匹配 Qwen 格式

class MultimodalMessage(BaseModel):
    """
    多模态对话消息
    """
    role: str = Field(..., description="角色 (user/assistant/system)")
    content: List[Dict[str, Any]] = Field(..., description="消息内容 (支持纯文本或多模态列表)")

class ImageChatRequest(BaseModel):
    """
    AI 图像对话请求 (Qwen-VL 等)
    """
    messages: List[MultimodalMessage] = Field(..., description="历史消息列表")
    model: str = Field("Qwen3-VL-4B-Instruct", description="模型名称")
    temperature: float = Field(0.7, description="温度系数")
    max_tokens: int = Field(512, description="最大生成 Token 数")

class ImageChatResponse(BaseModel):
    """
    AI 图像对话响应
    """
    reply: str = Field(..., description="AI 回复内容")
    model: str = Field(..., description="使用的模型")
    usage: Dict[str, Any] = Field({}, description="Token 使用统计")

class ImageGenRequest(BaseModel):
    """
    文生图请求
    """
    prompt: str = Field(..., description="提示词")
    model: str = Field("FLUX.2-dev", description="模型名称")
    size: str = Field("1024x1024", description="图片尺寸")
    n: int = Field(1, description="生成数量")

class ImageGenResponse(BaseModel):
    """
    文生图响应
    """
    created: int = Field(..., description="创建时间戳")
    data: List[Dict[str, str]] = Field(..., description="图片数据列表 [{'url': '...'}, ...]")

# =============================================================================
# Manager 实现
# =============================================================================

class ImageManager:
    """
    AI 图像/多模态业务管理器
    """
    
    @staticmethod
    async def chat_with_image(request: ImageChatRequest) -> ImageChatResponse:
        """
        多模态对话 (Qwen-VL) - 本地推理
        """
        try:
            # 转换消息格式 (如果需要适配前端格式到 Qwen 格式)
            # 假设前端传来的格式已经是:
            # content: [
            #    {"type": "image", "image": "http://..."},
            #    {"type": "text", "text": "描述图片"}
            # ]
            # 这与 QwenVLUtils 期望的格式一致，直接透传
            
            messages = [msg.model_dump() for msg in request.messages]
            
            # 添加系统提示要求中文回复 (如果用户没有明确指定语言)
            # 或者在最后一条消息中追加提示
            # 简单起见，我们假设用户会在 prompt 里问，或者我们默认追加
            # 这里不强制修改 prompt，以免影响用户意图
            
            reply = await ModelScopeUtils.chat_completion(
                messages=messages,
                model_name="Qwen3-VL-4B-Instruct",
                max_new_tokens=request.max_tokens
            )
            
            return ImageChatResponse(
                reply=reply,
                model="Qwen3-VL-4B-Instruct",
                usage={"prompt_tokens": 0, "completion_tokens": 0} # 暂无法精确统计
            )
            
        except Exception as e:
            logger.error(f"多模态对话失败: {e}")
            raise ValueError(f"Multimodal chat failed: {e}")

    @staticmethod
    async def generate_image(request: ImageGenRequest) -> ImageGenResponse:
        # ... (保持原有的文生图逻辑或待实现)
        return ImageGenResponse(created=int(time.time()), data=[])
        api_key = settings.AI_API_KEY or "sk-xxx"

        # 适配本地模型服务 (通常不带 /v1)
        # 如果配置中有 /v1 但我们需要去掉它 (根据测试结果)
        # 简单处理：如果 api_base 包含 /v1，先尝试去掉它
        
        base_url = api_base
        if "/v1" in base_url:
            base_url = base_url.replace("/v1", "")
        if base_url.endswith("/"):
            base_url = base_url[:-1]
            
        url = f"{base_url}/chat/completions"

        logger.info(f"正在调用多模态模型: {request.model}, URL: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=100.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"模型调用失败: {response.text}")
                    raise Exception(f"Model API Error: {response.status_code} - {response.text}")
                
                try:
                    data = response.json()
                except Exception:
                    logger.error(f"响应解析失败: {response.text[:200]}")
                    raise Exception(f"Invalid JSON response: {response.text[:200]}")
                
                return ImageChatResponse(
                    reply=data["choices"][0]["message"]["content"],
                    model=data["model"],
                    usage=data.get("usage", {})
                )
        except Exception as e:
            logger.error(f"多模态对话异常: {str(e)}")
            raise e

    @staticmethod
    async def generate_image(request: ImageGenRequest) -> ImageGenResponse:
        """
        文生图 (FLUX / Z-Image 等)
        """
        # 如果请求指定 Z-Image 模型，走本地调用
        if "Z-Image" in request.model or "Tongyi-MAI" in request.model:
             return await ImageManager._generate_z_image_local(request)

        # 构造请求体
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "size": request.size,
            "n": request.n
        }
        
        api_base = settings.DIFY_API_BASE_URL
        api_key = settings.AI_API_KEY
        
        url = f"{api_base}/images/generations"
        # 类似 chat，尝试适配路径
        base_url = api_base
        if "/v1" in base_url:
            base_url = base_url.replace("/v1", "")
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        
        url = f"{base_url}/images/generations"

        logger.info(f"正在调用文生图模型: {request.model}, URL: {url}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"生图失败: {response.text}")
                    raise Exception(f"Image Gen API Error: {response.status_code} - {response.text}")
                
                try:
                    data = response.json()
                except Exception:
                    logger.error(f"响应解析失败: {response.text[:200]}")
                    raise Exception(f"Invalid JSON response: {response.text[:200]}")
                
                return ImageGenResponse(
                    created=data.get("created", 0),
                    data=data.get("data", [])
                )
        except Exception as e:
            logger.error(f"文生图异常: {str(e)}")
            raise e

    @staticmethod
    async def _generate_z_image_local(request: ImageGenRequest) -> ImageGenResponse:
        """
        本地运行 Z-Image 模型 (异步包装)
        """
        import asyncio
        loop = asyncio.get_running_loop()
        # 在线程池中运行阻塞的 GPU 推理代码
        return await loop.run_in_executor(None, ImageManager._run_z_image_sync, request)

    @staticmethod
    def _run_z_image_sync(request: ImageGenRequest) -> ImageGenResponse:
        """
        Z-Image 同步推理逻辑
        """
        global _z_image_pipeline
        import torch
        from diffusers import ZImagePipeline

        # 1. 确定模型路径
        # backend/app/routers/ai/image_func.py -> backend
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        model_path = base_dir / "app/models/Tongyi-MAI"
        
        if not model_path.exists():
            raise Exception(f"Model path not found: {model_path}")

        # 2. 加载模型 (单例缓存)
        if _z_image_pipeline is None:
             logger.info(f"Loading Z-Image model from {model_path}...")
             try:
                 dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
                 _z_image_pipeline = ZImagePipeline.from_pretrained(
                     str(model_path),
                     torch_dtype=dtype,
                     low_cpu_mem_usage=False
                 )
                 if torch.cuda.is_available():
                     _z_image_pipeline.to("cuda")
                 logger.success("Z-Image model loaded successfully.")
             except Exception as e:
                 logger.error(f"Failed to load Z-Image model: {e}")
                 raise e

        # 3. 生成图片
        images_data = []
        static_dir = base_dir / "static/gen"
        static_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Start generating {request.n} images with prompt: {request.prompt[:50]}...")
        
        for i in range(request.n):
            # 解析尺寸 (默认 1024x1024)
            width, height = 1024, 1024
            if "x" in request.size:
                try:
                    w, h = request.size.split("x")
                    width, height = int(w), int(h)
                except:
                    pass

            image = _z_image_pipeline(
                prompt=request.prompt,
                height=height,
                width=width,
                num_inference_steps=9,  # Turbo model recommended steps
                guidance_scale=0.0,     # Turbo model recommended guidance
                generator=torch.Generator("cuda" if torch.cuda.is_available() else "cpu").manual_seed(int(time.time() * 1000) % 2**32),
            ).images[0]
            
            # 4. 保存文件
            filename = f"z_image_{uuid.uuid4()}.png"
            file_path = static_dir / filename
            image.save(file_path)
            
            # 构造访问 URL
            # 假设前端可以通过 /static 访问
            url = f"/static/gen/{filename}"
            images_data.append({"url": url})
            
            logger.info(f"Generated image: {file_path}")

        return ImageGenResponse(
            created=int(time.time()),
            data=images_data
        )

