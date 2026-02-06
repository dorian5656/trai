
import sys
import os
import math
import random
import logging
import torch
import torch.distributed as dist
from easydict import EasyDict
from tqdm import tqdm
from contextlib import contextmanager

# Add wan module to path
sys.path.append('/home/code_dev/trai/backend/app/engines/Robbyant/lingbot')

from wan.modules.model import WanModel
from wan.modules.t5 import T5EncoderModel
from wan.modules.vae2_1 import Wan2_1_VAE
from wan.utils.fm_solvers_unipc import FlowUniPCMultistepScheduler
from wan.utils.utils import save_video
from safetensors.torch import load_file

# Logging setup
logging.basicConfig(level=logging.INFO)

# Config for Wan2.1-T2V-1.3B
t2v_1_3B = EasyDict()

# Shared config
t2v_1_3B.t5_model = 'umt5_xxl'
t2v_1_3B.t5_dtype = torch.bfloat16
t2v_1_3B.text_len = 512
t2v_1_3B.param_dtype = torch.bfloat16
t2v_1_3B.num_train_timesteps = 1000
t2v_1_3B.sample_fps = 16
t2v_1_3B.sample_neg_prompt = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
t2v_1_3B.frame_num = 81

# Specific config
t2v_1_3B.t5_checkpoint = 'models_t5_umt5-xxl-enc-bf16.pth'
t2v_1_3B.t5_tokenizer = 'google/umt5-xxl'
t2v_1_3B.vae_checkpoint = 'Wan2.1_VAE.pth'
t2v_1_3B.vae_stride = (4, 8, 8)
t2v_1_3B.patch_size = (1, 2, 2)
t2v_1_3B.dim = 1536
t2v_1_3B.ffn_dim = 8960
t2v_1_3B.freq_dim = 256
t2v_1_3B.num_heads = 12
t2v_1_3B.num_layers = 30
t2v_1_3B.window_size = (-1, -1)
t2v_1_3B.qk_norm = True
t2v_1_3B.cross_attn_norm = True
t2v_1_3B.eps = 1e-6
t2v_1_3B.in_dim = 16
t2v_1_3B.text_dim = 4096
t2v_1_3B.out_dim = 16

