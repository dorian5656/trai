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

        # 用于追踪当前说话人
        current_speaker_id = 0

        async def forward_result_to_client(res):
            """解析讯飞结果，处理说话人角色，并转发给前端"""
            nonlocal current_speaker_id
            try:
                logger.info(f"🎤 [讯飞原始结果]: {res}")
                st = res.get("cn", {}).get("st", {})
                if not st:
                    return

                text_parts = []
                new_speaker_id = current_speaker_id
                speaker_has_changed_in_this_message = False

                # 预扫描，检查并更新说话人ID
                for rt_item in st.get("rt", []):
                    for ws_item in rt_item.get("ws", []):
                        for cw_item in ws_item.get("cw", []):
                            text_parts.append(cw_item.get("w", ""))
                            rl = int(cw_item.get("rl", 0))
                            if rl > 0 and rl != new_speaker_id:
                                new_speaker_id = rl
                                speaker_has_changed_in_this_message = True
                
                combined_text = "".join(text_parts)

                # 只有在 speaker 确实改变时才更新全局状态
                if speaker_has_changed_in_this_message:
                    current_speaker_id = new_speaker_id

                # 构建发送给前端的新数据结构
                new_payload = {
                    "type": st.get("type"), # '0' or '1'
                    "text": combined_text,
                    "speaker": new_speaker_id, # 使用本次消息中最新的 speaker_id
                    "speaker_changed": speaker_has_changed_in_this_message
                }

                logger.info(f"🎤 [讯飞结果-处理后]: {json.dumps(new_payload, ensure_ascii=False)}")
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(json.dumps(new_payload))

            except Exception as e:
                logger.error(f"解析并转发讯飞结果时出错: {e}", exc_info=True)


        async def handle_error(err):
            """处理错误，记录日志但不主动关闭连接（由 finally 统一处理）"""
            logger.error(f"讯飞客户端报错: {err}")

        iflytek_client = IFlytekASRClient(
            on_result_callback=lambda res: asyncio.create_task(forward_result_to_client(res)),
            on_error_callback=lambda err: asyncio.create_task(handle_error(err))
        )
        await iflytek_client.connect()

        if not iflytek_client._is_connected:
            await websocket.close(code=1011, reason="无法连接到讯飞服务")
            return

        is_paused = False
        silence_task = None
        silence_audio = b'\x00' * 1280

        async def send_silence_periodically():
            """暂停期间定期发送静音音频，维持与讯飞的连接"""
            while is_paused and iflytek_client._is_connected:
                try:
                    await iflytek_client.send_audio(silence_audio)
                    await asyncio.sleep(0.04)
                except Exception as e:
                    logger.error(f"发送静音音频失败: {e}")
                    break

        last_receive_time = asyncio.get_event_loop().time()
        
        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=14.0
                    )
                    last_receive_time = asyncio.get_event_loop().time()
                except asyncio.TimeoutError:
                    # 14 秒未收到数据，发送静音维持连接
                    logger.debug("⚠️ [Speech] 前端超过 14 秒未发送音频，发送静音数据维持连接")
                    await iflytek_client.send_audio(silence_audio)
                    continue
                    
                if "bytes" in message:
                    if not is_paused:
                        await iflytek_client.send_audio(message["bytes"])
                elif "text" in message:
                    text_data = json.loads(message["text"])
                    action = text_data.get("action")
                    
                    if action == "pause":
                        is_paused = True
                        silence_task = asyncio.create_task(send_silence_periodically())
                        logger.info("⏸️ [Speech] 录音已暂停，开始发送静音维持连接")
                    elif action == "resume":
                        is_paused = False
                        if silence_task:
                            silence_task.cancel()
                            try:
                                await silence_task
                            except asyncio.CancelledError:
                                pass
                            silence_task = None
                        logger.info("▶️ [Speech] 录音已恢复")
                    elif text_data.get("is_speaking") is False:
                        break
        except WebSocketDisconnect:
            logger.info("🔌 [Speech] 前端 WebSocket 连接断开")
        except Exception as e:
            logger.error(f"❌ [Speech] WebSocket 代理异常: {e}")
        finally:
            if silence_task:
                silence_task.cancel()
            await iflytek_client.close()
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
            logger.info("讯飞代理会话结束。")

    async def get_transcriptions(self, user_id, db, page=1, size=10, start_time=None, end_time=None, status=None):
        """
        获取语音识别结果列表
        """
        try:
            from sqlalchemy import select, and_, or_
            from sqlalchemy.sql import func

            # 构建查询
            query = select(SpeechLog).where(SpeechLog.user_id == user_id)

            # 添加时间范围过滤
            if start_time:
                query = query.where(SpeechLog.created_at >= start_time)
            if end_time:
                query = query.where(SpeechLog.created_at <= end_time)

            # 添加状态过滤
            if status:
                query = query.where(SpeechLog.status == status)

            # 计算总数
            count_query = select(func.count()).select_from(query.subquery())
            total = await db.scalar(count_query)

            # 分页
            offset = (page - 1) * size
            query = query.order_by(SpeechLog.created_at.desc()).offset(offset).limit(size)

            # 执行查询
            result = await db.execute(query)
            logs = result.scalars().all()

            # 构建响应数据
            items = []
            for log in logs:
                items.append({
                    "id": str(log.id),
                    "audio_url": log.audio_url,
                    "recognition_text": log.recognition_text,
                    "duration": log.duration,
                    "model_version": log.model_version,
                    "status": log.status,
                    "error_msg": log.error_msg,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                    "updated_at": log.updated_at.isoformat() if log.updated_at else None
                })

            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "items": items,
                    "page": page,
                    "size": size,
                    "total": total
                }
            }

        except Exception as e:
            logger.error(f"获取语音识别结果列表失败: {e}")
            return {"code": 500, "msg": f"获取失败: {str(e)}"}

    async def get_transcription(self, transcription_id, user_id, db):
        """
        获取单个语音识别结果详情
        """
        try:
            from sqlalchemy import select, and_

            # 构建查询
            query = select(SpeechLog).where(
                and_(
                    SpeechLog.id == transcription_id,
                    SpeechLog.user_id == user_id
                )
            )

            # 执行查询
            result = await db.execute(query)
            log = result.scalar_one_or_none()

            if not log:
                return {"code": 404, "msg": "识别记录不存在"}

            # 构建响应数据
            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "id": str(log.id),
                    "audio_url": log.audio_url,
                    "s3_key": log.s3_key,
                    "recognition_text": log.recognition_text,
                    "duration": log.duration,
                    "model_version": log.model_version,
                    "status": log.status,
                    "error_msg": log.error_msg,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                    "updated_at": log.updated_at.isoformat() if log.updated_at else None
                }
            }

        except Exception as e:
            logger.error(f"获取语音识别结果详情失败: {e}")
            return {"code": 500, "msg": f"获取失败: {str(e)}"}

# 全局单例
speech_service = SpeechManager()
