#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/speech/speech_func.py
# 作者：whf & Gemini
# 日期：2026-03-06
# 描述：语音识别业务逻辑封装

import os
import json
import asyncio
from pathlib import Path
from fastapi import UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from starlette.websockets import WebSocketState

# 引入项目配置和日志
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.pg_utils import Base
from backend.app.utils.iflytek_asr_client import IFlytekASRClient
from backend.app.utils.qwen_asr_utils import qwen_asr_client
from sqlalchemy import Column, String, Float, DateTime, Text, text
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
    model_version = Column(String(50), default="qwen-asr-1.7b", comment="模型版本")
    status = Column(String(20), default="success", comment="状态")
    error_msg = Column(Text, comment="错误信息")
    created_at = Column(DateTime, server_default=text("NOW()"), comment="创建时间")
    updated_at = Column(DateTime, server_default=text("NOW()"), onupdate=text("NOW()"), comment="更新时间")

class SpeechManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # 构造函数可以保持为空，因为Qwen-ASR客户端是独立的单例
        pass

    async def transcribe_file(self, file: UploadFile, current_user, db) -> dict:
        """
        文件转写 (使用 Qwen-ASR)
        """
        temp_file_path = None
        try:
            # 1. 直接上传文件
            url, local_path, size = await UploadUtils.save_file(file, module="speech")
            logger.info(f"上传的音频文件已保存到: {local_path}")

            # 2. 准备用于识别的文件路径
            if settings.S3_ENABLED:
                # 如果使用 S3 存储，需要下载到本地临时文件
                import tempfile
                import aioboto3
                
                # 创建临时文件
                ext = Path(file.filename).suffix if file.filename else ".wav"
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                    temp_file_path = temp_file.name
                
                # 下载文件从 S3 到临时文件
                session = aioboto3.Session()
                async with session.client(
                    's3',
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY,
                    region_name=settings.S3_REGION_NAME
                ) as s3:
                    await s3.download_file(
                        Bucket=settings.S3_BUCKET_NAME,
                        Key=local_path,
                        Filename=temp_file_path
                    )
                logger.info(f"从 S3 下载文件到临时路径: {temp_file_path}")
                transcribe_path = temp_file_path
            else:
                # 如果使用本地存储，直接使用本地路径
                transcribe_path = local_path

            # 3. 调用 Qwen-ASR 进行转写
            transcription_result = await qwen_asr_client.transcribe(transcribe_path)
            text_result = transcription_result.get("text", "")

            # 4. 存入数据库
            user_id = getattr(current_user, "username", str(current_user.id))
            # 从 local_path 提取 s3_key (如果是 S3 存储)
            object_key = local_path if settings.S3_ENABLED else None
            log_entry = SpeechLog(
                user_id=user_id,
                audio_url=url,
                s3_key=object_key,
                recognition_text=text_result,
                status="success",
                model_version="qwen-asr-1.7b" # 更新模型版本记录
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
            logger.error(f"处理音频文件转写时出错: {e}", exc_info=True)
            # 可以在这里添加更详细的错误日志记录到数据库
            return {"code": 500, "msg": f"处理失败: {str(e)}"}
        finally:
            # 清理临时文件
            if temp_file_path:
                import os
                try:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                        logger.info(f"临时文件已删除: {temp_file_path}")
                except Exception as e:
                    logger.error(f"删除临时文件失败: {e}")

    async def handle_websocket(self, websocket: WebSocket):
        """
        WebSocket 实时转写处理 (讯飞版)
        """
        await websocket.accept()
        logger.info(f"🔌 [Speech] WebSocket 连接建立: {websocket.client}")
        iflytek_client = IFlytekASRClient(
            on_result_callback=lambda res: asyncio.create_task(websocket.send_text(json.dumps(res))),
            on_error_callback=lambda err: asyncio.create_task(websocket.close(code=1011, reason=err))
        )
        await iflytek_client.connect()

        if not iflytek_client._is_connected:
            await websocket.close(code=1011, reason="无法连接到讯飞服务")
            return

        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message:
                    await iflytek_client.send_audio(message["bytes"])
                elif "text" in message and json.loads(message["text"]).get("is_speaking") is False:
                    break
        except WebSocketDisconnect:
            logger.info("🔌 [Speech] 前端 WebSocket 连接断开")
        except Exception as e:
            logger.error(f"❌ [Speech] WebSocket 代理异常: {e}")
        finally:
            await iflytek_client.close()
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
            logger.info("讯飞代理会话结束。")

# 全局单例
speech_service = SpeechManager()
