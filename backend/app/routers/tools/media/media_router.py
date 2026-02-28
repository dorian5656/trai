#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/tools/media/media_router.py
# 作者：liuhd
# 日期：2026-02-12 11:35:00
# 描述：媒体工具路由定义

from fastapi import APIRouter, UploadFile, File, Form, Depends, Query
from backend.app.routers.tools.media.media_func import MediaFunc
from backend.app.utils.dependencies import get_current_active_user

router = APIRouter()

@router.post("/video2gif", summary="视频转 GIF", description="上传视频文件，转换为 GIF 并返回下载链接")
async def convert_video_to_gif(
    file: UploadFile = File(..., description="视频文件 (支持 .mp4, .avi, .mov, .mkv; 最大 50MB)"),
    fps: int = Query(10, description="帧率 (FPS)，建议 5-20，数值越大文件越大"),
    width: int = Query(320, description="宽度 (px)，建议 320-640，数值越大文件越大"),
    current_user = Depends(get_current_active_user)
):
    """
    **视频转 GIF 接口**

    将上传的视频文件转换为 GIF 动图。
    
    **功能特性**:
    - ✅ 支持格式: .mp4, .avi, .mov, .mkv
    - ✅ 自动压缩: 可调节 FPS 和 宽度 以控制输出大小
    - ✅ 云端存储: 转换结果自动上传至 S3/MinIO
    - ✅ 消息通知: 转换完成后发送飞书通知
    - ✅ 记录留痕: 操作记录自动写入数据库

    **参数说明**:
    - `file`: 视频文件 (Max 50MB)
    - `fps`: 帧率 (默认 10)
    - `width`: 宽度像素 (默认 320)
    
    **返回**:
    - `url`: GIF 下载链接
    - `duration`: 转换耗时
    """
    # 使用当前登录用户的 username 作为 user_id
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await MediaFunc.convert_video_to_gif(file, user_id=user_id, fps=fps, width=width)
