#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/video_func.py
# 作者：liuhd
# 日期：2026-02-06
# 描述：AI 视频生成业务逻辑 (Wan2.1-T2V-1.3B)

import os
import sys
import uuid
import time
import torch
import logging
import random
import numpy as np
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from easydict import EasyDict
from safetensors.torch import load_file
from contextlib import asynccontextmanager

# 项目内部引用
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.feishu_utils import FeishuBot
from backend.app.models.ai_video import AIVideoTask

# Wan-AI 模块引用
# 假设 Wan 模块在 backend/app/engines/Robbyant/lingbot 目录下
WAN_MODULE_PATH = Path("/home/code_dev/trai/backend/app/engines/Robbyant/lingbot")
if str(WAN_MODULE_PATH) not in sys.path:
    sys.path.append(str(WAN_MODULE_PATH))

try:
    from wan.modules.model import WanModel
    from wan.modules.t5 import T5EncoderModel
    from wan.modules.vae2_1 import Wan2_1_VAE
    from wan.utils.fm_solvers_unipc import FlowUniPCMultistepScheduler
    from wan.utils.utils import save_video
except ImportError as e:
    logger.error(f"Wan-AI module import failed: {e}")

# =============================================================================
# Schema 定义
# =============================================================================

class VideoGenRequest(BaseModel):
    """
    文生视频请求
    """
    prompt: str = Field(..., description="提示词", examples=["一只可爱的小猫在草地上奔跑"])
    model: str = Field("Wan2.1-T2V-1.3B", description="模型名称", examples=["Wan2.1-T2V-1.3B"])
    ratio: str = Field("16:9", description="宽高比", examples=["16:9"])
    duration: int = Field(5, description="视频时长(秒) - 实际上由 frame_num 决定, 这里仅作参考", examples=[5])
    sampling_steps: int = Field(20, description="采样步数", examples=[20])
    guide_scale: float = Field(5.0, description="引导系数", examples=[5.0])
    seed: int = Field(-1, description="随机种子 (-1 表示随机)", examples=[-1])

class VideoGenResponse(BaseModel):
    """
    文生视频响应
    """
    video_url: str = Field(..., description="视频 URL")
    cover_url: Optional[str] = Field(None, description="封面图 URL")
    cost_time: float = Field(..., description="耗时(秒)")

# =============================================================================
# WanT2V 封装类
# =============================================================================

