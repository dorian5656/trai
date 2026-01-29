#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/upload_utils.py
# 作者：whf
# 日期：2026-01-27
# 描述：文件上传工具类 (统一管理文件上传与存储)

import shutil
import uuid
import time
import aioboto3
from pathlib import Path
from typing import List, Optional, Tuple
from fastapi import UploadFile, HTTPException
from backend.app.config import settings
from backend.app.utils.logger import logger

class UploadUtils:
    """
    文件上传工具箱
    """
    
    # 允许的文件类型白名单
    ALLOWED_EXTENSIONS = {
        # 图片
        'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico'},
        # 音频
        'audio': {'.mp3', '.wav', '.aac', '.ogg', '.m4a', '.flac'},
        # 视频
        'video': {'.mp4', '.avi', '.mov', '.wmv', '.mkv', '.flv', '.webm'},
        # 文档/压缩包
        'file': {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.zip', '.rar', '.7z', '.tar', '.gz'}
    }
    
    # 基础存储路径 (backend/static/uploads)
    BASE_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "uploads"

    @classmethod
    async def save_file(cls, file: UploadFile, module: str = "common") -> Tuple[str, str, int]:
        """
        保存上传的文件 (本地或S3)
        
        Args:
            file: 上传的文件对象
            module: 模块名称 (用于区分存储目录，如 avatar, chat, common)
            
        Returns:
            Tuple[str, str, int]: (相对路径/URL路径, 本地绝对路径/S3 Key, 文件大小)
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")

        # 1. 获取文件扩展名并转小写
        ext = Path(file.filename).suffix.lower()
        if not ext:
            # 如果没有后缀，尝试从 content_type 推断 (可选，这里先简单处理)
            ext = ".bin"
            
        # 2. 校验文件类型
        file_type = cls._get_file_type(ext)
        if not file_type:
            # 如果不在白名单中，根据 strict 模式决定是否报错
            # 这里为了通用性，允许上传，但记录警告
            logger.warning(f"上传了未在白名单中的文件类型: {ext}")
            # raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

        # 3. 生成存储路径
        # 格式: {module}/{yyyyMMdd}/{uuid}{ext}
        date_str = time.strftime("%Y%m%d")
        file_id = str(uuid.uuid4()).replace("-", "")
        new_filename = f"{file_id}{ext}"
        object_name = f"{module}/{date_str}/{new_filename}" # S3 Key 或相对路径
        
        # 4. 判断存储方式
        if settings.S3_ENABLED:
            # 确定 Bucket
            bucket_name = settings.S3_BUCKET_NAME
            if file_type == 'image' and settings.S3_IMAGE_BUCKET_NAME:
                bucket_name = settings.S3_IMAGE_BUCKET_NAME
                
            return await cls._save_to_s3(file, object_name, bucket_name)
        else:
            return await cls._save_to_local(file, module, date_str, new_filename)

    @classmethod
    async def _save_to_local(cls, file: UploadFile, module: str, date_str: str, filename: str) -> Tuple[str, str, int]:
        """保存到本地文件系统"""
        save_dir = cls.BASE_UPLOAD_DIR / module / date_str
        if not save_dir.exists():
            save_dir.mkdir(parents=True, exist_ok=True)
            
        local_path = save_dir / filename
        
        try:
            # 使用同步写文件 (FastAPI UploadFile 是 SpooledTemporaryFile)
            with local_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            file_size = local_path.stat().st_size
            logger.info(f"文件保存到本地成功: {local_path} (Size: {file_size})")
            
            # 生成访问 URL (相对路径)
            # 路径: /static/uploads/{module}/{yyyyMMdd}/{uuid}{ext}
            relative_path = f"/static/uploads/{module}/{date_str}/{filename}"
            
            return relative_path, str(local_path), file_size
            
        except Exception as e:
            logger.error(f"本地文件写入失败: {e}")
            raise HTTPException(status_code=500, detail="文件保存失败")
        finally:
            await file.close()

    @classmethod
    async def _save_to_s3(cls, file: UploadFile, object_name: str, bucket_name: str = None) -> Tuple[str, str, int]:
        """保存到 S3 对象存储"""
        if bucket_name is None:
            bucket_name = settings.S3_BUCKET_NAME
            
        session = aioboto3.Session()
        
        try:
            async with session.client(
                's3',
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION_NAME
            ) as s3:
                # 读取文件内容
                # 注意: 如果文件非常大，建议使用 multipart upload，这里简化处理直接 put_object
                file_content = await file.read()
                file_size = len(file_content)
                
                await s3.put_object(
                    Bucket=bucket_name,
                    Key=object_name,
                    Body=file_content,
                    ContentType=file.content_type
                )
                
                logger.info(f"文件上传到 S3 成功: {bucket_name}/{object_name}")
                
                # 生成访问 URL
                if settings.S3_PUBLIC_DOMAIN:
                    # 如果配置了 CDN/自定义域名
                    url = f"{settings.S3_PUBLIC_DOMAIN}/{object_name}"
                else:
                    # 默认使用 Endpoint 拼接
                    url = f"{settings.S3_ENDPOINT_URL}/{bucket_name}/{object_name}"
                    
                return url, object_name, file_size
                
        except Exception as e:
            logger.error(f"S3 上传失败: {e}")
            raise HTTPException(status_code=500, detail=f"S3 上传失败: {str(e)}")
        finally:
            await file.close()

    @classmethod
    async def get_file_stream(cls, file_key: str):
        """
        获取文件流 (从 S3 或本地)
        
        Args:
            file_key: S3 Key (如 "common/20260127/abc.png")
            
        Returns:
            Generator/Bytes: 文件内容流
        """
        if settings.S3_ENABLED:
            # S3 模式: 使用 aioboto3 生成流
            session = aioboto3.Session()
            async with session.client(
                's3',
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION_NAME
            ) as s3:
                try:
                    # 使用 generate_presigned_url 获取临时链接重定向 (更高效)
                    # 或者直接读取流 (消耗后端流量但兼容性好)
                    # 这里为了解决用户无法访问 S3 IP 的问题，必须代理流
                    response = await s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=file_key)
                    # 注意: StreamingResponse 需要 async generator
                    async for chunk in response['Body'].iter_chunks():
                        yield chunk
                except Exception as e:
                    logger.error(f"S3 读取失败: {e}")
                    raise HTTPException(status_code=404, detail="文件不存在")
        else:
            # 本地模式
            # file_key 可能是 "common/20260127/abc.png"
            local_path = cls.BASE_UPLOAD_DIR / file_key
            if not local_path.exists():
                raise HTTPException(status_code=404, detail="文件不存在")
                
            with open(local_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk

    @classmethod
    def _get_file_type(cls, ext: str) -> Optional[str]:
        """
        根据扩展名判断文件大类
        """
        for type_name, extensions in cls.ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                return type_name
        return None
