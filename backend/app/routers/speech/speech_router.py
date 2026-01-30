#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/speech/speech_router.py
# 作者：whf
# 日期：2026-01-30
# 描述：语音识别路由定义

from fastapi import APIRouter, UploadFile, File, WebSocket, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.routers.speech.speech_func import speech_service
from backend.app.utils.logger import logger
from backend.app.utils.dependencies import get_current_active_user, get_db

router = APIRouter()

@router.on_event("startup")
async def startup_event():
    """
    启动时异步初始化模型 (避免阻塞主进程太久，但会占用后台资源)
    """
    # 可以在这里触发下载，或者等第一次请求时触发
    # 考虑到下载可能耗时，建议第一次请求触发或通过专门的管理接口触发
    # 这里我们打印一条日志引导
    logger.info("ℹ️ [Speech] 语音模块已加载，模型将在首次调用时自动检查并下载")

@router.post("/transcribe", summary="上传音频文件转写")
async def transcribe(
    file: UploadFile = File(...),
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传音频文件进行语音转文字
    - **file**: 音频文件
    - **Note**: 结果会自动存入数据库并关联当前用户
    """
    return await speech_service.transcribe_file(file, current_user, db)

@router.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket 实时语音转写
    - 协议: 发送二进制音频流 (PCM/WAV bytes)
    - 控制: 发送 {"is_speaking": false} 结束
    """
    await speech_service.handle_websocket(websocket)

@router.get("/health", summary="语音服务健康检查")
async def health_check():
    """
    检查模型加载状态
    """
    is_loaded = speech_service._model is not None
    return {
        "status": "ok", 
        "device": speech_service.device, 
        "model_loaded": is_loaded,
        "model_path": str(speech_service.BASE_MODEL_DIR)
    }
