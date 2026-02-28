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
    启动时异步初始化模型 (后台预加载)
    """
    import asyncio
    logger.info("ℹ️ [Speech] 触发语音模型后台预加载...")
    # 使用 create_task 在后台加载，不阻塞服务启动
    asyncio.create_task(speech_service.initialize())

@router.post("/transcribe", summary="上传音频文件转写")
async def transcribe(
    file: UploadFile = File(...),
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传音频文件进行语音转文字
    
    Args:
        file (UploadFile): 音频文件 (支持 mp3, wav, m4a 等格式)
        current_user (User): 当前登录用户
        db (AsyncSession): 数据库会话
    
    Returns:
        dict: 转写结果，包含文本内容和元数据
    """
    return await speech_service.transcribe_file(file, current_user, db)

@router.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket 实时语音转写

    Args:
        websocket (WebSocket): WebSocket 连接对象

    Protocol:
        - Client 发送: 二进制音频流 (PCM/WAV bytes)
        - Client 控制: 发送 {"is_speaking": false} 结束
        - Server 返回: 实时转写文本

    Returns:
        None
    """
    await speech_service.handle_websocket(websocket)

@router.get("/health", summary="语音服务健康检查")
async def health_check():
    """
    检查模型加载状态

    Returns:
        dict: 服务状态信息
            - status (str): "ok"
            - device (str): 运行设备 (cuda/cpu)
            - model_loaded (bool): 模型是否已加载
            backend/app/routers/upload- model_path (str): 模型路径
    """
    is_loaded = speech_service._model is not None
    return {
        "status": "ok", 
        "device": speech_service.device, 
        "model_loaded": is_loaded,
        "model_path": str(speech_service.BASE_MODEL_DIR)
    }
