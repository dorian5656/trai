#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/speech/speech_router.py
# 作者：whf
# 日期：2026-01-30
# 描述：语音识别路由定义

from fastapi import APIRouter, UploadFile, File, WebSocket, BackgroundTasks, Depends, Query
from backend.app.utils.dependencies import get_current_active_user, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.routers.speech.speech_func import speech_service
from backend.app.utils.logger import logger
from backend.app.utils.dependencies import get_current_active_user, get_db
from datetime import datetime





router = APIRouter()

@router.post("/transcribe_file", summary="上传音频文件进行转写(QwenASR)")
async def transcribe_file(
    current_user = Depends(get_current_active_user),
    file: UploadFile = File(...),
):
    """
    使用QwenASR上传音频文件进行语音转文字

    Args:
        current_user (User): 当前用户
        file (UploadFile): 音频文件

    Returns:
        dict: 转写结果
    """
    return await speech_service.transcribe_audio_file(user_id=str(current_user.id), file=file)

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

@router.get("/transcriptions", summary="获取语音识别结果列表")
async def get_transcriptions(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    start_time: datetime = Query(None, description="开始时间"),
    end_time: datetime = Query(None, description="结束时间"),
    status: str = Query(None, description="状态过滤")
):
    """
    获取语音识别结果列表

    Args:
        current_user (User): 当前用户
        db (AsyncSession): 数据库会话
        page (int): 页码，默认1
        size (int): 每页数量，默认10
        start_time (datetime): 开始时间
        end_time (datetime): 结束时间
        status (str): 状态过滤

    Returns:
        dict: 识别结果列表和分页信息
    """
    return await speech_service.get_transcriptions(
        user_id=str(current_user.id),
        db=db,
        page=page,
        size=size,
        start_time=start_time,
        end_time=end_time,
        status=status
    )

@router.get("/transcriptions/{transcription_id}", summary="获取单个语音识别结果")
async def get_transcription(
    transcription_id: str,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个语音识别结果详情

    Args:
        transcription_id (str): 识别记录ID
        current_user (User): 当前用户
        db (AsyncSession): 数据库会话

    Returns:
        dict: 识别结果详情
    """
    return await speech_service.get_transcription(
        transcription_id=transcription_id,
        user_id=str(current_user.id),
        db=db
    )