class WanT2V:
    def __init__(
        self,
        config,
        checkpoint_dir,
        device_id=0,
        rank=0,
        t5_fsdp=False,
        dit_fsdp=False,
        use_sp=False,
        t5_cpu=False,
        init_on_cpu=True,
    ):
        self.device = torch.device(f"cuda:{device_id}")
        self.config = config
        self.rank = rank
        self.t5_cpu = t5_cpu
        self.init_on_cpu = init_on_cpu
        self.num_train_timesteps = config.num_train_timesteps
        self.param_dtype = config.param_dtype
        
        # Initialize T5
        self.text_encoder = T5EncoderModel(
            text_len=config.text_len,
            dtype=config.t5_dtype,
            device=torch.device('cpu'),
            checkpoint_path=os.path.join(checkpoint_dir, config.t5_checkpoint),
            tokenizer_path=os.path.join(checkpoint_dir, config.t5_tokenizer),
            shard_fn=None,
        )

        # Initialize VAE
        self.vae_stride = config.vae_stride
        self.patch_size = config.patch_size
        self.vae = Wan2_1_VAE(
            vae_pth=os.path.join(checkpoint_dir, config.vae_checkpoint),
            device=self.device)

        # Initialize WanModel (T2V 1.3B has only one model usually)
        logging.info(f"Creating WanModel from {checkpoint_dir}")
        # Manually initialize to avoid meta device issues with partial weights
        self.model = WanModel(
            model_type='t2v',
            patch_size=config.patch_size,
            text_len=config.text_len,
            in_dim=config.in_dim,
            dim=config.dim,
            ffn_dim=config.ffn_dim,
            freq_dim=config.freq_dim,
            text_dim=config.text_dim,
            out_dim=config.out_dim,
            num_heads=config.num_heads,
            num_layers=config.num_layers,
            window_size=config.window_size,
            qk_norm=config.qk_norm,
            cross_attn_norm=config.cross_attn_norm,
            eps=config.eps
        )
        
        # Load weights
        state_dict_path = os.path.join(checkpoint_dir, "diffusion_pytorch_model.safetensors")
        if os.path.exists(state_dict_path):
            state_dict = load_file(state_dict_path)
            missing, unexpected = self.model.load_state_dict(state_dict, strict=False)
            logging.info(f"Loaded weights. Missing keys: {len(missing)}")
            if len(missing) > 0:
                logging.debug(f"Missing: {missing}")
        else:
            raise FileNotFoundError(f"Weights not found at {state_dict_path}")
        
        # Configure model
        self.model.eval().requires_grad_(False)
        self.model.to(self.device)
        self.model.to(self.param_dtype)
        
        self.sample_neg_prompt = config.sample_neg_prompt

    def generate(self,
                 input_prompt,
                 max_area=720 * 1280,
                 frame_num=81,
                 shift=5.0,
                 sample_solver='unipc',
                 sampling_steps=40,
                 guide_scale=5.0,
                 n_prompt="",
                 seed=-1,
                 offload_model=True):
        
        # Set up dimensions
        aspect_ratio = 16/9 # Default aspect ratio
        
        # Calculate latent dimensions
        lat_h = round(np.sqrt(max_area * aspect_ratio) // self.vae_stride[1] // self.patch_size[1] * self.patch_size[1])
        lat_w = round(np.sqrt(max_area / aspect_ratio) // self.vae_stride[2] // self.patch_size[2] * self.patch_size[2])
        h = lat_h * self.vae_stride[1]
        w = lat_w * self.vae_stride[2]
        lat_f = (frame_num - 1) // self.vae_stride[0] + 1
        
        max_seq_len = lat_f * lat_h * lat_w // (self.patch_size[1] * self.patch_size[2])
        
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
        
        if n_prompt == "":
            n_prompt = self.sample_neg_prompt

        # Text encoding
        if not self.t5_cpu:
            self.text_encoder.model.to(self.device)
            context = self.text_encoder([input_prompt], self.device)
            context_null = self.text_encoder([n_prompt], self.device)
            if offload_model:
                self.text_encoder.model.cpu()
        else:
            context = self.text_encoder([input_prompt], torch.device('cpu'))
            context_null = self.text_encoder([n_prompt], torch.device('cpu'))
            context = [t.to(self.device) for t in context]
            context_null = [t.to(self.device) for t in context_null]

        # Scheduler
        sample_scheduler = FlowUniPCMultistepScheduler(
            num_train_timesteps=self.num_train_timesteps,
            shift=1,
            use_dynamic_shifting=False)
        sample_scheduler.set_timesteps(sampling_steps, device=self.device, shift=shift)
        timesteps = sample_scheduler.timesteps

        latent = noise
        
        # Model arguments
        arg_c = {'context': [context[0]], 'seq_len': max_seq_len}
        arg_null = {'context': context_null, 'seq_len': max_seq_len}

        if offload_model:
            torch.cuda.empty_cache()

        # Sampling loop
        with torch.amp.autocast('cuda', dtype=self.param_dtype), torch.no_grad():
            for _, t in enumerate(tqdm(timesteps)):
                latent_model_input = [latent.to(self.device)]
                timestep = [t]
                timestep = torch.stack(timestep).to(self.device)

                # In T2V 1.3B we only have one model, so no switching needed
                model = self.model 
                
                noise_pred_cond = model(latent_model_input, t=timestep, **arg_c)[0]
                noise_pred_uncond = model(latent_model_input, t=timestep, **arg_null)[0]
                
                noise_pred = noise_pred_uncond + guide_scale * (noise_pred_cond - noise_pred_uncond)
                
                temp_x0 = sample_scheduler.step(
                    noise_pred.unsqueeze(0),
                    t,
                    latent.unsqueeze(0),
                    return_dict=False,
                    generator=seed_g)[0]
                latent = temp_x0.squeeze(0)

        # Decode
        if offload_model:
            self.model.cpu()
            torch.cuda.empty_cache()
            
        videos = self.vae.decode([latent])
        
        return videos[0]

import numpy as np

def main():
    checkpoint_dir = '/home/code_dev/trai/backend/app/models/Wan-AI/Wan2.1-T2V-1.3B'
    prompt = "一只超级可爱的小奶猫，毛茸茸的，白色和橘色相间的花纹，大大的水灵灵的眼睛，好奇地看着镜头。它在柔软的草地上玩耍，阳光明媚，光影柔和。特写镜头，4k高清，毛发细节清晰可见，极其真实，电影感。"
    
    print(f"Initializing WanT2V with checkpoint: {checkpoint_dir}")
    wan_t2v = WanT2V(
        config=t2v_1_3B,
        checkpoint_dir=checkpoint_dir,
        device_id=0
    )
    
    print(f"Generating video for prompt: {prompt}")
    video = wan_t2v.generate(
        prompt,
        max_area=480*832, # 480p recommended for 1.3B
        frame_num=81,
        sampling_steps=20, # 减少步数以加快测试
        guide_scale=5.0,
        seed=42
    )
    
    output_file = "test_output_cute_kitten.mp4"
    save_video(
        tensor=video[None],
        save_file=output_file,
        fps=16,
        nrow=1,
        normalize=True,
        value_range=(-1, 1)
    )
    print(f"Video saved to {output_file}")

if __name__ == "__main__":
    main()
