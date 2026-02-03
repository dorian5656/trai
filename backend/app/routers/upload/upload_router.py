#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/upload/upload_router.py
# 作者：whf
# 日期：2026-01-27
# 描述：文件上传路由

from fastapi import APIRouter, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from backend.app.routers.upload.upload_func import UploadResponse
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.dependencies import get_current_active_user
from backend.app.utils.logger import logger

router = APIRouter()

from backend.app.utils.pg_utils import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.routers.upload.upload_func import UserImage, UserAudio

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
    page: int = 1,
    size: int = 20,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户上传的图片列表

    **Args:**

    - `page` (int): 页码
    - `size` (int): 每页数量
    - `current_user` (User): 当前登录用户
    - `db` (AsyncSession): 数据库会话

    **Returns:**

    - `List[ImageInfo]`: 图片信息列表
    """
    stmt = (
        select(UserImage)
        .where(UserImage.user_id == current_user.username)
        .where(UserImage.is_deleted == False)
        .order_by(desc(UserImage.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(stmt)
    images = result.scalars().all()
    
    return [
        ImageInfo(
            id=str(img.id),
            filename=img.filename,
            url=img.url,
            created_at=img.created_at
        ) for img in images
    ]

class DeleteImageRequest(BaseModel):
    image_id: str

@router.post("/delete", summary="删除图片")
async def delete_image(
    request: DeleteImageRequest,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除图片 (软删除)

    **Args:**

    - `request` (DeleteImageRequest): 删除请求
        - `image_id` (str): 图片ID
    - `current_user` (User): 当前登录用户
    - `db` (AsyncSession): 数据库会话

    **Returns:**

    - `dict`: 操作结果
    """
    stmt = select(UserImage).where(UserImage.id == request.image_id)
    result = await db.execute(stmt)
    image = result.scalar_one_or_none()
    
    if not image:
        return {"code": 404, "msg": "图片不存在"}
        
    if image.user_id != current_user.username:
        return {"code": 403, "msg": "无权删除此图片"}
        
    image.is_deleted = True
    await db.commit()
    
    return {"code": 200, "msg": "删除成功"}
