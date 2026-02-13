#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/routers/ai/music_func.py
# 作者：wuhao
# 日期：2026-02-12 17:19:55
# 描述：AI 文生音乐业务逻辑 (ACE-Step1.5)

import asyncio
import os
import time
import uuid
import json
import httpx
import sys
from pathlib import Path
from typing import Any, Tuple, Optional, Dict, List

from pydantic import BaseModel, Field
from fastapi import HTTPException

from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.feishu_utils import feishu_bot
from backend.app.routers.upload.upload_func import UserAudio
from backend.app.routers.ai.image_func import ImageGenRequest, ImageManager

# -----------------------------------------------------------------------------
# 集成 ACE-Step 代码
# -----------------------------------------------------------------------------
# 确保 ACE-Step 目录在 sys.path 中
ACE_STEP_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "app" / "model_runtimes" / "ACE-Step-1.5-main"
if str(ACE_STEP_ROOT) not in sys.path:
    sys.path.append(str(ACE_STEP_ROOT))

try:
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music as ace_generate_music
    from acestep.constants import TASK_INSTRUCTIONS
except ImportError as e:
    logger.error(f"Failed to import ACE-Step modules: {e}")
    # Define dummy classes to avoid crashing on import if path is wrong, though it should be correct
    AceStepHandler = None
    LLMHandler = None
    GenerationParams = None
    GenerationConfig = None
    ace_generate_music = None


class MusicGenRequest(BaseModel):
    """
    文生音乐请求参数
    """
    prompt: str = Field(..., description="音乐描述提示词 (Prompt)", examples=["女性 流行音乐，清亮女声，现代流行编曲"])
    model_id: str = Field("ACE-Step/Ace-Step1.5", description="使用的模型ID", examples=["ACE-Step/Ace-Step1.5"])
    user_id: str = Field("system", description="发起请求的用户ID", examples=["system"])
    lyrics: Optional[str] = Field(None, description="自定义歌词 (可选, 若不填则自动生成)", examples=["Verse 1\nHello world..."])
    duration: Optional[float] = Field(None, description="目标时长 (秒, 可选)", examples=[30.0])


class MusicGenResponse(BaseModel):
    """
    文生音乐响应
    """
    audio_url: str = Field(..., description="音频地址")
    title: Optional[str] = Field(None, description="音乐标题")
    lyrics: Optional[str] = Field(None, description="歌词")
    duration: float = Field(..., description="音频时长(秒)")
    cost_time: float = Field(..., description="生成耗时(秒)")
    prompt: str = Field(..., description="提示词")
    model_id: str = Field(..., description="模型ID")


class MusicWithCoverResponse(BaseModel):
    """
    音乐+封面响应
    """
    audio_url: str = Field(..., description="音频地址")
    image_url: Optional[str] = Field(None, description="封面图片地址")
    title: Optional[str] = Field(None, description="音乐标题")
    lyrics: Optional[str] = Field(None, description="歌词")
    duration: float = Field(..., description="音频时长(秒)")
    cost_time: float = Field(..., description="生成耗时(秒)")
    prompt: str = Field(..., description="提示词")
    model_id: str = Field(..., description="音乐模型ID")



