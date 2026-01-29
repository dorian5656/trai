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
from backend.app.routers.upload.upload_func import UserImage

@router.post("/common", response_model=UploadResponse, summary="通用文件上传")
async def upload_file(
    file: UploadFile = File(...),
    module: str = Form("common", description="业务模块名称 (如 avatar, chat)"),
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传文件到服务器
    - **file**: 文件对象
    - **module**: 模块名称 (决定存储子目录)
    
    返回:
    - **url**: 文件的静态访问路径
    """
    logger.info(f"用户 {current_user.username} 正在上传文件: {file.filename} (Module: {module})")
    
    url, local_path, size = await UploadUtils.save_file(file, module)
    
    # 记录到数据库
    try:
        new_image = UserImage(
            user_id=current_user.username,
            filename=file.filename,
            s3_key=local_path, # local_path 在 S3 模式下是 object_name
            url=url,
            size=size,
            mime_type=file.content_type,
            module=module
        )
        db.add(new_image)
        await db.commit()
        await db.refresh(new_image)
        logger.info(f"图片记录已保存到数据库: {new_image.id}")
    except Exception as e:
        logger.error(f"保存图片记录失败: {e}")
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
    - **file_path**: 文件路径 (如 common/20260127/abc.png)
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

@router.delete("/{image_id}", summary="删除图片")
async def delete_image(
    image_id: str,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除图片 (软删除)
    """
    stmt = select(UserImage).where(UserImage.id == image_id)
    result = await db.execute(stmt)
    image = result.scalar_one_or_none()
    
    if not image:
        return {"code": 404, "msg": "图片不存在"}
        
    if image.user_id != current_user.username:
        return {"code": 403, "msg": "无权删除此图片"}
        
    image.is_deleted = True
    await db.commit()
    
    return {"code": 200, "msg": "删除成功"}
