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
from backend.app.routers.ai.chat_func import AIManager

# 全局缓存模型 pipeline
_z_image_pipeline = None
_sdxl_base_pipeline = None
_sdxl_refiner_pipeline = None


# =============================================================================
# Schema 定义 (Image/Multimodal)
# =============================================================================

class ImageContent(BaseModel):
    """
    多模态消息内容
    """
    type: str = Field(..., description="内容类型: 'text' (文本) 或 'image' (图片)", examples=["text", "image"])
    text: Optional[str] = Field(None, description="当 type='text' 时必填，表示文本内容", examples=["Describe this image."])
    image: Optional[str] = Field(None, description="当 type='image' 时必填，支持 URL (http/file) 或 Base64 (data:image/...)", examples=["https://example.com/image.jpg"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "type": "text",
                "text": "What is in this picture?",
                "image": None
            }
        }
    }

class MultimodalMessage(BaseModel):
    """
    多模态对话消息
    """
    role: str = Field(..., description="角色 (user/assistant/system)", examples=["user"])
    content: List[ImageContent] = Field(..., description="消息内容 (支持纯文本或多模态列表)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "role": "user",
                "content": [
                    {"type": "image", "image": "https://example.com/cat.jpg"},
                    {"type": "text", "text": "What animal is this?"}
                ]
            }
        }
    }

