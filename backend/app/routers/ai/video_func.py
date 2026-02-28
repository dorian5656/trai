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

import random
import numpy as np
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from easydict import EasyDict
from safetensors.torch import load_file
from contextlib import asynccontextmanager

from PIL import Image
import torchvision.transforms as transforms

# 项目内部引用
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.feishu_utils import FeishuBot
from backend.app.utils.ai_utils import AIUtils

# Wan-AI 模块引用
# 假设 Wan 模块在 backend/app/engines/Robbyant/lingbot 目录下
WAN_MODULE_PATH = Path("/home/code_dev/trai/backend/app/engines/Robbyant/lingbot")
if str(WAN_MODULE_PATH) not in sys.path:
    sys.path.append(str(WAN_MODULE_PATH))

try:
    from wan.modules.model import WanModel
    from wan.modules.t5 import T5EncoderModel
    from wan.modules.vae2_1 import Wan2_1_VAE
    from wan.modules.vae2_2 import Wan2_2_VAE
    from wan.utils.fm_solvers_unipc import FlowUniPCMultistepScheduler
    from wan.utils.utils import save_video
except ImportError as e:
    logger.error(f"Wan-AI module import failed: {e}")
    # 定义占位符以避免 NameError
    WanModel = None
    T5EncoderModel = None
    Wan2_1_VAE = None
    Wan2_2_VAE = None
    FlowUniPCMultistepScheduler = None
    save_video = None

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
    image_path: Optional[str] = Field(None, description="图生视频的参考图片路径 (本地绝对路径)", examples=["/home/user/test.png"])

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
            
        # 自动选择显存最空闲的 GPU
        best_gpu = AIUtils.get_best_gpu_device()
        self.device = torch.device(best_gpu)
        logger.info(f"WanT2VWrapper 绑定设备: {self.device}")
        
        # 默认模型路径
        self.base_model_dir = '/home/code_dev/trai/backend/app/models/Wan-AI'
        self.checkpoint_dir = os.path.join(self.base_model_dir, 'Wan2.1-T2V-1.3B')
        self.current_model_name = "Wan2.1-T2V-1.3B"
        
        self.init_config()
        
        self.text_encoder = None
        self.vae = None
        self.model = None
        
        # 检查依赖是否导入成功
        if WanModel is None:
            logger.warning("Wan-AI 模块未正确加载，视频生成功能将不可用。")
        
        self.initialized = True
        logger.info("WanT2VWrapper 配置初始化完成。")

    def init_config(self, model_name: str = "Wan2.1-T2V-1.3B"):
        """
        初始化配置，根据模型名称加载不同的参数
        """
        self.current_model_name = model_name
        self.checkpoint_dir = os.path.join(self.base_model_dir, model_name)
        
        logger.info(f"Initializing config for model: {model_name} at {self.checkpoint_dir}")
        
        self.config = EasyDict()
        
        # 通用配置
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
        self.config.window_size = (-1, -1)
        self.config.qk_norm = True
        self.config.cross_attn_norm = True
        self.config.eps = 1e-6
        self.config.in_dim = 16
        self.config.text_dim = 4096
        self.config.out_dim = 16

        # 模型特定配置
        if "1.3B" in model_name:
            self.config.dim = 1536
            self.config.ffn_dim = 8960
            self.config.freq_dim = 256
            self.config.num_heads = 12
            self.config.num_layers = 30
        elif "5B" in model_name: # Wan2___2-TI2V-5B
            # 根据 config.json 内容
            # "dim": 3072, "ffn_dim": 14336, "num_heads": 24, "num_layers": 30, "in_dim": 48, "out_dim": 48
            self.config.dim = 3072
            self.config.ffn_dim = 14336
            self.config.freq_dim = 256
            self.config.num_heads = 24
            self.config.num_layers = 30
            self.config.in_dim = 48
            self.config.out_dim = 48
            self.config.vae_checkpoint = 'Wan2.2_VAE.pth'
            self.config.vae_stride = (4, 16, 16)
            # 注意：用户使用的是 TI2V 模型进行 T2V 任务，这里我们将通道数调整为 48 以匹配权重
            # 但实际生成效果可能受限，因为缺失了图像条件


    def load_models(self, model_name: str = "Wan2.1-T2V-1.3B"):
        """
        加载模型 (Lazy Loading)
        """
        # 如果请求的模型和当前加载的不一致，需要重新加载
        if self.model is not None and self.current_model_name != model_name:
            logger.info(f"Switching model from {self.current_model_name} to {model_name}...")
            # 释放旧模型
            del self.model
            del self.text_encoder
            del self.vae
            torch.cuda.empty_cache()
            self.model = None
            self.text_encoder = None
            self.vae = None
            
        if self.model is not None:
            return

        # 更新配置
        self.init_config(model_name)

        logger.info(f"正在加载 {model_name} 模型...")
        try:
            # 1. T5 编码器
            # T5 和 VAE 通常共享或位于 1.3B 目录中（如果当前模型目录中不存在）
            # 如果文件丢失，回退到 1.3B 目录查找通用组件
            t5_ckpt_path = os.path.join(self.checkpoint_dir, self.config.t5_checkpoint)
            t5_tokenizer_path = os.path.join(self.checkpoint_dir, self.config.t5_tokenizer)
            
            # Fallback logic
            default_model_dir = os.path.join(self.base_model_dir, 'Wan2.1-T2V-1.3B')
            if not os.path.exists(t5_ckpt_path):
                t5_ckpt_path = os.path.join(default_model_dir, self.config.t5_checkpoint)
                logger.warning(f"T5 checkpoint not found in {self.checkpoint_dir}, falling back to {t5_ckpt_path}")
                
            if not os.path.exists(t5_tokenizer_path):
                t5_tokenizer_path = os.path.join(default_model_dir, self.config.t5_tokenizer)
                logger.warning(f"T5 tokenizer not found in {self.checkpoint_dir}, falling back to {t5_tokenizer_path}")

            self.text_encoder = T5EncoderModel(
                text_len=self.config.text_len,
                dtype=self.config.t5_dtype,
                device=torch.device('cpu'), # Init on CPU
                checkpoint_path=t5_ckpt_path,
                tokenizer_path=t5_tokenizer_path,
                shard_fn=None,
            )

            # 2. VAE
            vae_ckpt_path = os.path.join(self.checkpoint_dir, self.config.vae_checkpoint)
            if not os.path.exists(vae_ckpt_path):
                vae_ckpt_path = os.path.join(default_model_dir, self.config.vae_checkpoint)
                logger.warning(f"VAE checkpoint not found in {self.checkpoint_dir}, falling back to {vae_ckpt_path}")

            if os.path.basename(vae_ckpt_path) == 'Wan2.2_VAE.pth':
                self.vae = Wan2_2_VAE(
                    vae_pth=vae_ckpt_path,
                    device=self.device,
                    dtype=self.config.param_dtype)
            else:
                self.vae = Wan2_1_VAE(
                    vae_pth=vae_ckpt_path,
                    device=self.device,
                    dtype=self.config.param_dtype)

            # 3. WanModel
            # 根据配置或名称确定模型类型
            model_type = 't2v'
            if 'TI2V' in self.current_model_name:
                model_type = 'ti2v'
                # TI2V specific adjustments if needed
                self.config.in_dim = 48
                self.config.out_dim = 48
            
            self.model = WanModel(
                model_type=model_type,
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
            
            # 修复 meta tensor 问题: 如果模型在 meta device 上，必须先分配内存
            # 这样 load_state_dict 才能正确加载权重，而不是尝试拷贝到 meta tensor
            try:
                is_meta = any(p.device.type == 'meta' for p in self.model.parameters())
            except:
                is_meta = False
                
            if is_meta:
                logger.info(f"检测到 WanModel 在 meta device 上，正在使用 to_empty(device={self.device}) 分配内存...")
                self.model.to_empty(device=self.device)
            
            # 加载权重
            from safetensors.torch import load_file
            import json

            # 支持分片权重 (safetensors)
            if "5B" in self.current_model_name:
                # 5B 模型通常有分片权重
                index_file = os.path.join(self.checkpoint_dir, "diffusion_pytorch_model.safetensors.index.json")
                if os.path.exists(index_file):
                    # 加载分片权重
                    with open(index_file, 'r') as f:
                        index_data = json.load(f)
                    
                    weight_map = index_data.get("weight_map", {})
                    # 获取唯一文件列表
                    shard_files = set(weight_map.values())
                    
                    for shard_file in shard_files:
                        shard_path = os.path.join(self.checkpoint_dir, shard_file)
                        logger.info(f"加载分片: {shard_file}")
                        state_dict = load_file(shard_path)
                        # 修复 CUDA 内存对齐错误：确保张量内存连续并统一数据类型
                        for k, v in state_dict.items():
                            if isinstance(v, torch.Tensor):
                                state_dict[k] = v.contiguous().to(self.config.param_dtype)
                        self.model.load_state_dict(state_dict, strict=False)
                else:
                    # 如果索引丢失，尝试单文件回退或特定分片（5B不太可能）
                     # 手动加载已知分片（如果索引丢失但文件存在）
                    shard_1 = os.path.join(self.checkpoint_dir, "diffusion_pytorch_model-00001-of-00003.safetensors")
                    if os.path.exists(shard_1):
                        for i in range(1, 4):
                            shard_name = f"diffusion_pytorch_model-0000{i}-of-00003.safetensors"
                            shard_path = os.path.join(self.checkpoint_dir, shard_name)
                            if os.path.exists(shard_path):
                                logger.info(f"加载分片: {shard_name}")
                                state_dict = load_file(shard_path)
                                # 修复 CUDA 内存对齐错误：确保张量内存连续并统一数据类型
                                for k, v in state_dict.items():
                                    if isinstance(v, torch.Tensor):
                                        state_dict[k] = v.contiguous().to(self.config.param_dtype)
                                self.model.load_state_dict(state_dict, strict=False)
                    else:
                        raise FileNotFoundError(f"在 {self.checkpoint_dir} 中未找到权重")
            else:
                # 1.3B 单文件
                state_dict_path = os.path.join(self.checkpoint_dir, "diffusion_pytorch_model.safetensors")
                if os.path.exists(state_dict_path):
                    state_dict = load_file(state_dict_path)
                    # 1.3B 同样修复内存对齐错误
                    for k, v in state_dict.items():
                        if isinstance(v, torch.Tensor):
                            state_dict[k] = v.contiguous().to(self.config.param_dtype)
                    self.model.load_state_dict(state_dict, strict=False)
                else:
                    raise FileNotFoundError(f"在 {state_dict_path} 未找到权重")

            self.model.eval().requires_grad_(False)
            self.model.to(self.device)
            self.model.to(self.config.param_dtype)
            
            # 强制转换所有参数和Buffer，确保无遗漏
            for name, param in self.model.named_parameters():
                if param.dtype != self.config.param_dtype:
                    param.data = param.data.contiguous().to(self.config.param_dtype)
            for name, buf in self.model.named_buffers():
                if buf.dtype != self.config.param_dtype and buf.dtype in [torch.float16, torch.float32]:
                    buf.data = buf.data.contiguous().to(self.config.param_dtype)
            
            logger.success("Wan2.1 模型加载成功。")
            
        except Exception as e:
            logger.error(f"Wan2.1 模型加载失败: {e}")
            raise

    def _get_mask(self, lat_h, lat_w, frame_num):
        """
        构建 I2V 掩码 (参考官方 image2video.py)
        """
        # F = frame_num
        # msk = torch.ones(1, F, lat_h, lat_w, device=self.device)
        # msk[:, 1:] = 0
        # ... logic from reference ...
        
        F = frame_num
        mask = torch.ones(1, F, lat_h, lat_w, device=self.device)
        mask[:, 1:] = 0
        
        # Handle VAE stride (4 in time)
        # Repeat first frame mask 4 times?
        # Official code:
        # msk = torch.concat([torch.repeat_interleave(msk[:, 0:1], repeats=4, dim=1), msk[:, 1:]], dim=1)
        # msk = msk.view(1, msk.shape[1] // 4, 4, lat_h, lat_w)
        # msk = msk.transpose(1, 2)[0]
        
        mask = torch.concat([
            torch.repeat_interleave(mask[:, 0:1], repeats=4, dim=1), 
            mask[:, 1:]
        ], dim=1)
        mask = mask.view(1, mask.shape[1] // 4, 4, lat_h, lat_w)
        mask = mask.transpose(1, 2)[0] # [C=4, T_lat, H, W] ? 
        # Wait, mask shape in reference ends up as?
        # VAE encodes to 4 channels? No, VAE latent is 16 channels.
        # Wan2.1 VAE stride is (4, 8, 8).
        # Time stride is 4.
        # Input to VAE is [3, F, H, W]. Output is [16, F/4, H/8, W/8].
        # The mask is constructed in latent space directly? 
        # No, reference code constructs `msk` with `lat_h, lat_w`.
        # `msk` shape: `[1, F, lat_h, lat_w]`.
        # After concat repeats: `[1, F+3, lat_h, lat_w]`.
        # After view: `[1, (F+3)//4, 4, lat_h, lat_w]`.
        # After transpose: `[1, 4, (F+3)//4, lat_h, lat_w]`.
        # [0]: `[4, T_lat, H, W]`.
        # Mask has 4 channels?
        # But `y` (latent) has 16 channels.
        # `y = torch.concat([msk, y])`.
        # So `msk` must have compatible dimensions.
        # If `msk` is 4 channels and `y` is 16, total 20?
        # But `in_dim` is 48.
        # `noise` (16) + `y` (32).
        # So `y` must be 32.
        # `y` from VAE is 16.
        # So `msk` must be 16 channels!
        # In reference code: `msk = msk.transpose(1, 2)[0]`.
        # Does `repeat_interleave` repeats 4 make it 4 channels?
        # No, `repeat_interleave` is on `dim=1` (time).
        # Ah, the reference logic handles the specific VAE structure.
        # Wait, `Wan2.1` VAE output is 16 channels.
        # Is `msk` 16 channels?
        # Let's look closely at reference:
        # msk starts [1, F, h, w].
        # repeats 4 times on dim 1 -> [1, 4, h, w] (for first frame).
        # concat -> [1, F+3, h, w].
        # view -> [1, T_lat, 4, h, w].
        # transpose(1, 2) -> [1, 4, T_lat, h, w].
        # [0] -> [4, T_lat, h, w].
        # So mask is 4 channels.
        # 4 + 16 = 20.
        # Where does 48 come from?
        # 16 (noise) + 16 (cond) + 16 (mask) = 48?
        # Maybe `Wan2.1` 1.3B/14B uses 16 channels, but 5B uses different?
        # Or maybe I misread the reference code.
        # Let's check `WanI2V` init `param_dtype`.
        # Wait, I might be looking at `Wan2.1` reference but the model is `Wan2.2`?
        # The user's web search mentioned `Wan2.2`.
        # But the file `image2video.py` is in `Robbyant/lingbot/wan`, which seems to be the local library.
        
        # Let's re-read `image2video.py` line 302: `msk = torch.ones(1, F, lat_h, lat_w, ...)`
        # `lat_h` is latent height.
        # If `msk` is 4 channels.
        # `y = self.vae.encode(...)`.
        # `y` is 16 channels.
        # `y = torch.concat([msk, y])` -> 20 channels.
        # `noise` is 16 channels.
        # `x` passed to model = `cat(noise, y)` = 16 + 20 = 36 channels.
        # But `in_dim` is 48. 36 != 48.
        # Something is missing.
        # Maybe `msk` logic produces 16 channels?
        # `msk` starts [1, F, ...].
        # `repeats=4`.
        # `view(..., 4, ...)`.
        # It creates 4 channels.
        # Unless `repeat_interleave` repeats 16 times? No, 4.
        
        # Wait, `msk` repeats 4 times.
        # Maybe `lat_h` / `lat_w` are different?
        # `Wan2_1_VAE` has `z_dim=16`.
        
        # Let's check `WanModel` `in_dim` in `image2video.py`.
        # It's not explicitly set in `__init__`, so it comes from `config`.
        # `config.in_dim` for I2V might be 36?
        # But `Wan2.1` paper says 16 channels VAE.
        # If `in_dim` is 48, maybe mask is 16 channels?
        # How to get 16 channels from 1? Repeat 16 times?
        # The reference code repeats 4 times.
        
        # Let's blindly follow the reference code for now, assuming it matches the model.
        # BUT, `config.in_dim` in my `video_func.py` is set to 48.
        # If I produce 36 channels and pass to 48-channel model, it will crash.
        # I need to match `in_dim`.
        
        # Maybe `msk` is repeated 4 times AGAIN?
        # Or `y` (latent) is 32 channels? No, `z_dim=16`.
        
        # Let's look at `msk` construction again.
        # `msk = torch.concat([torch.repeat_interleave(msk[:, 0:1], repeats=4, dim=1), msk[:, 1:]], dim=1)`
        # This extends the TIME dimension.
        # `msk = msk.view(1, msk.shape[1] // 4, 4, lat_h, lat_w)`
        # Reshapes time into (T/4, 4).
        # `msk.transpose(1, 2)` -> (1, 4, T/4, H, W).
        # So it puts 4 time steps into channels.
        # This is essentially "patching" the mask in time.
        # If the mask is 4 channels.
        
        # What if `Wan2.1` I2V uses `concat` of [Noise(16), Mask(16), Cond(16)]?
        # If I use `torch.repeat_interleave(..., repeats=16, ...)`?
        
        # Let's check `image2video.py` imports.
        # `from .modules.vae2_1 import Wan2_1_VAE`
        # It uses `Wan2_1_VAE`.
        
        # Maybe `config.in_dim` in `image2video.py` is NOT 48?
        # Let's check `backend/app/engines/Robbyant/lingbot/wan/configs/wan_i2v_A14B.py` if it exists.
        
        pass

    def encode_image(self, image_path: str, height: int, width: int):
        """
        对参考图进行编码 (Wan2.1 VAE)
        """
        if not self.vae:
            logger.error("VAE not initialized")
            return None

        try:
            # 1. 加载并预处理图片
            img = Image.open(image_path).convert('RGB')
            # 简单 Resize (双三次插值)
            img = img.resize((width, height), Image.BICUBIC)
            
            # 2. 转 Tensor 并归一化 [-1, 1]
            # [3, H, W]
            img_tensor = transforms.ToTensor()(img).to(self.device)
            img_tensor = (img_tensor - 0.5) * 2.0
            
            # 3. 构造视频输入格式 [1, 3, F, H, W]
            # Wan2.1 VAE 需要输入视频序列
            # 参考 image2video.py:
            # input: [3, F, H, W] (batched later)
            # Here we just encode 1 frame? No, we need to pad to temporal window?
            # Reference:
            # torch.concat([
            #     torch.nn.functional.interpolate(img[None].cpu(), size=(h, w), ...).transpose(0, 1),
            #     torch.zeros(3, F - 1, h, w)
            # ], dim=1)
            
            F = self.config.frame_num
            # H, W must be divisible by stride? handled by resize above
            
            # [1, 3, H, W]
            x = img_tensor.unsqueeze(0) 
            # [3, 1, H, W]
            x = x.transpose(0, 1)
            
            # Pad with zeros for remaining frames
            zeros = torch.zeros(3, F - 1, height, width, device=self.device)
            # [3, F, H, W]
            x_seq = torch.cat([x, zeros], dim=1)
            
            # 4. VAE Encode
            # Output: [1, 16, f, h, w]
            with torch.no_grad():
                latent = self.vae.encode([x_seq])[0]
            
            if self.config.in_dim == 48 and isinstance(self.vae, Wan2_2_VAE):
                logger.info(f"Encoded image latent shape: {latent.shape}")
                return latent

            base_repeats = 4
            _, lat_f, lat_h, lat_w = latent.shape
            msk = torch.ones(1, F, lat_h, lat_w, device=self.device)
            msk[:, 1:] = 0
            msk = torch.concat([
                torch.repeat_interleave(msk[:, 0:1], repeats=4, dim=1),
                msk[:, 1:]
            ], dim=1)
            t_len = msk.shape[1]
            if t_len % base_repeats != 0:
                pad_len = base_repeats - (t_len % base_repeats)
                msk = torch.cat([msk, torch.zeros(1, pad_len, lat_h, lat_w, device=self.device)], dim=1)
            msk_view = msk.view(1, msk.shape[1] // base_repeats, base_repeats, lat_h, lat_w)
            msk_base = msk_view.transpose(1, 2)[0]
            if msk_base.shape[1] != lat_f:
                msk_base = torch.nn.functional.interpolate(msk_base.unsqueeze(0), size=(lat_f, lat_h, lat_w), mode='nearest')[0]
            msk_final = msk_base
            cond_latent = torch.cat([msk_final, latent], dim=0)
            logger.info(f"Encoded image latent shape: {cond_latent.shape} (Mask: {msk_final.shape}, Latent: {latent.shape})")
            return cond_latent

        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            return None

    def generate(self, prompt: str, seed: int = -1, steps: int = 20, guide_scale: float = 5.0, model_name: str = "Wan2.1-T2V-1.3B", image_path: str = None):
        """
        生成视频
        """
        self.load_models(model_name)

        # 480 * 832 接近 16:9 的长宽比 (832/480 = 1.733, 16/9 = 1.777)
        max_area = 480 * 832 
        frame_num = self.config.frame_num
        
        # Latent (潜在空间) 计算
        aspect_ratio = 16/9
        lat_h = round(np.sqrt(max_area * aspect_ratio) // self.config.vae_stride[1] // self.config.patch_size[1] * self.config.patch_size[1])
        lat_w = round(np.sqrt(max_area / aspect_ratio) // self.config.vae_stride[2] // self.config.patch_size[2] * self.config.patch_size[2])
        lat_f = (frame_num - 1) // self.config.vae_stride[0] + 1
        max_seq_len = lat_f * lat_h * lat_w // (self.config.patch_size[1] * self.config.patch_size[2])

        logger.info(f"Latent Shape: {lat_f}x{lat_h}x{lat_w}, Max Seq Len: {max_seq_len}")

        # 随机种子
        seed = seed if seed >= 0 else random.randint(0, sys.maxsize)
        logger.info(f"Using Seed: {seed}")
        seed_g = torch.Generator(device=self.device)
        seed_g.manual_seed(seed)
        
        # 初始噪声
        if self.config.in_dim == 48:
            noise_latent = torch.randn(
                48, lat_f, lat_h, lat_w,
                dtype=torch.float32, generator=seed_g, device=self.device
            )

            fixed_cond = None
            fixed_mask = None
            if image_path:
                target_h = lat_h * self.config.vae_stride[1]
                target_w = lat_w * self.config.vae_stride[2]
                logger.info(f"正在编码参考图像: {image_path} ({target_w}x{target_h})...")

                encoded = self.encode_image(image_path, target_h, target_w)
                if encoded is None:
                    logger.warning("参考图编码失败，降级为 T2V 模式")
                else:
                    fixed_cond = encoded.to(self.device)
                    if fixed_cond.shape[1] != lat_f or fixed_cond.shape[2] != lat_h or fixed_cond.shape[3] != lat_w:
                        fixed_cond = torch.nn.functional.interpolate(
                            fixed_cond.unsqueeze(0),
                            size=(lat_f, lat_h, lat_w),
                            mode='nearest'
                        )[0]
                    fixed_mask = torch.zeros(1, lat_f, lat_h, lat_w, device=self.device)
                    fixed_mask[:, 0] = 1.0
                    fixed_mask = fixed_mask.repeat(fixed_cond.shape[0], 1, 1, 1)
            else:
                logger.info("TI2V 模型未提供图片，使用纯文生视频模式")

            noise = noise_latent
        else:
            # T2V 模型 (16通道)
            noise = torch.randn(
                self.config.in_dim,
                lat_f,
                lat_h,
                lat_w,
                dtype=torch.float32,
                generator=seed_g,
                device=self.device)
            
            if image_path:
                logger.warning(f"当前模型 {model_name} (in_dim={self.config.in_dim}) 不支持 I2V，将忽略参考图，仅使用提示词生成。")
        
        n_prompt = self.config.sample_neg_prompt

        # 文本编码
        logger.info(f"步骤 1/3: 正在编码提示词 ({self.config.text_len} tokens)...")
        # 如果显存紧张，编码后将 T5 卸载到 CPU，但这里暂时保持简单
        # 或者更好：移动到设备，编码，然后移回
        self.text_encoder.model.to(self.device)
        # 确保 T5 也在正确的数据类型下（如果可能），尽管 T5EncoderModel 会处理它
        # context = self.text_encoder([prompt], self.device)
        # context_null = self.text_encoder([n_prompt], self.device)
        
        # 显式处理上下文生成
        context = self.text_encoder([prompt], self.device)
        context_null = self.text_encoder([n_prompt], self.device)
        
        # 确保上下文在 param_dtype (bf16) 中
        if isinstance(context, list):
            context = [c.to(self.config.param_dtype) for c in context]
        else:
            context = context.to(self.config.param_dtype)
            
        if isinstance(context_null, list):
            context_null = [c.to(self.config.param_dtype) for c in context_null]
        else:
            context_null = context_null.to(self.config.param_dtype)

        self.text_encoder.model.cpu() # 卸载 T5
        torch.cuda.empty_cache()

        # 调度器
        sample_scheduler = FlowUniPCMultistepScheduler(
            num_train_timesteps=self.config.num_train_timesteps,
            shift=1,
            use_dynamic_shifting=False)
        sample_scheduler.set_timesteps(steps, device=self.device, shift=5.0)
        timesteps = sample_scheduler.timesteps

        latent = noise
        arg_c = {'context': [context[0]], 'seq_len': max_seq_len}
        arg_null = {'context': context_null, 'seq_len': max_seq_len}

        # 采样循环
        logger.info(f"Step 2/3: 开始扩散采样 (Total Steps: {steps})...")
        with torch.amp.autocast('cuda', dtype=self.config.param_dtype), torch.no_grad():
            for i, t in enumerate(timesteps):
                if (i + 1) % 5 == 0 or (i + 1) == steps or i == 0:
                    logger.info(f"  采样进度: {i + 1}/{steps} ({(i + 1) / steps * 100:.0f}%)")
                
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
                if self.config.in_dim == 48 and fixed_cond is not None and fixed_mask is not None:
                    latent = latent * (1 - fixed_mask) + fixed_cond * fixed_mask

        # 解码
        logger.info("Step 3/3: 正在解码视频 (VAE Decoding)...")
        # self.model.cpu() # 如果有需要，可以卸载模型以节省显存
        # torch.cuda.empty_cache()
        
        # 如果是 TI2V 模型 (48通道)，只取前 16 个通道作为生成的 Latent
        if isinstance(self.vae, Wan2_1_VAE) and latent.shape[0] > 16:
            latent = latent[:16]

        videos = self.vae.decode([latent])
        
        # 检查生成结果统计信息 (Debug Solid Color Issue)
        video_tensor = videos[0]
        v_min, v_max = video_tensor.min().item(), video_tensor.max().item()
        v_mean, v_std = video_tensor.mean().item(), video_tensor.std().item()
        logger.info(f"Generated Video Stats: Min={v_min:.4f}, Max={v_max:.4f}, Mean={v_mean:.4f}, Std={v_std:.4f}")
        
        if v_std < 1e-3:
            logger.error("⚠️ 警告: 生成的视频方差极低，可能是纯色视频！请检查模型输入或参数。")
        
        if image_path:
            try:
                frame = video_tensor[:, 0]
                ref_img = Image.open(image_path).convert('RGB')
                ref_img = ref_img.resize((frame.shape[2], frame.shape[1]), Image.BICUBIC)
                ref_tensor = transforms.ToTensor()(ref_img).to(frame.device)
                ref_tensor = (ref_tensor - 0.5) * 2.0
                mse = torch.mean((frame - ref_tensor) ** 2).item()
                mae = torch.mean(torch.abs(frame - ref_tensor)).item()
                f = frame.permute(1, 2, 0).reshape(-1, 3)
                r = ref_tensor.permute(1, 2, 0).reshape(-1, 3)
                f_norm = f / (torch.norm(f, dim=1, keepdim=True) + 1e-8)
                r_norm = r / (torch.norm(r, dim=1, keepdim=True) + 1e-8)
                cos_sim = torch.mean(torch.sum(f_norm * r_norm, dim=1)).item()
                logger.info(f"I2V 首帧与参考图相似度: Cos={cos_sim:.4f}, MSE={mse:.2f}, MAE={mae:.2f}")
                if cos_sim < 0.85:
                    logger.error("⚠️ 警告: I2V 首帧与参考图相似度较低，可能未正确注入图像条件。")
            except Exception as e:
                logger.error(f"I2V 首帧相似度检测失败: {e}")
        
        return videos[0]


# =============================================================================
# Manager
# =============================================================================

class VideoManager:
    """
    视频生成业务逻辑管理器
    """
    
    @staticmethod
    async def preload_model():
        """
        启动时预加载模型 (异步执行)
        """
        try:
            logger.info("🚀 [VideoManager] 开始预加载视频生成模型...")
            # 在线程池中执行耗时操作，避免阻塞事件循环
            import asyncio
            wrapper = WanT2VWrapper()
            await asyncio.to_thread(wrapper.load_models)
            logger.success("✅ [VideoManager] 视频生成模型预加载完成!")
        except Exception as e:
            logger.error(f"❌ [VideoManager] 模型预加载失败: {e}")

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
            
            # 在线程池中运行同步生成
            import asyncio
            loop = asyncio.get_running_loop()
            
            video_tensor = await loop.run_in_executor(
                None, 
                wrapper.generate, 
                req.prompt, 
                req.seed, 
                req.sampling_steps, 
                req.guide_scale,
                req.model,
                req.image_path # 传递图片路径
            )
            
            # 2. 保存视频文件 (临时保存)
            today = time.strftime("%Y%m%d")
            filename = f"{task_id}.mp4"
            # 临时目录
            temp_dir = Path("/tmp/trai_video_gen") 
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / filename
            
            # 先保存到本地
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
                    logger.error(f"无法打开视频文件提取封面: {temp_path}")
                else:
                    ret, frame = cap.read()
                    if ret:
                        # 保存为 JPEG
                        cv2.imwrite(str(cover_path), frame)
                        logger.info(f"封面图提取成功: {cover_path}")
                    else:
                        logger.error("无法读取视频第一帧")
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
                        logger.warning(f"上传封面到飞书失败: {e}")
                        
                    # 清理封面临时文件
                    os.remove(cover_path)
            except ImportError:
                logger.error("未安装 opencv-python-headless，跳过封面提取")
            except Exception as e:
                logger.error(f"生成封面图失败: {e}")
                
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
