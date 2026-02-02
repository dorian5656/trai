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
import json
from io import BytesIO
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.modelscope_utils import ModelScopeUtils
from backend.app.utils.upload_utils import UploadUtils
from backend.app.routers.upload.upload_func import UserImage
from backend.app.utils.pg_utils import PGUtils
from sqlalchemy import text

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
    model: str = Field("Qwen/Qwen3-VL-4B-Instruct", description="模型名称")
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
            messages = [msg.model_dump() for msg in request.messages]
            
            # 处理模型名称
            model_name = request.model
            if model_name == "Qwen3-VL-4B-Instruct":
                model_name = "Qwen/Qwen3-VL-4B-Instruct"
            elif model_name == "Qwen3-VL-8B-Instruct":
                model_name = "Qwen/Qwen3-VL-8B-Instruct"

            reply = await ModelScopeUtils.chat_completion(
                messages=messages,
                model_name=model_name,
                max_new_tokens=request.max_tokens
            )
            
            return ImageChatResponse(
                reply=reply,
                model=model_name,
                usage={"prompt_tokens": 0, "completion_tokens": 0}
            )
            
        except Exception as e:
            logger.error(f"多模态对话失败: {e}")
            raise ValueError(f"Multimodal chat failed: {e}")

    @staticmethod
    async def generate_image(request: ImageGenRequest, user_id: str = "anonymous") -> ImageGenResponse:
        """
        文生图 (FLUX / Z-Image 等)
        """
        # 如果请求指定 Z-Image 模型，走本地调用
        if "Z-Image" in request.model or "Tongyi-MAI" in request.model:
             return await ImageManager._generate_z_image_local(request, user_id)

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
                
                # 记录到 user_images 表
                try:
                    engine = PGUtils.get_engine()
                    async with engine.begin() as conn:
                        for item in data.get("data", []):
                            img_url = item.get("url")
                            if img_url:
                                await conn.execute(
                                    text("""
                                        INSERT INTO user_images (user_id, filename, s3_key, url, module, source, prompt, meta_data)
                                        VALUES (:user_id, :filename, :s3_key, :url, :module, :source, :prompt, :meta_data)
                                    """),
                                    {
                                        "user_id": user_id,
                                        "filename": f"dify_gen_{int(time.time())}_{uuid.uuid4().hex[:8]}.png",
                                        "s3_key": img_url, # 远程URL作为key
                                        "url": img_url,
                                        "module": "gen",
                                        "source": "generated",
                                        "prompt": request.prompt,
                                        "meta_data": json.dumps({"model": request.model, "provider": "dify"})
                                    }
                                )
                except Exception as e:
                    logger.error(f"Failed to save generated image to DB: {e}")

                return ImageGenResponse(
                    created=data.get("created", 0),
                    data=data.get("data", [])
                )
        except Exception as e:
            logger.error(f"文生图异常: {str(e)}")
            raise e

    @staticmethod
    async def _generate_z_image_local(request: ImageGenRequest, user_id: str = "anonymous") -> ImageGenResponse:
        """
        本地运行 Z-Image 模型 (异步包装)
        """
        import asyncio
        loop = asyncio.get_running_loop()
        # 在线程池中运行阻塞的 GPU 推理代码
        images_bytes = await loop.run_in_executor(None, ImageManager._run_z_image_sync, request)
        
        images_data = []
        for img_bytes in images_bytes:
            filename = f"z_image_{uuid.uuid4()}.png"
            
            # 判断是否启用 S3 (通过 settings 或 UploadUtils 内部逻辑)
            # UploadUtils.save_from_bytes 内部已经处理了 S3_ENABLED 的判断逻辑
            # 但我们需要确保返回的是完整 URL 给前端
            
            url, object_key, size = await UploadUtils.save_from_bytes(
                data=img_bytes, 
                filename=filename, 
                module="gen", 
                content_type="image/png"
            )
            
            # 如果是本地存储，UploadUtils 返回的是相对路径 (e.g., /static/uploads/...)
            # 如果是 S3，返回的是完整 URL (e.g., http://minio... or https://oss...)
            # 前端通常需要完整 URL，或者拼接 BaseURL
            
            # 这里的 url 字段，如果是 S3 则是完整链接；如果是本地则是相对路径
            # 为了方便前端，我们可以尝试拼接本地 URL 的 host
            
            final_url = url
            
            # 记录到 user_images 表
            try:
                engine = PGUtils.get_engine()
                async with engine.begin() as conn:
                     await conn.execute(
                        text("""
                            INSERT INTO user_images (user_id, filename, s3_key, url, size, mime_type, module, source, prompt, meta_data)
                            VALUES (:user_id, :filename, :s3_key, :url, :size, :mime_type, :module, :source, :prompt, :meta_data)
                        """),
                        {
                            "user_id": user_id,
                            "filename": filename,
                            "s3_key": object_key,
                            "url": final_url,
                            "size": size,
                            "mime_type": "image/png",
                            "module": "gen",
                            "source": "generated",
                            "prompt": request.prompt,
                            "meta_data": json.dumps({"model": request.model, "provider": "z-image"})
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to save generated Z-Image to DB: {e}")

            if not url.startswith("http"):
                 # 本地相对路径，尝试拼接 (虽然后端无法确切知道前端访问的 Host，但可以尽量提供完整路径)
                 # 或者保持相对路径，由前端拼接。
                 # 用户要求 "记得返回有 S3 地址"，意味着如果配置了 S3，必须是 S3 地址。
                 # UploadUtils.save_from_bytes 已经做到了这一点。
                 pass

            images_data.append({"url": final_url})
            logger.info(f"Generated image: {object_key} (URL: {final_url})")
            
        return ImageGenResponse(
            created=int(time.time()),
            data=images_data
        )

    @staticmethod
    def _run_z_image_sync(request: ImageGenRequest) -> List[bytes]:
        """
        Z-Image 同步推理逻辑 (返回图片字节列表)
        """
        global _z_image_pipeline
        import torch
        from diffusers import DiffusionPipeline

        # 1. 确定模型路径
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        
        # 自动下载/检查模型
        try:
            from modelscope.hub.snapshot_download import snapshot_download
            logger.info(f"Checking/Downloading Z-Image-Turbo model...")
            # snapshot_download 会自动处理断点续传和缓存
            model_path = snapshot_download("Tongyi-MAI/Z-Image-Turbo", cache_dir=str(base_dir / "app/models"))
            logger.success(f"✅ Z-Image-Turbo model ready at {model_path}")
        except Exception as e:
            logger.error(f"❌ Z-Image-Turbo 模型下载/检查失败: {e}")
            raise e

        # 2. 加载模型 (单例缓存)
        if _z_image_pipeline is None:
             logger.info(f"Loading Z-Image model from {model_path}...")
             try:
                 dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
                 _z_image_pipeline = DiffusionPipeline.from_pretrained(
                     str(model_path),
                     torch_dtype=dtype,
                     low_cpu_mem_usage=False
                 )
                 if torch.cuda.is_available():
                     # 自动选择显存最大的 GPU
                     device = "cuda"
                     try:
                         device_count = torch.cuda.device_count()
                         max_free_memory = 0
                         best_gpu_id = 0
                         for i in range(device_count):
                             free_mem = torch.cuda.mem_get_info(i)[0]
                             if free_mem > max_free_memory:
                                 max_free_memory = free_mem
                                 best_gpu_id = i
                         device = f"cuda:{best_gpu_id}"
                         logger.info(f"Z-Image using GPU {best_gpu_id} (Free: {max_free_memory / 1024**3:.2f} GB)")
                     except Exception as e:
                         logger.warning(f"Failed to auto-select GPU, using default cuda: {e}")
                     
                     _z_image_pipeline.to(device)
                 logger.success("Z-Image model loaded successfully.")
             except Exception as e:
                 logger.error(f"Failed to load Z-Image model: {e}")
                 raise e

        # 3. 生成图片
        generated_images_bytes = []
        
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
            
            # 将 PIL Image 保存到内存
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='PNG')
            generated_images_bytes.append(img_byte_arr.getvalue())
            
        return generated_images_bytes
