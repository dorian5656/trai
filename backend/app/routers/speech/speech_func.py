#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/speech/speech_func.py
# 作者：whf
# 日期：2026-01-30
# 描述：语音识别业务逻辑封装

import os
import sys
import shutil
import uuid
import json
import traceback
import asyncio
import numpy as np
from pathlib import Path
from fastapi import UploadFile, WebSocket, WebSocketDisconnect

# 引入项目配置和日志
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.pg_utils import Base
from sqlalchemy import Column, String, Float, DateTime, Text, Boolean, text
from sqlalchemy.dialects.postgresql import UUID

class SpeechLog(Base):
    """语音识别记录表"""
    __tablename__ = "speech_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(String(50), nullable=False, comment="用户ID")
    audio_url = Column(Text, nullable=False, comment="音频URL")
    s3_key = Column(String(500), comment="S3 Key")
    recognition_text = Column(Text, comment="识别结果")
    duration = Column(Float, comment="时长(秒)")
    model_version = Column(String(50), default="funasr-paraformer", comment="模型版本")
    status = Column(String(20), default="success", comment="状态")
    error_msg = Column(Text, comment="错误信息")
    created_at = Column(DateTime, server_default=text("NOW()"), comment="创建时间")
    updated_at = Column(DateTime, server_default=text("NOW()"), onupdate=text("NOW()"), comment="更新时间")

# 引入模型相关库
try:
    from funasr import AutoModel
    from modelscope import snapshot_download
except ImportError:
    logger.error("缺少 funasr 或 modelscope 依赖，请执行: pip install funasr modelscope")
    AutoModel = None
    snapshot_download = None

