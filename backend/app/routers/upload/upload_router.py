#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/upload/upload_router.py
# 作者：whf
# 日期：2026-01-27
# 描述：文件上传路由

from fastapi import APIRouter, UploadFile, File, Form, Depends, Body, HTTPException, Query
from fastapi.responses import StreamingResponse
from backend.app.routers.upload.upload_func import UploadResponse, ChunkInitResponse, ChunkMergeResponse
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.feishu_utils import feishu_bot
from backend.app.utils.dependencies import get_current_active_user
from backend.app.utils.logger import logger
import uuid

router = APIRouter()

from backend.app.utils.pg_utils import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.routers.upload.upload_func import UserImage, UserAudio

# =============================================================================
# 分片上传相关路由
# =============================================================================

@router.post("/chunk/init", response_model=ChunkInitResponse, summary="初始化分片上传")
async def init_chunk_upload(
    filename: str = Body(..., embed=True),
    current_user = Depends(get_current_active_user)
):
    """
    初始化分片上传任务
    
    返回 upload_id，后续分片上传需携带此 ID。
    同时检查是否有已存在的断点（断点续传），返回已上传的分片索引。
    """
    # 简单生成 upload_id，实际可以使用 hash(filename + user_id + size) 来支持更严格的断点检测
    # 这里为了演示，直接生成新的 ID，或者如果用户传了 MD5 更好。
    # 为了支持简单的"同名文件断点续传"，我们可以尝试用 hash
    upload_id = str(uuid.uuid4())
    
    # 检查是否有历史残留 (暂时不自动关联旧 ID，由前端管理 upload_id 或此处不做复杂逻辑)
    # 如果前端想续传，应该在客户端缓存 upload_id。
    # 这里我们假设是新的上传，或者前端通过其他方式（如 MD5）向后端查询进度。
    
    # 获取已上传分片 (对于新生成的 upload_id 肯定是空的)
    uploaded_chunks = UploadUtils.get_uploaded_chunks(upload_id)
    
    logger.info(f"用户 {current_user.username} 初始化分片上传: {filename} -> {upload_id}")
    
    return ChunkInitResponse(
        upload_id=upload_id,
        uploaded_chunks=uploaded_chunks
    )

@router.get("/chunk/progress", summary="查询上传进度 (断点续传)")
async def get_chunk_progress(
    upload_id: str = Query(..., description="上传任务ID"),
    current_user = Depends(get_current_active_user)
):
    """
    查询指定 upload_id 的上传进度
    """
    uploaded_chunks = UploadUtils.get_uploaded_chunks(upload_id)
    return {"upload_id": upload_id, "uploaded_chunks": uploaded_chunks}

@router.post("/chunk/upload", summary="上传单个分片")
async def upload_chunk(
    upload_id: str = Form(...),
    part_number: int = Form(..., description="分片序号 (从1开始)"),
    file: UploadFile = File(...),
    current_user = Depends(get_current_active_user)
):
    """
    上传单个分片文件
    """
    # 读取分片数据
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="分片数据为空")
        
    chunk_path = await UploadUtils.save_chunk(upload_id, part_number, data)
    
    return {"status": "success", "upload_id": upload_id, "part_number": part_number, "size": len(data)}