class ImageChatRequest(BaseModel):
    """
    AI 图像对话请求 (Qwen-VL 等)
    """
    messages: List[MultimodalMessage] = Field(..., description="历史消息列表")
    model: str = Field("Qwen/Qwen3-VL-4B-Instruct", description="模型名称", examples=["Qwen/Qwen3-VL-4B-Instruct"])
    temperature: float = Field(0.7, description="温度系数", examples=[0.7])
    max_tokens: int = Field(512, description="最大生成 Token 数", examples=[512])
    session_id: Optional[str] = Field(None, description="会话ID (若不传则自动生成)", examples=["uuid-v4-string"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": "https://example.com/demo.jpg"},
                            {"type": "text", "text": "Describe this image."}
                        ]
                    }
                ],
                "model": "Qwen/Qwen3-VL-4B-Instruct",
                "temperature": 0.7,
                "max_tokens": 512
            }
        }
    }

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
    prompt: str = Field(..., description="提示词", examples=["A futuristic city skyline at sunset"])
    model: str = Field("Z-Image-Turbo", description="模型名称", examples=["Z-Image-Turbo"])
    size: str = Field("1024x1024", description="图片尺寸", examples=["1024x1024"])
    n: int = Field(1, description="生成数量", examples=[1])
    # SDXL / 高级参数
    num_inference_steps: int = Field(30, description="推理步数 (默认30)", examples=[30])
    guidance_scale: float = Field(7.5, description="引导系数 (默认7.5)", examples=[7.5])
    use_refiner: bool = Field(False, description="是否使用 Refiner 模型优化 (仅SDXL有效)", examples=[False])
    negative_prompt: Optional[str] = Field(None, description="负向提示词", examples=["low quality, bad anatomy"])
    style_preset: Optional[str] = Field(None, description="风格预设", examples=["cinematic"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "prompt": "A cute cat playing piano",
                "model": "Z-Image-Turbo",
                "size": "1024x1024",
                "n": 1,
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "use_refiner": False
            }
        }
    }

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
    async def get_image_history(user_id: str, page: int = 1, size: int = 20) -> Dict[str, Any]:
        """
        获取文生图历史记录
        """
        try:
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # 统计总数 (仅查询 source='generated')
                total = await conn.execute(
                    text("SELECT COUNT(*) FROM user_images WHERE user_id = :user_id AND source = 'generated' AND is_deleted = FALSE"),
                    {"user_id": user_id}
                )
                total_count = total.scalar()
                
                # 分页查询
                offset = (page - 1) * size
                result = await conn.execute(
                    text("""
                        SELECT id, url, prompt, meta_data, created_at
                        FROM user_images 
                        WHERE user_id = :user_id AND source = 'generated' AND is_deleted = FALSE
                        ORDER BY created_at DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    {"user_id": user_id, "limit": size, "offset": offset}
                )
                
                items = []
                for row in result:
                    meta = row.meta_data if row.meta_data else {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except:
                            meta = {}
                            
                    items.append({
                        "id": str(row.id),
                        "url": row.url,
                        "prompt": row.prompt,
                        "model": meta.get("model", "unknown"),
                        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None
                    })
                    
                return {
                    "total": total_count,
                    "items": items,
                    "page": page,
                    "size": size
                }
        except Exception as e:
            logger.error(f"获取文生图历史失败: {e}")
            raise ValueError(f"Failed to fetch image history: {e}")

    @staticmethod
    async def delete_image_history(image_id: str, user_id: str) -> None:
        """
        删除文生图历史 (软删除)
        """
        try:
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # 检查记录是否存在且属于该用户
                result = await conn.execute(
                    text("SELECT id FROM user_images WHERE id = :id AND user_id = :user_id AND is_deleted = FALSE"),
                    {"id": image_id, "user_id": user_id}
                )
                if not result.scalar():
                    raise ValueError("Image not found or permission denied")

                # 执行软删除
                await conn.execute(
                    text("UPDATE user_images SET is_deleted = TRUE, updated_at = (NOW() AT TIME ZONE 'Asia/Shanghai') WHERE id = :id"),
                    {"id": image_id}
                )
                logger.info(f"文生图记录已删除: {image_id}")
        except Exception as e:
            logger.error(f"删除文生图历史失败: {e}")
            raise e

    @staticmethod
    async def chat_with_image_stream(request: ImageChatRequest, user_id: str = "anonymous"):
        """
        多模态对话 (Qwen-VL) - 流式响应
        """
        session_id = request.session_id or str(uuid.uuid4())
        full_reply = ""
        
        try:
            # 1. 转换当前消息格式 (Pydantic -> Dict)
            current_messages = []
            for msg in request.messages:
                content_list = []
                for item in msg.content:
                    content_item = {"type": item.type}
                    if item.text is not None:
                        content_item["text"] = item.text
                    if item.image is not None:
                        content_item["image"] = item.image
                    content_list.append(content_item)
                
                current_messages.append({
                    "role": msg.role,
                    "content": content_list
                })

            # 2. 记录用户消息 (只记录最后一条 user 消息)
            if current_messages and current_messages[-1]['role'] == 'user':
                await AIManager.save_message(session_id, user_id, 'user', current_messages[-1]['content'], request.model)

            # 3. 获取历史上下文 (从数据库加载，以支持多轮对话)
            # 注意: 这里假设 save_message 已经完成写入
            history_messages = await AIManager.get_session_messages(session_id, limit=10)
            
            final_messages = []
            if history_messages:
                 final_messages = history_messages
            else:
                 # 如果数据库读取为空(异常)，使用当前请求消息兜底
                 final_messages = current_messages
            
            # 处理模型名称
            model_name = request.model
            if model_name == "Qwen3-VL-4B-Instruct":
                model_name = "Qwen/Qwen3-VL-4B-Instruct"
            elif model_name == "Qwen3-VL-8B-Instruct":
                model_name = "Qwen/Qwen3-VL-8B-Instruct"

            # 4. 流式推理
            async for chunk in ModelScopeUtils.chat_completion_stream(
                messages=final_messages,
                model_name=model_name,
                max_new_tokens=request.max_tokens
            ):
                full_reply += chunk
                yield chunk
            
            # 5. 记录 AI 回复
            if full_reply:
                await AIManager.save_message(session_id, user_id, 'assistant', full_reply, request.model)
            
        except Exception as e:
            logger.error(f"多模态流式对话失败: {e}")
            yield f"[ERROR: {str(e)}]"

    @staticmethod
    async def chat_with_image(request: ImageChatRequest, user_id: str = "anonymous") -> ImageChatResponse:
        """
        多模态对话 (Qwen-VL) - 本地推理
        """
        session_id = request.session_id or str(uuid.uuid4())
        
        try:
            # 1. 转换当前消息格式
            current_messages = []
            for msg in request.messages:
                content_list = []
                for item in msg.content:
                    content_item = {"type": item.type}
                    if item.text is not None:
                        content_item["text"] = item.text
                    if item.image is not None:
                        content_item["image"] = item.image
                    content_list.append(content_item)
                
                current_messages.append({
                    "role": msg.role,
                    "content": content_list
                })
            
            # 2. 记录用户消息
            if current_messages and current_messages[-1]['role'] == 'user':
                await AIManager.save_message(session_id, user_id, 'user', current_messages[-1]['content'], request.model)

            # 3. 获取历史上下文
            history_messages = await AIManager.get_session_messages(session_id, limit=10)
            final_messages = history_messages if history_messages else current_messages
            
            # 处理模型名称
            model_name = request.model
            if model_name == "Qwen3-VL-4B-Instruct":
                model_name = "Qwen/Qwen3-VL-4B-Instruct"
            elif model_name == "Qwen3-VL-8B-Instruct":
                model_name = "Qwen/Qwen3-VL-8B-Instruct"

            # 4. 推理
            reply = await ModelScopeUtils.chat_completion(
                messages=final_messages,
                model_name=model_name,
                max_new_tokens=request.max_tokens
            )
            
            # 5. 记录回复
            await AIManager.save_message(session_id, user_id, 'assistant', reply, request.model)
            
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
        
        # 如果请求指定 SDXL 模型，走本地调用
        if "stable-diffusion-xl" in request.model or "SDXL" in request.model:
             return await ImageManager._generate_sdxl_local(request, user_id)

        # 构造请求体
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "size": request.size,
            "n": request.n
        }
        
        api_base = settings.DIFY_API_BASE_URL
        api_key = settings.AI_API_KEY
        
        # 构造 URL (Dify OpenAI 兼容接口通常在 /v1 下)
        # 如果配置中有 /v1，则直接拼接; 否则尝试自动适配
        url = f"{api_base}/images/generations"
        if api_base.endswith("/"):
            url = f"{api_base}images/generations"

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
                                # 发送 Feishu 通知 (图文)
                                try:
                                    from backend.app.utils.feishu_utils import feishu_bot
                                    
                                    # 1. 尝试下载图片以获取 bytes
                                    async with httpx.AsyncClient() as client:
                                        resp = await client.get(img_url)
                                        if resp.status_code == 200:
                                            img_bytes = resp.content
                                            # 2. 上传到飞书获取 image_key
                                            image_key = feishu_bot.upload_image(img_bytes)
                                            
                                            if image_key:
                                                # 3. 构造富文本消息
                                                post_content = [
                                                    [{"tag": "text", "text": f"Prompt: {request.prompt}"}],
                                                    [{"tag": "text", "text": f"Model: {request.model}"}],
                                                    [{"tag": "text", "text": f"URL: {img_url}"}],
                                                    [{"tag": "img", "image_key": image_key}]
                                                ]
                                                feishu_bot.send_webhook_post(
                                                    title="🎨 [文生图完成]",
                                                    content=post_content,
                                                    webhook_token=settings.FEISHU_IMAGE_GEN_WEBHOOK_TOKEN
                                                )
                                            else:
                                                # 上传失败，降级为纯文本
                                                notify_content = f"🎨 [文生图完成]\n📝 Prompt: {request.prompt}\n🤖 Model: {request.model}\n🖼️ URL: {img_url}\n(图片上传飞书失败)"
                                                feishu_bot.send_webhook_message(notify_content, webhook_token=settings.FEISHU_IMAGE_GEN_WEBHOOK_TOKEN)
                                        else:
                                            # 下载失败
                                            notify_content = f"🎨 [文生图完成]\n📝 Prompt: {request.prompt}\n🤖 Model: {request.model}\n🖼️ URL: {img_url}\n(图片下载失败)"
                                            feishu_bot.send_webhook_message(notify_content, webhook_token=settings.FEISHU_IMAGE_GEN_WEBHOOK_TOKEN)

                                except Exception as fe:
                                    logger.error(f"发送飞书通知失败: {fe}")

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
                # 发送 Feishu 通知 (图文)
                try:
                    from backend.app.utils.feishu_utils import feishu_bot
                    
                    # 1. 上传到飞书获取 image_key (我们已经有 img_bytes)
                    image_key = feishu_bot.upload_image(img_bytes)
                    
                    if image_key:
                        # 2. 构造富文本消息
                        post_content = [
                            [{"tag": "text", "text": f"Prompt: {request.prompt}"}],
                            [{"tag": "text", "text": f"Model: {request.model}"}],
                            [{"tag": "text", "text": f"URL: {final_url}"}],
                            [{"tag": "img", "image_key": image_key}]
                        ]
                        feishu_bot.send_webhook_post(
                            title="🎨 [本地文生图完成]",
                            content=post_content,
                            webhook_token=settings.FEISHU_IMAGE_GEN_WEBHOOK_TOKEN
                        )
                    else:
                         # 降级
                         notify_content = f"🎨 [本地文生图完成]\n📝 Prompt: {request.prompt}\n🤖 Model: {request.model}\n🖼️ URL: {final_url}\n(图片上传飞书失败)"
                         feishu_bot.send_webhook_message(notify_content, webhook_token=settings.FEISHU_IMAGE_GEN_WEBHOOK_TOKEN)

                except Exception as fe:
                    logger.error(f"发送飞书通知失败: {fe}")

            except Exception as e:
                logger.error(f"Failed to save generated Z-Image to DB: {e}")

            if not url.startswith("http"):
                 # 本地相对路径，尝试拼接 (虽然后端无法确切知道前端访问的 Host，但可以尽量提供完整路径)
                 # 或者保持相对路径，由前端拼接。
                 # 用户要求 "记得返回有 S3 地址"，意味着如果配置了 S3，必须是 S3 地址。
                 # UploadUtils.save_from_bytes 已经做到了这一点。
                 pass

            # Feishu Push Logic (Triggered by keyword in prompt)
            try:
                if "A6666" in request.prompt or "飞书" in request.prompt:
                    from backend.app.yibaocode.feishu import feishu_service
                    import tempfile
                    
                    logger.info("Triggering Feishu push...")
                    # Create temp file for Feishu upload
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        tmp.write(img_bytes)
                        tmp.flush()
                        tmp_path = tmp.name
                    
                    try:
                        # Upload to Feishu (sync call, might block briefly)
                        image_key = feishu_service.upload_image(tmp_path)
                        
                        # Send Image
                        feishu_service.send_image_to_webhook(image_key)
                        
                        # Send Text
                        feishu_service.send_group_message(f"【文生图完成】\nPrompt: {request.prompt}\nUser: {user_id}\nURL: {final_url}")
                        logger.info("Feishu push successful")
                    finally:
                        os.unlink(tmp_path)
            except Exception as e:
                logger.error(f"Feishu push failed: {e}")

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

    @staticmethod
    async def _generate_sdxl_local(request: ImageGenRequest, user_id: str = "anonymous") -> ImageGenResponse:
        """
        本地运行 SDXL 模型 (Base + Refiner)
        """
        import asyncio
        loop = asyncio.get_running_loop()
        # 在线程池中运行阻塞的 GPU 推理代码
        images_bytes = await loop.run_in_executor(None, ImageManager._run_sdxl_sync, request)
        
        images_data = []
        for img_bytes in images_bytes:
            filename = f"sdxl_{uuid.uuid4()}.png"
            
            url, object_key, size = await UploadUtils.save_from_bytes(
                data=img_bytes, 
                filename=filename, 
                module="gen", 
                content_type="image/png"
            )
            
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
                            "meta_data": json.dumps({
                                "model": request.model, 
                                "provider": "sdxl-local",
                                "steps": request.num_inference_steps,
                                "refiner": request.use_refiner
                            })
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to save generated SDXL image to DB: {e}")

            images_data.append({"url": final_url})
            
        return ImageGenResponse(
            created=int(time.time()),
            data=images_data
        )

    @staticmethod
    def _run_sdxl_sync(request: ImageGenRequest) -> List[bytes]:
        """
        SDXL 同步推理逻辑
        """
        global _sdxl_base_pipeline, _sdxl_refiner_pipeline
        import torch
        from diffusers import DiffusionPipeline
        
        # 模型路径配置
        BASE_MODEL_PATH = "/home/code_dev/trai/backend/app/models/stabilityai/stable-diffusion-xl-base-1.0"
        REFINER_MODEL_PATH = "/home/code_dev/trai/backend/app/models/stabilityai/stable-diffusion-xl-refiner-1.0"
        
        # 1. 加载 Base 模型
        if _sdxl_base_pipeline is None:
            logger.info(f"Loading SDXL Base from {BASE_MODEL_PATH}...")
            if not os.path.exists(BASE_MODEL_PATH):
                raise FileNotFoundError(f"SDXL Base model not found at {BASE_MODEL_PATH}")
                
            _sdxl_base_pipeline = DiffusionPipeline.from_pretrained(
                BASE_MODEL_PATH,
                torch_dtype=torch.float16,
                use_safetensors=True,
                variant="fp16"
            )
            if torch.cuda.is_available():
                _sdxl_base_pipeline.to("cuda")
                # 启用编译优化
                logger.info("Enabling torch.compile for SDXL Base...")
                try:
                    _sdxl_base_pipeline.unet = torch.compile(_sdxl_base_pipeline.unet, mode="reduce-overhead", fullgraph=True)
                except Exception as e:
                    logger.warning(f"torch.compile failed: {e}")
            logger.success("SDXL Base loaded.")

        # 2. 加载 Refiner 模型 (按需)
        if request.use_refiner and _sdxl_refiner_pipeline is None:
            logger.info(f"Loading SDXL Refiner from {REFINER_MODEL_PATH}...")
            if not os.path.exists(REFINER_MODEL_PATH):
                logger.warning("Refiner model not found, skipping refiner step.")
            else:
                _sdxl_refiner_pipeline = DiffusionPipeline.from_pretrained(
                    REFINER_MODEL_PATH,
                    text_encoder_2=_sdxl_base_pipeline.text_encoder_2,
                    vae=_sdxl_base_pipeline.vae,
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                    variant="fp16",
                )
                if torch.cuda.is_available():
                    _sdxl_refiner_pipeline.to("cuda")
                logger.success("SDXL Refiner loaded.")

        # 3. 推理参数
        width, height = 1024, 1024
        if request.size and "x" in request.size:
            try:
                w, h = request.size.split("x")
                width, height = int(w), int(h)
            except:
                pass
                
        num_steps = request.num_inference_steps or 30
        guidance_scale = request.guidance_scale or 7.5
        negative_prompt = request.negative_prompt or "low quality, bad anatomy, worst quality, deformed, disfigured, watermark, text"

        generated_images_bytes = []
        logger.info(f"Generating SDXL image (Refiner={request.use_refiner})...")

        for _ in range(request.n):
            if request.use_refiner and _sdxl_refiner_pipeline:
                # 专家混合模式
                high_noise_frac = 0.8
                # Base
                latents = _sdxl_base_pipeline(
                    prompt=request.prompt,
                    negative_prompt=negative_prompt,
                    height=height,
                    width=width,
                    num_inference_steps=num_steps,
                    guidance_scale=guidance_scale,
                    denoising_end=high_noise_frac,
                    output_type="latent",
                ).images
                # Refiner
                image = _sdxl_refiner_pipeline(
                    prompt=request.prompt,
                    negative_prompt=negative_prompt,
                    num_inference_steps=num_steps,
                    denoising_start=high_noise_frac,
                    image=latents,
                ).images[0]
            else:
                # Base Only
                image = _sdxl_base_pipeline(
                    prompt=request.prompt,
                    negative_prompt=negative_prompt,
                    height=height,
                    width=width,
                    num_inference_steps=num_steps,
                    guidance_scale=guidance_scale,
                ).images[0]

            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='PNG')
            generated_images_bytes.append(img_byte_arr.getvalue())

        return generated_images_bytes
