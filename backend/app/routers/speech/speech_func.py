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
from starlette.websockets import WebSocketState

# 引入项目配置和日志
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.pg_utils import Base
from backend.app.utils.iflytek_asr_client import IFlytekASRClient
from backend.app.utils.ocr_utils import OcrHelper
from backend.app.routers.upload.upload_func import UserAudio
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
    import torch
    from funasr import AutoModel
    from modelscope import snapshot_download
except ImportError:
    logger.error("缺少 funasr 或 modelscope 依赖，请执行: pip install funasr modelscope torch")
    AutoModel = None
    snapshot_download = None
    torch = None

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
        "asr-streaming": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch-streaming",
        "asr": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        "vad": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        "punc": "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
    }

    # 路径配置
    BASE_MODEL_DIR = settings.BASE_DIR / "app" / "models"
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
        
        # 确保模型目录存在
        if not self.BASE_MODEL_DIR.exists():
            self.BASE_MODEL_DIR.mkdir(parents=True, exist_ok=True)
            
        # 预先创建模型目录结构，以便用户查看
        for model_id in self.MODELS.values():
            # model_id format: namespace/model_name (e.g. iic/speech_paraformer...)
            if "/" in model_id:
                parts = model_id.split("/")
                if len(parts) >= 2:
                     model_dir = self.BASE_MODEL_DIR / parts[0] / parts[1]
                     if not model_dir.exists():
                         model_dir.mkdir(parents=True, exist_ok=True)
                         logger.info(f"📁 [Speech] 创建默认模型目录: {model_dir}")
        
        # 自动选择最空闲的 GPU
        gpu_id = OcrHelper.get_free_gpu_id()
        if gpu_id != -1:
            self.device = f"cuda:{gpu_id}"
            logger.info(f"✅ SpeechManager 使用 GPU: {self.device}")
        else:
            self.device = "cpu"
            logger.warning("⚠️ 未检测到可用 GPU，SpeechManager 将使用 CPU")

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
            logger.info("🚀 [Speech] 开始初始化语音模型...")
            
            # 1. 准备模型路径
            model_paths = {}
            for key, model_id in self.MODELS.items():
                logger.info(f"📥 [Speech] 检查/下载模型: {model_id}")
                try:
                    # modelscope 会自动处理目录结构: cache_dir/namespace/model_name
                    download_path = snapshot_download(model_id, cache_dir=str(self.BASE_MODEL_DIR))
                    model_paths[key] = download_path
                    logger.success(f"✅ [Speech] 模型就绪: {key} -> {download_path}")
                except Exception as e:
                    logger.error(f"❌ [Speech] 模型下载失败 {model_id}: {e}")
                    raise e

            # 2. 加载模型
            logger.info("🔄 [Speech] 正在加载 FunASR 模型...")
            self._model = AutoModel(
                model=model_paths["asr"],
                vad_model=model_paths["vad"],
                punc_model=model_paths["punc"],
                device=self.device,
                disable_update=True,
                nproc=1,
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
            os.makedirs(self.TEMP_DIR, exist_ok=True)
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
            user_id = getattr(current_user, "username", str(current_user))
            
            # 4.1 SpeechLog
            log_entry = SpeechLog(
                user_id=user_id,
                audio_url=url,
                s3_key=object_key,
                recognition_text=text_result,
                duration=duration,
                status="success"
            )
            db.add(log_entry)
            
            # 4.2 UserAudio (资产表)
            user_audio = UserAudio(
                user_id=user_id,
                filename=file.filename,
                s3_key=object_key,
                url=url,
                size=size,
                duration=duration,
                mime_type=file.content_type or "audio/wav",
                module="speech",
                source="upload",
                text_content=text_result,
                meta_data={"task": "asr", "model": "funasr"}
            )
            db.add(user_audio)
            
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
        WebSocket 实时转写处理 (讯飞版) - 最终修复版
        严格区分中间结果与最终结果，确保文本正确累积。
        新增了后端心跳维持，以防止讯飞 15s 超时断开。
        """
        await websocket.accept()
        logger.info(f"🔌 [Speech] WebSocket 连接建立: {websocket.client}")

        # --- 为每个连接维护独立的状态 ---
        final_transcript_parts = []
        interim_transcript = ""
        last_speaker_id = None
        keep_alive_task = None

        # 1. 定义回调与心跳函数
        async def on_result_from_iflytek(result_data: dict):
            """处理从讯飞收到的识别结果，并维护完整稿件"""
            nonlocal last_speaker_id, interim_transcript
            try:
                st_data = result_data.get("cn", {}).get("st", {})
                result_type = st_data.get("type")
                if result_type is None: return

                current_text_parts = []
                current_sentence_speaker = None
                rt_data = st_data.get("rt", [])
                if rt_data:
                    for part in rt_data:
                        ws_data = part.get("ws", [])
                        for word_info in ws_data:
                            cw_data = word_info.get("cw", [])
                            for char_info in cw_data:
                                current_text_parts.append(char_info.get("w", ""))
                                # 实时追踪本句的说话人ID
                                rl = char_info.get("rl")
                                if rl and rl != "0":
                                    current_sentence_speaker = rl
                
                current_text = "".join(current_text_parts)
                speaker_prefix = ""

                # 核心逻辑：判断是否发生了说话人切换
                if current_sentence_speaker and current_sentence_speaker != last_speaker_id:
                    speaker_prefix = f"\n\n发言人 {current_sentence_speaker}: "
                    last_speaker_id = current_sentence_speaker
                    # 如果切换了说话人，之前的中间结果需要作废，因为属于上一个人
                    interim_transcript = ""

                if result_type == "0": # 确定性结果
                    final_transcript_parts.append(speaker_prefix + current_text)
                    interim_transcript = "" # 清空草稿
                elif result_type == "1": # 中间结果
                    # 如果是新说话人，interim_transcript 已被清空，speaker_prefix会带上新前缀
                    # 如果是同一人，speaker_prefix为空，直接更新草稿
                    interim_transcript = speaker_prefix + current_text

                # 拼接完整稿件并发送 (最终稿 + 当前草稿)
                full_transcript = "".join(final_transcript_parts) + interim_transcript
                await websocket.send_text(json.dumps({"text": full_transcript}))
                    
            except Exception as e:
                logger.error(f"处理讯飞结果时出错: {e} | {traceback.format_exc()}")

        async def on_error_from_iflytek(error_message):
            """处理从讯飞收到的错误"""
            logger.error(f"讯飞客户端报告错误: {error_message}")
            if websocket.client_state != WebSocketState.DISCONNECTED:
                try:
                    await websocket.close(code=1011, reason=f"ASR service error: {error_message}")
                except RuntimeError:
                    pass

        async def send_keep_alive(iflytek_client):
            """每10秒发送一次静音数据以维持与讯飞的连接。"""
            silent_chunk = b'\x00' * 1280  # 1280字节的静音数据
            while True:
                try:
                    await asyncio.sleep(10)
                    if iflytek_client._is_connected:
                        logger.info("🎤 [Speech] 发送静音心跳包维持连接...")
                        await iflytek_client.send_audio(silent_chunk)
                except asyncio.CancelledError:
                    logger.info("🎤 [Speech] 静音心跳任务已取消。")
                    break
                except Exception as e:
                    logger.error(f"🎤 [Speech] 静音心跳任务异常: {e}")
                    break

        # 2. 初始化并连接讯飞客户端
        iflytek_client = IFlytekASRClient(
            on_result_callback=on_result_from_iflytek,
            on_error_callback=on_error_from_iflytek
        )
        await iflytek_client.connect()

        if not iflytek_client._is_connected:
            await websocket.close(code=1011, reason="无法连接到讯飞服务")
            return

        # 3. 循环处理客户端消息
        try:
            while True:
                message = await websocket.receive()
                
                if "bytes" in message:
                    if keep_alive_task and not keep_alive_task.done():
                        logger.info("🎤 [Speech] 收到音频数据，停止静音心跳。")
                        keep_alive_task.cancel()
                        keep_alive_task = None
                    audio_chunk = message["bytes"]
                    await iflytek_client.send_audio(audio_chunk)
                
                elif "text" in message:
                    try:
                        data = json.loads(message["text"])
                        action = data.get("action")

                        if action == "pause":
                            if not keep_alive_task or keep_alive_task.done():
                                logger.info("🎤 [Speech] 前端请求暂停，启动静音心跳任务。")
                                keep_alive_task = asyncio.create_task(send_keep_alive(iflytek_client))
                        elif action == "resume":
                            if keep_alive_task and not keep_alive_task.done():
                                logger.info("🎤 [Speech] 前端请求恢复，停止静音心跳任务。")
                                keep_alive_task.cancel()
                                keep_alive_task = None
                        
                        if data.get("is_speaking") is False:
                            logger.info("收到前端结束信号，准备关闭连接。")
                            break
                    except json.JSONDecodeError:
                        logger.warning(f"收到无法解析的文本消息: {message['text']}")

        except WebSocketDisconnect:
            logger.info("🔌 [Speech] 前端 WebSocket 连接断开")
        except Exception as e:
            logger.error(f"❌ [Speech] WebSocket 代理异常: {e}")
        finally:
            if keep_alive_task and not keep_alive_task.done():
                keep_alive_task.cancel()
            await iflytek_client.close()
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
            logger.info("讯飞代理会话结束。")

# 全局单例
speech_service = SpeechManager()