class SpeechManager:
    """
    语音识别管理器 (单例模式)
    负责模型加载、推理和资源管理
    """
    _instance = None
    _model = None
    _is_loading = False

    # 模型配置
    MODELS = {
        "asr": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        "vad": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        "punc": "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"
    }

    # 路径配置
    BASE_MODEL_DIR = settings.BASE_DIR / "app" / "models" / "speech_model"
    TEMP_DIR = settings.BASE_DIR / "temp"

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # 确保临时目录存在
        if not self.TEMP_DIR.exists():
            self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
        # 强制 CPU 配置 (参考原 1.py)
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        self.device = "cpu"

    async def initialize(self):
        """
        初始化模型：检查本地模型是否存在，不存在则下载，然后加载
        """
        if self._model:
            logger.info("✅ [Speech] 模型已加载，跳过初始化")
            return

        if self._is_loading:
            logger.warning("⚠️ [Speech] 模型正在加载中，请稍候...")
            while self._is_loading:
                await asyncio.sleep(1)
            return

        self._is_loading = True
        try:
            logger.info("🚀 [Speech] 开始初始化语音模型 (CPU模式)...")
            
            # 1. 准备模型路径
            model_paths = {}
            for key, model_id in self.MODELS.items():
                # 使用模型ID的最后一部分作为本地目录名
                local_name = model_id.split("/")[-1]
                local_path = self.BASE_MODEL_DIR / local_name
                
                # 检查是否已存在
                if not local_path.exists():
                    logger.info(f"📥 [Speech] 模型未找到，开始下载: {model_id} -> {local_path}")
                    try:
                        # 自动下载到指定目录
                        download_path = snapshot_download(model_id, cache_dir=str(self.BASE_MODEL_DIR))
                        # snapshot_download 默认会下载到 cache_dir/model_id，我们需要确认实际路径
                        # 这里直接使用 snapshot_download 返回的路径即可
                        model_paths[key] = download_path
                        logger.success(f"✅ [Speech] 模型下载完成: {key}")
                    except Exception as e:
                        logger.error(f"❌ [Speech] 模型下载失败 {model_id}: {e}")
                        raise e
                else:
                    # 如果手动放置了目录，尝试直接使用 (需符合 funasr 结构)
                    # 为兼容 snapshot_download 的缓存结构，建议还是通过 snapshot_download 检查
                    # 这里为了稳健，我们再次调用 snapshot_download，它会自动跳过已下载的文件
                    logger.info(f"🔍 [Speech] 校验本地模型: {local_path}")
                    model_paths[key] = snapshot_download(model_id, cache_dir=str(self.BASE_MODEL_DIR))

            # 2. 加载模型
            logger.info("🔄 [Speech] 正在加载 FunASR 模型...")
            self._model = AutoModel(
                model=model_paths["asr"],
                vad_model=model_paths["vad"],
                punc_model=model_paths["punc"],
                device=self.device,
                disable_update=True,  # 已手动下载，禁止自动更新
                nproc=1,              # CPU 单进程
                trust_remote_code=False,
                disable_pbar=True
            )
            logger.success("✅ [Speech] 模型加载成功！")

        except Exception as e:
            logger.error(f"❌ [Speech] 模型加载失败: {traceback.format_exc()}")
            self._model = None
        finally:
            self._is_loading = False

    async def transcribe_file(self, file: UploadFile, current_user, db) -> dict:
        """
        文件转写 (含 S3 上传和 DB 记录)
        """
        if not self._model:
            await self.initialize()
            if not self._model:
                return {"status": "error", "message": "模型加载失败，请查看后台日志"}

        # 1. 上传文件到 S3 / 本地
        try:
            # 假设存储在 speech 模块下
            url, object_key, size = await UploadUtils.save_file(file, module="speech")
        except Exception as e:
            logger.error(f"❌ [Speech] 文件上传失败: {e}")
            return {"status": "error", "message": f"文件上传失败: {str(e)}"}

        # 2. 准备本地临时文件用于推理 (因为 funasr 需要本地路径)
        # 如果是 S3 模式，save_file 返回的是 key，我们需要重新下载流或者
        # 为了性能，我们在上传前/后保留一个本地副本用于推理？
        # UploadUtils.save_file 会关闭 file stream。
        # 我们可以修改 UploadUtils 或者在这里重新获取流。
        # 简单起见：
        # 方案 A: 使用 save_file 返回的 url (如果是 http) -> 不行，funasr 需要本地路径
        # 方案 B: 再次读取 file (UploadFile 支持 seek(0) 吗？spooled file 可以)
        # 方案 C: 先保存到 temp，然后上传 S3，然后推理。
        
        # 重新 seek file (UploadUtils.save_file 会 close 吗？check UploadUtils code)
        # UploadUtils code shows `await file.close()` in finally block. 
        # So file is closed. We cannot read it again.
        
        # Strategy: We must read content first, or modify UploadUtils.
        # But we can't easily modify UploadUtils without affecting others.
        # Alternative: We can use `UploadUtils.get_file_stream(object_key)` to download it back to temp.
        
        temp_file_path = self.TEMP_DIR / f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
        
        try:
            # 从 S3/Local 下载回临时文件用于推理
            # 或者，更高效的做法是：我们自己先存 temp，然后传给 UploadUtils (但 UploadUtils 接收 UploadFile)
            # Let's use get_file_stream to be safe and compatible with S3
            
            # Write temp file from S3/Local stream
            with open(temp_file_path, "wb") as f:
                 async for chunk in UploadUtils.get_file_stream(object_key):
                     f.write(chunk)
            
            # 3. 推理
            logger.info(f"🎤 [Speech] 开始转写文件: {file.filename}")
            # 计算时长 (可选，需要音频库)
            duration = 0.0 
            
            res = self._model.generate(input=str(temp_file_path), batch_size_s=300)
            text_result = res[0].get("text", "") if (res and len(res) > 0) else ""
            
            # 4. 存入数据库
            log_entry = SpeechLog(
                user_id=current_user.username, # 假设 current_user 有 username
                audio_url=url,
                s3_key=object_key,
                recognition_text=text_result,
                duration=duration,
                status="success"
            )
            db.add(log_entry)
            await db.commit()
            await db.refresh(log_entry)
            
            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "text": text_result,
                    "url": url,
                    "id": str(log_entry.id)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ [Speech] 处理出错: {e}")
            # 记录失败日志
            try:
                err_log = SpeechLog(
                    user_id=current_user.username,
                    audio_url=url, # URL 依然有效
                    s3_key=object_key,
                    recognition_text="",
                    status="failed",
                    error_msg=str(e)
                )
                db.add(err_log)
                await db.commit()
            except:
                pass
                
            return {"code": 500, "msg": f"处理失败: {str(e)}"}
            
        finally:
            # 清理临时文件
            if temp_file_path.exists():
                os.remove(temp_file_path)

    async def handle_websocket(self, websocket: WebSocket):
        """
        WebSocket 实时转写处理
        """
        await websocket.accept()
        logger.info(f"🔌 [Speech] WebSocket 连接建立: {websocket.client}")

        if not self._model:
            await self.initialize()
            if not self._model:
                await websocket.close(code=1011, reason="模型未加载")
                return

        audio_buffer = bytearray()
        try:
            while True:
                message = await websocket.receive()
                
                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                        # 支持结束信号
                        if not data.get("is_speaking", True):
                            break
                    except:
                        pass
                
                elif "bytes" in message:
                    audio_chunk = message["bytes"]
                    audio_buffer.extend(audio_chunk)
                    
                    # 简单的缓冲策略：每积攒一定量数据进行一次快速推理 (模拟流式，实际是伪流式)
                    # 原 1.py 逻辑：len(audio_buffer) % 32000 < len(audio_chunk)
                    # 这里的逻辑是大约每 1-2 秒的数据推一次
                    if len(audio_buffer) % 32000 < len(audio_chunk):
                        audio_np = np.frombuffer(audio_buffer, dtype=np.int16).astype(np.float32)
                        # 注意：AutoModel 的 generate 在 CPU 上可能较慢，频繁调用会阻塞
                        # 这里沿用原逻辑
                        res = self._model.generate(input=audio_np, batch_size_s=300)
                        text = res[0].get("text", "") if (res and len(res) > 0) else ""
                        
                        if text:
                            await websocket.send_text(json.dumps({
                                "text": text,
                                "mode": "2pass-online",
                                "is_final": False
                            }))

        except WebSocketDisconnect:
            logger.info("🔌 [Speech] WebSocket 连接断开")
        except Exception as e:
            logger.error(f"❌ [Speech] WebSocket 异常: {e}")
        finally:
            # 最终处理（处理剩余 buffer）
            if len(audio_buffer) > 0 and self._model:
                try:
                    audio_np = np.frombuffer(audio_buffer, dtype=np.int16).astype(np.float32)
                    res = self._model.generate(input=audio_np, batch_size_s=300)
                    text = res[0].get("text", "") if (res and len(res) > 0) else ""
                    await websocket.send_text(json.dumps({
                        "text": text,
                        "mode": "2pass-offline",
                        "is_final": True
                    }))
                except Exception as e:
                    logger.error(f"❌ [Speech] 最终推理失败: {e}")

# 全局单例
speech_service = SpeechManager()