class WanT2VWrapper:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(WanT2VWrapper, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
            
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.checkpoint_dir = '/home/code_dev/trai/backend/app/models/Wan-AI/Wan2.1-T2V-1.3B'
        
        # Config (Hardcoded for 1.3B based on test script)
        self.config = EasyDict()
        self.config.t5_model = 'umt5_xxl'
        self.config.t5_dtype = torch.bfloat16
        self.config.text_len = 512
        self.config.param_dtype = torch.bfloat16
        self.config.num_train_timesteps = 1000
        self.config.sample_fps = 16
        self.config.sample_neg_prompt = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
        self.config.frame_num = 81
        self.config.t5_checkpoint = 'models_t5_umt5-xxl-enc-bf16.pth'
        self.config.t5_tokenizer = 'google/umt5-xxl'
        self.config.vae_checkpoint = 'Wan2.1_VAE.pth'
        self.config.vae_stride = (4, 8, 8)
        self.config.patch_size = (1, 2, 2)
        self.config.dim = 1536
        self.config.ffn_dim = 8960
        self.config.freq_dim = 256
        self.config.num_heads = 12
        self.config.num_layers = 30
        self.config.window_size = (-1, -1)
        self.config.qk_norm = True
        self.config.cross_attn_norm = True
        self.config.eps = 1e-6
        self.config.in_dim = 16
        self.config.text_dim = 4096
        self.config.out_dim = 16

        self.text_encoder = None
        self.vae = None
        self.model = None
        
        self.initialized = True
        logger.info("WanT2VWrapper 配置初始化完成。")

    def load_models(self):
        """
        加载模型 (Lazy Loading)
        """
        if self.model is not None:
            return

        logger.info("正在加载 Wan2.1 模型...")
        try:
            # 1. T5 Encoder
            self.text_encoder = T5EncoderModel(
                text_len=self.config.text_len,
                dtype=self.config.t5_dtype,
                device=torch.device('cpu'), # Init on CPU
                checkpoint_path=os.path.join(self.checkpoint_dir, self.config.t5_checkpoint),
                tokenizer_path=os.path.join(self.checkpoint_dir, self.config.t5_tokenizer),
                shard_fn=None,
            )

            # 2. VAE
            self.vae = Wan2_1_VAE(
                vae_pth=os.path.join(self.checkpoint_dir, self.config.vae_checkpoint),
                device=self.device)

            # 3. WanModel
            self.model = WanModel(
                model_type='t2v',
                patch_size=self.config.patch_size,
                text_len=self.config.text_len,
                in_dim=self.config.in_dim,
                dim=self.config.dim,
                ffn_dim=self.config.ffn_dim,
                freq_dim=self.config.freq_dim,
                text_dim=self.config.text_dim,
                out_dim=self.config.out_dim,
                num_heads=self.config.num_heads,
                num_layers=self.config.num_layers,
                window_size=self.config.window_size,
                qk_norm=self.config.qk_norm,
                cross_attn_norm=self.config.cross_attn_norm,
                eps=self.config.eps
            )
            
            # Load weights
            state_dict_path = os.path.join(self.checkpoint_dir, "diffusion_pytorch_model.safetensors")
            if os.path.exists(state_dict_path):
                state_dict = load_file(state_dict_path)
                self.model.load_state_dict(state_dict, strict=False)
            else:
                raise FileNotFoundError(f"Weights not found at {state_dict_path}")

            self.model.eval().requires_grad_(False)
            self.model.to(self.device)
            self.model.to(self.config.param_dtype)
            
            # 强制转换所有参数和Buffer，确保无遗漏
            for name, param in self.model.named_parameters():
                if param.dtype != self.config.param_dtype:
                    param.data = param.data.to(self.config.param_dtype)
            for name, buf in self.model.named_buffers():
                if buf.dtype != self.config.param_dtype and buf.dtype in [torch.float16, torch.float32]:
                    buf.data = buf.data.to(self.config.param_dtype)
            
            logger.success("Wan2.1 模型加载成功。")
            
        except Exception as e:
            logger.error(f"Wan2.1 模型加载失败: {e}")
            raise

    def generate(self, prompt: str, seed: int = -1, steps: int = 20, guide_scale: float = 5.0):
        self.load_models()
        
        # Dimensions (480p recommended for 1.3B)
        # 480 * 832 is close to 16:9 aspect ratio (832/480 = 1.733, 16/9 = 1.777)
        max_area = 480 * 832 
        frame_num = self.config.frame_num
        
        # Latent calculations
        aspect_ratio = 16/9
        lat_h = round(np.sqrt(max_area * aspect_ratio) // self.config.vae_stride[1] // self.config.patch_size[1] * self.config.patch_size[1])
        lat_w = round(np.sqrt(max_area / aspect_ratio) // self.config.vae_stride[2] // self.config.patch_size[2] * self.config.patch_size[2])
        # Recalculate h/w based on latents to match VAE requirements
        # h = lat_h * self.config.vae_stride[1]
        # w = lat_w * self.config.vae_stride[2]
        lat_f = (frame_num - 1) // self.config.vae_stride[0] + 1
        max_seq_len = lat_f * lat_h * lat_w // (self.config.patch_size[1] * self.config.patch_size[2])

        # Seed
        seed = seed if seed >= 0 else random.randint(0, sys.maxsize)
        seed_g = torch.Generator(device=self.device)
        seed_g.manual_seed(seed)
        
        # Initial noise
        noise = torch.randn(
            16,
            lat_f,
            lat_h,
            lat_w,
            dtype=torch.float32,
            generator=seed_g,
            device=self.device)
        
        n_prompt = self.config.sample_neg_prompt

        # Text Encoding
        # Offload T5 to CPU after encoding if memory is tight, but here we keep it simple for now
        # Or better: move to device, encode, move back
        self.text_encoder.model.to(self.device)
        # Ensure T5 is also in correct dtype if possible, though T5EncoderModel handles it
        # context = self.text_encoder([prompt], self.device)
        # context_null = self.text_encoder([n_prompt], self.device)
        
        # Explicitly handling context generation
        context = self.text_encoder([prompt], self.device)
        context_null = self.text_encoder([n_prompt], self.device)
        
        # Ensure context is in param_dtype (bf16)
        if isinstance(context, list):
            context = [c.to(self.config.param_dtype) for c in context]
        else:
            context = context.to(self.config.param_dtype)
            
        if isinstance(context_null, list):
            context_null = [c.to(self.config.param_dtype) for c in context_null]
        else:
            context_null = context_null.to(self.config.param_dtype)

        self.text_encoder.model.cpu() # Offload T5
        torch.cuda.empty_cache()

        # Scheduler
        sample_scheduler = FlowUniPCMultistepScheduler(
            num_train_timesteps=self.config.num_train_timesteps,
            shift=1,
            use_dynamic_shifting=False)
        sample_scheduler.set_timesteps(steps, device=self.device, shift=5.0)
        timesteps = sample_scheduler.timesteps

        latent = noise
        arg_c = {'context': [context[0]], 'seq_len': max_seq_len}
        arg_null = {'context': context_null, 'seq_len': max_seq_len}

        # Sampling Loop
        with torch.amp.autocast('cuda', dtype=self.config.param_dtype), torch.no_grad():
            for _, t in enumerate(timesteps):
                latent_model_input = [latent.to(self.device)]
                timestep = [t]
                timestep = torch.stack(timestep).to(self.device)

                noise_pred_cond = self.model(latent_model_input, t=timestep, **arg_c)[0]
                noise_pred_uncond = self.model(latent_model_input, t=timestep, **arg_null)[0]
                
                noise_pred = noise_pred_uncond + guide_scale * (noise_pred_cond - noise_pred_uncond)
                
                temp_x0 = sample_scheduler.step(
                    noise_pred.unsqueeze(0),
                    t,
                    latent.unsqueeze(0),
                    return_dict=False,
                    generator=seed_g)[0]
                latent = temp_x0.squeeze(0)

        # 解码
        # self.model.cpu() # 如果有需要，可以卸载模型以节省显存
        # torch.cuda.empty_cache()
        
        videos = self.vae.decode([latent])
        return videos[0]


# =============================================================================
# Manager
# =============================================================================

class VideoManager:
    """
    视频生成业务逻辑管理器
    """
    
    @staticmethod
    async def generate_video(req: VideoGenRequest) -> VideoGenResponse:
        start_time = time.time()
        task_id = str(uuid.uuid4())
        logger.info(f"开始生成视频, 提示词: {req.prompt}, 任务ID: {task_id}")
        
        # 0. 创建数据库记录 (Pending)
        session_factory = PGUtils.get_session_factory()
        async with session_factory() as session:
            try:
                new_task = AIVideoTask(
                    task_id=task_id,
                    prompt=req.prompt,
                    model=req.model,
                    status="processing", # 标记为处理中
                    cost_time=0.0
                )
                session.add(new_task)
                await session.commit()
            except Exception as e:
                logger.error(f"创建数据库任务记录失败: {e}")
                # 即使DB失败，也尝试继续生成，或者直接抛出异常
                # raise e 
        
        # 0.5 发送飞书通知 (任务开始)
        try:
            feishu = FeishuBot()
            start_msg = f"🚀 **视频生成任务已启动**\n\n🆔 任务ID: {task_id}\n📝 提示词: {req.prompt}\n🤖 模型: {req.model}\n⏳ 状态: 处理中..."
            feishu.send_webhook_message(start_msg)
        except Exception as e:
            logger.error(f"飞书启动通知发送失败: {e}")
        
        try:
            # 1. 生成视频
            wrapper = WanT2VWrapper()
            
            # Run synchronous generation in thread pool
            import asyncio
            loop = asyncio.get_running_loop()
            
            video_tensor = await loop.run_in_executor(
                None, 
                wrapper.generate, 
                req.prompt, 
                req.seed, 
                req.sampling_steps, 
                req.guide_scale
            )
            
            # 2. 保存视频文件 (临时保存)
            today = time.strftime("%Y%m%d")
            filename = f"{task_id}.mp4"
            # 临时目录
            temp_dir = Path("/tmp/trai_video_gen") 
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / filename
            
            # Save video locally first
            save_video(
                tensor=video_tensor[None],
                save_file=str(temp_path),
                fps=16,
                nrow=1,
                normalize=True,
                value_range=(-1, 1)
            )
            
            # 3. 上传到 S3 (或本地静态目录)
            with open(temp_path, "rb") as f:
                video_bytes = f.read()
            
            # 3.1 生成封面图 (取第一帧)
            cover_url = None
            cover_image_key = None
            try:
                import cv2
                cover_filename = f"{task_id}.jpg"
                cover_path = temp_dir / cover_filename
                
                # 使用 OpenCV 提取第一帧
                cap = cv2.VideoCapture(str(temp_path))
                if not cap.isOpened():
                    logger.error(f"Failed to open video file for cover extraction: {temp_path}")
                else:
                    ret, frame = cap.read()
                    if ret:
                        # 保存为 JPEG
                        cv2.imwrite(str(cover_path), frame)
                        logger.info(f"Cover image extracted successfully: {cover_path}")
                    else:
                        logger.error("Failed to read first frame from video")
                    cap.release()
                
                if cover_path.exists():
                    with open(cover_path, "rb") as f:
                        cover_bytes = f.read()
                        
                    # 上传封面到 S3
                    c_url, _, _ = await UploadUtils.save_from_bytes(
                        data=cover_bytes,
                        filename=cover_filename,
                        module="ai_video/covers",
                        content_type="image/jpeg"
                    )
                    
                    if not c_url.startswith("http"):
                        if not c_url.startswith("/"):
                            c_url = "/" + c_url
                    cover_url = c_url
                    
                    # 上传封面到飞书 (获取 image_key)
                    try:
                        feishu = FeishuBot()
                        cover_image_key = feishu.upload_image(cover_bytes)
                    except Exception as e:
                        logger.warning(f"Failed to upload cover to Feishu: {e}")
                        
                    # 清理封面临时文件
                    os.remove(cover_path)
            except ImportError:
                logger.error("opencv-python-headless not installed, skipping cover extraction")
            except Exception as e:
                logger.error(f"Failed to generate cover image: {e}")
                
            # 使用 UploadUtils 上传
            # save_from_bytes 返回 (url_path, file_path, size)
            # module="ai_video"
            video_url, _, _ = await UploadUtils.save_from_bytes(
                data=video_bytes,
                filename=filename,
                module="ai_video",
                content_type="video/mp4"
            )
            
            # 如果是本地存储，UploadUtils 返回的是相对路径，需要拼装完整 URL
            if not video_url.startswith("http"):
                # 假设 API 基础 URL，或者前端通过 /static 访问
                # 这里简单处理，如果是相对路径，假设是 /static/...
                if not video_url.startswith("/"):
                    video_url = "/" + video_url
            
            cost_time = time.time() - start_time
            logger.success(f"视频生成并上传成功: {video_url}, 耗时: {cost_time:.2f}s")
            
            # 4. 更新数据库 (Success)
            async with session_factory() as session:
                async with session.begin():
                    # 重新查询以获取最新状态
                    task = await PGUtils.fetch_one(
                        "SELECT * FROM ai_video_tasks WHERE task_id = :task_id", 
                        {"task_id": task_id}
                    )
                    if task:
                        await PGUtils.execute_update(
                            """
                            UPDATE ai_video_tasks 
                            SET status = :status, video_url = :video_url, cover_url = :cover_url, cost_time = :cost_time, updated_at = NOW()
                            WHERE task_id = :task_id
                            """,
                            {
                                "status": "success",
                                "video_url": video_url,
                                "cover_url": cover_url,
                                "cost_time": cost_time,
                                "task_id": task_id
                            }
                        )

            # 5. 发送飞书通知 (卡片消息)
            try:
                feishu = FeishuBot()
                
                # 注意: 飞书 Webhook 不支持直接发送视频文件 (media/file 类型)
                # 因此我们使用交互式卡片展示封面图和链接，这是 Webhook 的最佳实践
                
                # 尝试发送交互式卡片
                if cover_image_key:
                    card_content = {
                        "config": {
                            "wide_screen_mode": True
                        },
                        "header": {
                            "title": {
                                "tag": "plain_text",
                                "content": "🎬 视频生成完成"
                            },
                            "template": "blue"
                        },
                        "elements": [
                            {
                                "tag": "div",
                                "fields": [
                                    {
                                        "is_short": True,
                                        "text": {
                                            "tag": "lark_md",
                                            "content": f"**任务ID**: {task_id}"
                                        }
                                    },
                                    {
                                        "is_short": True,
                                        "text": {
                                            "tag": "lark_md",
                                            "content": f"**耗时**: {cost_time:.2f}s"
                                        }
                                    }
                                ]
                            },
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**提示词**: {req.prompt}"
                                }
                            },
                            {
                                "tag": "img",
                                "img_key": cover_image_key,
                                "alt": {
                                    "tag": "plain_text",
                                    "content": "视频封面"
                                },
                                "mode": "crop_center",
                                "custom_width": 300
                            },
                            {
                                "tag": "action",
                                "actions": [
                                    {
                                        "tag": "button",
                                        "text": {
                                            "tag": "plain_text",
                                            "content": "▶️ 点击播放视频"
                                        },
                                        "url": video_url,
                                        "type": "primary"
                                    },
                                    {
                                        "tag": "button",
                                        "text": {
                                            "tag": "plain_text",
                                            "content": "📥 下载"
                                        },
                                        "url": video_url,
                                        "type": "default"
                                    }
                                ]
                            }
                        ]
                    }
                    feishu.send_webhook_card(card_content)
                else:
                    # 降级为文本
                    msg = f"🎬 **视频生成完成**\n\n🆔 任务ID: {task_id}\n📝 提示词: {req.prompt}\n⏱️ 耗时: {cost_time:.2f}s\n🔗 链接: {video_url}"
                    feishu.send_webhook_message(msg)
            except Exception as e:
                logger.error(f"Feishu notification failed: {e}")

            # 清理临时文件 (移到最后，确保上传完成后清理)
            try:
                if temp_path.exists():
                    os.remove(temp_path)
            except:
                pass

            return VideoGenResponse(
                video_url=video_url,
                cost_time=cost_time
            )

        except Exception as e:
            cost_time = time.time() - start_time
            logger.error(f"视频生成失败: {e}")
            
            # 更新数据库 (Failed)
            async with session_factory() as session:
                try:
                    await PGUtils.execute_update(
                        """
                        UPDATE ai_video_tasks 
                        SET status = :status, error_msg = :error_msg, cost_time = :cost_time, updated_at = NOW()
                        WHERE task_id = :task_id
                        """,
                        {
                            "status": "failed",
                            "error_msg": str(e)[:500], # 截断错误信息
                            "cost_time": cost_time,
                            "task_id": task_id
                        }
                    )
                except Exception as db_e:
                    logger.error(f"更新数据库失败状态出错: {db_e}")
            
            raise e