@router.post("/chunk/merge", response_model=ChunkMergeResponse, summary="合并分片")
async def merge_chunks(
    upload_id: str = Body(...),
    filename: str = Body(...),
    total_parts: int = Body(...),
    module: str = Body("common"),
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    所有分片上传完成后，调用此接口进行合并
    """
    logger.info(f"用户 {current_user.username} 请求合并分片: {upload_id}, 文件名: {filename}, 总分片: {total_parts}")
    
    # 1. 执行合并
    url, local_path, size = await UploadUtils.merge_chunks(upload_id, filename, total_parts, module)
    
    # 2. 记录到数据库 (复用 upload_file 的逻辑)
    try:
        ext = filename.lower().split('.')[-1] if '.' in filename else ""
        is_audio = False
        if f".{ext}" in UploadUtils.ALLOWED_EXTENSIONS.get('audio', {}):
            is_audio = True
            
        if is_audio:
            new_audio = UserAudio(
                user_id=current_user.username,
                filename=filename,
                s3_key=local_path,
                url=url,
                size=size,
                mime_type=f"audio/{ext}", # 简易判断
                module=module,
                source="chunk_upload"
            )
            db.add(new_audio)
            await db.commit()
            await db.refresh(new_audio)
        else:
            new_image = UserImage(
                user_id=current_user.username,
                filename=filename,
                s3_key=local_path,
                url=url,
                size=size,
                mime_type=f"application/octet-stream", # 暂时无法准确获取
                module=module,
                source="chunk_upload"
            )
            db.add(new_image)
            await db.commit()
            await db.refresh(new_image)
            
        logger.info(f"分片合并文件已记录到数据库")
        
        # 发送飞书通知
        feishu_bot.send_file_upload_card(filename, url, current_user.username, size)
        
    except Exception as e:
        logger.error(f"保存分片记录失败: {e}")
        # 不阻断返回
        
    return ChunkMergeResponse(
        url=url,
        filename=filename,
        size=size
    )

@router.post("/common", response_model=UploadResponse, summary="通用文件上传")
async def upload_file(
    file: UploadFile = File(...),
    module: str = Form("common", description="业务模块名称 (如 avatar, chat)"),
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传文件到服务器

    **Args:**

    - `file` (UploadFile): 文件对象
    - `module` (str): 模块名称 (决定存储子目录)
    - `current_user` (User): 当前登录用户
    - `db` (AsyncSession): 数据库会话

    **Returns:**

    - `UploadResponse`: 上传结果
        - `url` (str): 文件的静态访问路径
        - `filename` (str): 原始文件名
        - `size` (int): 文件大小
        - `content_type` (str): MIME类型
        - `local_path` (str): 存储路径
    """
    logger.info(f"用户 {current_user.username} 正在上传文件: {file.filename} (Module: {module})")
    
    url, local_path, size = await UploadUtils.save_file(file, module)
    
    # 记录到数据库
    try:
        # 判断文件类型
        content_type = file.content_type or "application/octet-stream"
        is_audio = content_type.startswith("audio/")
        
        # 二次检查扩展名 (防止 MIME 类型不准)
        if not is_audio and file.filename:
            ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ""
            if f".{ext}" in UploadUtils.ALLOWED_EXTENSIONS.get('audio', {}):
                is_audio = True
        
        if is_audio:
            # 保存到音频表
            new_audio = UserAudio(
                user_id=current_user.username,
                filename=file.filename,
                s3_key=local_path,
                url=url,
                size=size,
                mime_type=content_type,
                module=module,
                source="upload"
            )
            db.add(new_audio)
            await db.commit()
            await db.refresh(new_audio)
            logger.info(f"音频记录已保存到数据库: {new_audio.id}")
        else:
            # 默认保存到图片表 (兼容旧逻辑，且 UserImage 实际上作为通用文件表使用)
            # 只有明确是音频才去 audio 表
            new_image = UserImage(
                user_id=current_user.username,
                filename=file.filename,
                s3_key=local_path, # local_path 在 S3 模式下是 object_name
                url=url,
                size=size,
                mime_type=content_type,
                module=module,
                source="upload"
            )
            db.add(new_image)
            await db.commit()
            await db.refresh(new_image)
            logger.info(f"文件记录已保存到数据库: {new_image.id}")

        # 发送飞书通知
        feishu_bot.send_file_upload_card(file.filename, url, current_user.username, size)
            
    except Exception as e:
        logger.error(f"保存文件记录失败: {e}")
        # 注意：这里不应该回滚文件上传，但需要记录错误
    
    return UploadResponse(
        url=url,
        filename=file.filename,
        size=size,
        content_type=file.content_type,
        local_path=local_path
    )

@router.get("/files/{file_path:path}", summary="文件代理下载")
async def download_file(file_path: str):
    """
    代理下载文件 (用于解决内网 S3 无法直接访问的问题)

    **Args:**

    - `file_path` (str): 文件路径 (如 common/20260127/abc.png)

    **Returns:**

    - `StreamingResponse`: 文件流
    """
    logger.info(f"正在代理下载文件: {file_path}")
    
    # 简单的 MIME 类型推断
    media_type = "application/octet-stream"
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        media_type = f"image/{file_path.split('.')[-1]}"
    elif file_path.lower().endswith('.pdf'):
        media_type = "application/pdf"
        
    return StreamingResponse(
        UploadUtils.get_file_stream(file_path),
        media_type=media_type
    )

from typing import List
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import select, desc

class ImageInfo(BaseModel):
    id: str
    filename: str
    url: str
    created_at: datetime

@router.get("/list", response_model=List[ImageInfo], summary="获取我的图片列表")
async def list_my_images(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户的图片上传历史 (最近50条)
    """
    result = await db.execute(
        select(UserImage)
        .where(UserImage.user_id == current_user.username)
        .order_by(desc(UserImage.created_at))
        .limit(50)
    )
    images = result.scalars().all()
    
    return [
        ImageInfo(
            id=str(img.id),
            filename=img.filename,
            url=img.url,
            created_at=img.created_at
        )
        for img in images
    ]