class MusicManager:
    """
    音乐生成管理器 (直接集成 ACE-Step 代码)
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MusicManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.handler = None
        self.llm_handler = None
        self.is_initialized = False
        self.init_lock = asyncio.Lock()
        
        # Paths
        # /home/code_dev/trai/backend/app/models/ACE-Step/Ace-Step1.5
        self.checkpoints_dir = Path(__file__).resolve().parent.parent.parent.parent / "app" / "models" / "ACE-Step" / "Ace-Step1.5"
        # 设置环境变量供 acestep 内部使用
        os.environ["ACESTEP_CHECKPOINTS_DIR"] = str(self.checkpoints_dir)
        
        # 临时生成目录
        self.gen_dir = Path(__file__).resolve().parent.parent.parent.parent / "static" / "gen" / "music"
        self.gen_dir.mkdir(parents=True, exist_ok=True)

    async def _generate_lyrics_and_title(self, prompt: str) -> Tuple[str, str]:
        """
        使用 AI 生成歌词和标题
        返回: (title, lyrics)
        """
        try:
            # 构造提示词
            sys_prompt = """You are a professional songwriter. Based on the user's description, generate a song title and lyrics.
            The lyrics should be structured (Verse, Chorus, etc.) and suitable for a pop song.
            If the user's description is in Chinese or requests Chinese content, the generated title and lyrics MUST be in Chinese.
            Output ONLY valid JSON in the following format:
            {
                "title": "Song Title",
                "lyrics": "Verse 1\\n..."
            }
            Do not include markdown code blocks (```json ... ```). Just the raw JSON string.
            """
            
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Description: {prompt}"}
            ]
            
            if settings.AI_API_KEY and settings.DEEPSEEK_API_BASE:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{settings.DEEPSEEK_API_BASE}/chat/completions",
                        json={
                            "model": "deepseek-chat",
                            "messages": messages,
                            "max_tokens": 1024,
                            "temperature": 0.8,
                            "response_format": {"type": "json_object"}
                        },
                        headers={"Authorization": f"Bearer {settings.AI_API_KEY}"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        try:
                            res_json = json.loads(content)
                            return res_json.get("title", "Untitled"), res_json.get("lyrics", "")
                        except Exception:
                            logger.warning(f"解析歌词JSON失败: {content}")
            
            # Fallback
            return await self._generate_title(prompt), ""
            
        except Exception as e:
            logger.warning(f"生成歌词标题失败: {e}")
            return "Untitled", ""

    async def _generate_title(self, prompt: str) -> str:
        """
        使用 AI 生成音乐标题
        """
        try:
            sys_prompt = """You are a creative music producer. Generate a short, catchy, and relevant title (3-6 words) for a song based on the user's description.
            If the user's description is in Chinese or requests Chinese content, the title MUST be in Chinese.
            Output ONLY the title, no quotes or explanations."""
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Description: {prompt}"}
            ]
            
            if settings.AI_API_KEY and settings.DEEPSEEK_API_BASE:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        f"{settings.DEEPSEEK_API_BASE}/chat/completions",
                        json={
                            "model": "deepseek-chat",
                            "messages": messages,
                            "max_tokens": 20,
                            "temperature": 0.8
                        },
                        headers={"Authorization": f"Bearer {settings.AI_API_KEY}"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        title = data["choices"][0]["message"]["content"].strip().strip('"')
                        return title
            
            return " ".join(prompt.split()[:5])
            
        except Exception as e:
            logger.warning(f"生成标题失败: {e}")
            return "Untitled Track"

    async def initialize(self):
        """
        初始化 ACE-Step 模型 (懒加载)
        """
        async with self.init_lock:
            if self.is_initialized:
                return
            
            if not AceStepHandler:
                raise ImportError("ACE-Step modules not found. Please check installation.")

            logger.info(f"🎵 正在初始化 ACE-Step 音乐模型...")
            logger.info(f"📂 模型路径: {self.checkpoints_dir}")
            
            # 运行同步初始化逻辑
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._init_sync)
            
            self.is_initialized = True
            logger.success("🎵 ACE-Step 音乐模型初始化完成")

    def _init_sync(self):
        """
        同步初始化逻辑 (运行在线程池中)
        """
        self.handler = AceStepHandler()
        self.llm_handler = LLMHandler()
        
        # 1. 初始化 DiT 模型
        # config_path 是 checkpoints_dir 下的子目录名
        # 我们的结构: models/ACE-Step/Ace-Step1.5/acestep-v15-turbo
        config_path = "acestep-v15-turbo"
        
        # AceStepHandler.initialize_service 需要 project_root
        # 它会去 project_root/checkpoints 下找 config_path
        # 我们把 self.checkpoints_dir 作为 project_root/checkpoints 的父级?
        # self.checkpoints_dir 是 .../Ace-Step1.5
        # 所以 project_root 应该是 .../ACE-Step (如果 checkpoints_dir 名为 checkpoints)
        # 但这里目录名是 Ace-Step1.5
        # 变通方法: 将 project_root 设为 ACE_STEP_ROOT (代码目录), 
        # 但在 handler.py 中它会拼 checkpoints
        # 
        # 让我们看看 initialize_service 源码细节:
        # checkpoint_dir = get_checkpoints_dir(project_root)
        # 而 get_checkpoints_dir 优先使用 ACESTEP_CHECKPOINTS_DIR 环境变量
        # 所以只要环境变量设置正确，project_root 参数可以随意传(但不能不存在)
        
        status, ok = self.handler.initialize_service(
            project_root=str(ACE_STEP_ROOT), # 这里的 project_root 不太重要，因为我们会用环境变量覆盖 checkpoints 路径
            config_path=config_path,
            device="auto",
            use_flash_attention=False,
            compile_model=False,
            offload_to_cpu=False,
            offload_dit_to_cpu=False
        )
        
        if not ok:
            raise RuntimeError(f"DiT 模型初始化失败: {status}")
            
        # 2. 初始化 LLM 模型 (可选但推荐)
        lm_model_path = "acestep-5Hz-lm-1.7B"
        
        # 使用 PyTorch 后端以确保稳定性
        # checkpoint_dir 必须是包含 model 文件夹的父目录
        # 这里 self.checkpoints_dir 是 .../Ace-Step1.5
        # 而 model 在 .../Ace-Step1.5/acestep-5Hz-lm-1.7B
        # 所以 checkpoint_dir 就是 self.checkpoints_dir
        
        status, ok = self.llm_handler.initialize(
            checkpoint_dir=str(self.checkpoints_dir),
            lm_model_path=lm_model_path,
            backend="pt", # 使用 PyTorch 后端
            device="cuda", # 假设有 GPU
            offload_to_cpu=False
        )
        
        if not ok:
            logger.warning(f"LLM 模型初始化失败 (将降级运行): {status}")
        else:
            logger.info("LLM 模型初始化成功")

    async def generate_music(self, request: MusicGenRequest, notify: bool = True) -> MusicGenResponse:
        """
        生成音乐并上传落库
        """
        start_time = time.time()
        logger.info(f"🎵 开始生成音乐: {request.prompt}")
        
        # 0. 确保初始化
        if not self.is_initialized:
            await self.initialize()
        
        # 1. 准备歌词和标题 (如果需要)
        generated_title = "Untitled"
        generated_lyrics = ""
        
        if request.lyrics:
            generated_lyrics = request.lyrics
            generated_title = await self._generate_title(request.prompt)
        else:
            # 自动生成歌词和标题
            generated_title, generated_lyrics = await self._generate_lyrics_and_title(request.prompt)
        
        # 2. 构造生成参数
        params = GenerationParams(
            task_type="text2music",
            caption=request.prompt,
            lyrics=generated_lyrics,
            duration=request.duration if request.duration else 30.0,
            instruction="Fill the audio semantic mask based on the given conditions:",
            thinking=False # 简单模式，不开启复杂推理
        )
        
        config = GenerationConfig(
            # 使用默认配置
        )
        
        # 3. 执行生成 (在线程池中)
        loop = asyncio.get_running_loop()
        
        def _run_gen():
            # 确保保存目录存在
            return ace_generate_music(
                dit_handler=self.handler,
                llm_handler=self.llm_handler,
                params=params,
                config=config,
                save_dir=str(self.gen_dir)
            )
            
        try:
            result = await loop.run_in_executor(None, _run_gen)
            
            if not result.success:
                raise ValueError(result.error or result.status_message)
                
            # 4. 处理结果
            if not result.audios or not result.audios[0].get('path'):
                raise ValueError("未生成有效的音频文件")
                
            audio_path = result.audios[0]['path']
            logger.info(f"✅ 音频生成成功: {audio_path}")
            
            # 读取音频文件内容
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
                
            # 5. 上传落库
            file_name = f"ace_step_{uuid.uuid4().hex}.wav"
            
            url, object_key, size = await UploadUtils.save_from_bytes(
                audio_bytes,
                file_name,
                module="music",
                content_type="audio/wav"
            )
            
            # 实际时长
            duration = request.duration or 30.0
            
            # 落库
            session_factory = PGUtils.get_session_factory()
            async with session_factory() as session:
                record = UserAudio(
                    user_id=request.user_id,
                    filename=file_name,
                    s3_key=object_key,
                    url=url,
                    size=size,
                    duration=duration,
                    mime_type="audio/wav",
                    module="music",
                    source="generated",
                    prompt=request.prompt,
                    text_content=generated_lyrics if generated_lyrics else generated_title,
                    meta_data={
                        "model_id": request.model_id,
                        "title": generated_title,
                        "lyrics": generated_lyrics
                    }
                )
                session.add(record)
                await session.commit()
                await session.refresh(record)
            
            if notify:
                try:
                    content = (
                        "🎵 音乐生成完成 (Internal)\n"
                        f"标题: {generated_title}\n"
                        f"提示词: {request.prompt}\n"
                        f"模型: {request.model_id}\n"
                        f"时长: {duration:.2f}s\n"
                        f"地址: {url}"
                    )
                    feishu_bot.send_webhook_message(content, webhook_token=settings.FEISHU_IMAGE_GEN_WEBHOOK_TOKEN)
                except Exception as e:
                    logger.warning(f"飞书通知发送失败: {e}")
            
            cost_time = time.time() - start_time
            return MusicGenResponse(
                audio_url=url,
                title=generated_title,
                lyrics=generated_lyrics,
                duration=duration,
                cost_time=cost_time,
                prompt=request.prompt,
                model_id=request.model_id
            )
            
        except Exception as e:
            logger.error(f"音乐生成失败: {e}")
            raise HTTPException(status_code=500, detail=f"音乐生成失败: {str(e)}")

    async def generate_music_with_cover(self, request: MusicGenRequest) -> MusicWithCoverResponse:
        """
        生成音乐并生成封面
        """
        start_time = time.time()
        
        # 1. 生成音乐 (复用上面的方法, notify=False 以避免重复通知)
        music_res = await self.generate_music(request, notify=False)
        
        # 2. 生成封面
        image_url = None
        try:
            # 优化提示词：仅保留视觉描述，移除具体的歌名文字，避免图片上出现乱码或不需要的文字
            # 同时保留 "artistic" 等风格词
            cover_prompt = f"Music album cover, {request.prompt}, high quality, artistic, no text, no watermark"
            
            img_req = ImageGenRequest(
                prompt=cover_prompt,
                width=1024,
                height=1024,
                user_id=request.user_id,
                model_id="Tongyi-MAI/Z-Image-Turbo" # 默认使用 Turbo 模型
            )
            
            # 调用 ImageManager (假设已导入)
            # from backend.app.routers.ai.image_func import ImageManager
            # image_manager = ImageManager()
            # 但 ImageManager 可能是单例，直接实例化或导入实例
            # 这里我们假设 ImageManager 是可用的
            
            # 注意: 这里需要确保 ImageManager 已初始化
            img_res = await ImageManager.generate_image(img_req, user_id=request.user_id)
            if img_res.data and len(img_res.data) > 0:
                image_url = img_res.data[0].get("url")
            
        except Exception as e:
            logger.warning(f"封面生成失败: {e}")
            # 封面生成失败不影响音乐返回
            pass
            
        # 3. 发送合并通知
        try:
            content = (
                "🎵 音乐+封面生成完成\n"
                f"标题: {music_res.title}\n"
                f"音乐地址: {music_res.audio_url}\n"
                f"封面地址: {image_url}"
            )
            feishu_bot.send_webhook_message(content, webhook_token=settings.FEISHU_IMAGE_GEN_WEBHOOK_TOKEN)
        except Exception:
            pass
            
        cost_time = time.time() - start_time
        
        return MusicWithCoverResponse(
            audio_url=music_res.audio_url,
            image_url=image_url,
            title=music_res.title,
            lyrics=music_res.lyrics,
            duration=music_res.duration,
            cost_time=cost_time,
            prompt=request.prompt,
            model_id=request.model_id
        )


music_manager = MusicManager()
