#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/upload_utils.py
# 作者：whf
# 日期：2026-01-27
# 描述：文件上传工具类 (统一管理文件上传与存储)

import shutil
import uuid
import time
import json
import aioboto3
import aiofiles
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
    async def upload_local_file(cls, local_path: Path, object_name: str, content_type: str = None) -> str:
        """
        上传本地文件到存储 (S3 或 Local)
        
        Args:
            local_path: 本地文件绝对路径
            object_name: 目标路径 (S3 Key 或 相对路径)
            content_type: MIME 类型
            
        Returns:
            str: 访问 URL
        """
        if settings.S3_ENABLED:
            # S3 Upload
            bucket_name = settings.S3_BUCKET_NAME
            session = aioboto3.Session()
            async with session.client(
                's3',
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION_NAME
            ) as s3:
                try:
                    # Auto create bucket if needed (simplified check)
                    try:
                        await s3.head_bucket(Bucket=bucket_name)
                    except Exception:
                        try:
                            await s3.create_bucket(Bucket=bucket_name)
                            await cls._set_bucket_public(s3, bucket_name)
                        except:
                            pass

                    async with aiofiles.open(local_path, 'rb') as f:
                        data = await f.read()
                        
                    await s3.put_object(
                        Bucket=bucket_name,
                        Key=object_name,
                        Body=data,
                        ContentType=content_type or "application/octet-stream",
                        ACL='public-read'
                    )
                    
                    if settings.S3_PUBLIC_DOMAIN:
                        return f"{settings.S3_PUBLIC_DOMAIN}/{object_name}"
                    else:
                        return f"{settings.S3_ENDPOINT_URL}/{bucket_name}/{object_name}"
                except Exception as e:
                    logger.error(f"S3上传失败: {e}")
                    raise e
        else:
            # Local Copy
            # object_name might be "tools/gif/..."
            # target: static/uploads/tools/gif/...
            # Remove leading slash if present to ensure proper joining
            clean_object_name = object_name.lstrip('/')
            target_path = cls.BASE_UPLOAD_DIR / clean_object_name
            
            if not target_path.parent.exists():
                target_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(local_path, target_path)
            return f"/static/uploads/{clean_object_name}"

    @classmethod
    async def save_from_bytes(cls, data: bytes, filename: str, module: str = "common", content_type: str = None) -> Tuple[str, str, int]:
        """
        保存字节数据 (本地或S3)
        
        Args:
            data: 文件的字节内容
            filename: 原始文件名
            module: 模块名称
            content_type: MIME类型
            
        Returns:
            Tuple[str, str, int]: (相对路径/URL路径, 本地绝对路径/S3 Key, 文件大小)
        """
        # 1. 获取文件扩展名并转小写
        ext = Path(filename).suffix.lower()
        if not ext:
            ext = ".bin"
            
        # 2. 校验文件类型 (可选，仅警告)
        file_type = cls._get_file_type(ext)
        if not file_type:
            logger.warning(f"上传了未在白名单中的文件类型: {ext}")

        # 3. 生成存储路径
        date_str = time.strftime("%Y%m%d")
        file_id = str(uuid.uuid4()).replace("-", "")
        new_filename = f"{file_id}{ext}"
        
        # Determine prefix based on file_type
        prefix = "files"
        if file_type == 'image': 
            prefix = "images"
        elif file_type == 'audio': 
            prefix = "speech"
        elif file_type == 'video': 
            prefix = "video"
            
        object_name = f"{prefix}/{module}/{date_str}/{new_filename}" # S3 Key 或相对路径
        
        file_size = len(data)
        
        # 4. 判断存储方式
        if settings.S3_ENABLED:
            # S3 模式 - 统一使用 trai Bucket
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
                    # 确保 ContentType
                    final_content_type = content_type or "application/octet-stream"
                    
                    # 自动创建 Bucket
                    try:
                        await s3.head_bucket(Bucket=bucket_name)
                    except Exception:
                        try:
                            logger.info(f"Bucket {bucket_name} 不存在，正在创建...")
                            await s3.create_bucket(Bucket=bucket_name)
                            await cls._set_bucket_public(s3, bucket_name)
                        except Exception:
                            pass

                    await s3.put_object(
                        Bucket=bucket_name,
                        Key=object_name,
                        Body=data,
                        ContentType=final_content_type,
                        ACL='public-read'
                    )
                    
                    logger.info(f"文件上传到 S3 成功: {bucket_name}/{object_name}")
                    
                    if settings.S3_PUBLIC_DOMAIN:
                        url = f"{settings.S3_PUBLIC_DOMAIN}/{object_name}"
                    else:
                        url = f"{settings.S3_ENDPOINT_URL}/{bucket_name}/{object_name}"
                        
                    return url, object_name, file_size
            except Exception as e:
                logger.error(f"S3 上传失败: {e}")
                raise HTTPException(status_code=500, detail=f"S3 上传失败: {str(e)}")
        else:
            # 本地模式
            save_dir = cls.BASE_UPLOAD_DIR / module / date_str
            if not save_dir.exists():
                save_dir.mkdir(parents=True, exist_ok=True)
                
            local_path = save_dir / new_filename
            try:
                with open(local_path, "wb") as f:
                    f.write(data)
                
                logger.info(f"文件保存到本地成功: {local_path} (Size: {file_size})")
                
                # 生成访问 URL
                relative_path = f"/static/uploads/{module}/{date_str}/{new_filename}"
                return relative_path, str(local_path), file_size
            except Exception as e:
                logger.error(f"本地文件写入失败: {e}")
                raise HTTPException(status_code=500, detail="文件保存失败")

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
        # 格式: {prefix}/{module}/{yyyyMMdd}/{uuid}{ext}
        date_str = time.strftime("%Y%m%d")
        file_id = str(uuid.uuid4()).replace("-", "")
        new_filename = f"{file_id}{ext}"
        
        # Determine prefix based on file_type
        prefix = "files"
        if file_type == 'image': 
            prefix = "images"
        elif file_type == 'audio': 
            prefix = "speech"
        elif file_type == 'video': 
            prefix = "video"
            
        object_name = f"{prefix}/{module}/{date_str}/{new_filename}" # S3 Key 或相对路径
        
        # 4. 判断存储方式
        if settings.S3_ENABLED:
            # 确定 Bucket
            bucket_name = settings.S3_BUCKET_NAME
                
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
    async def _set_bucket_public(cls, s3_client, bucket_name: str):
        """设置 Bucket 为公开读"""
        try:
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicRead",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                    }
                ]
            }
            await s3_client.put_bucket_policy(
                Bucket=bucket_name,
                Policy=json.dumps(policy)
            )
            logger.info(f"已设置 Bucket {bucket_name} 为公开读模式")
        except Exception as e:
            logger.warning(f"设置 Bucket {bucket_name} 策略失败: {e}")

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
                
                # 确保 ContentType 不为 None
                content_type = file.content_type or "application/octet-stream"
                
                # 尝试自动创建 Bucket (如果不存在)
                try:
                    await s3.head_bucket(Bucket=bucket_name)
                except Exception:
                    try:
                        logger.info(f"Bucket {bucket_name} 不存在，正在创建...")
                        await s3.create_bucket(Bucket=bucket_name)
                        # 创建后立即设置公开读权限
                        await cls._set_bucket_public(s3, bucket_name)
                    except Exception as e:
                        logger.warning(f"创建 Bucket {bucket_name} 失败 (可能已存在或权限不足): {e}")

                await s3.put_object(
                    Bucket=bucket_name,
                    Key=object_name,
                    Body=file_content,
                    ContentType=content_type,
                    ACL='public-read'  # 显式设置对象 ACL
                )
                
                logger.info(f"文件上传到 S3 成功: {bucket_name}/{object_name}")
                
                # 生成访问 URL
                if settings.S3_PUBLIC_DOMAIN:
                    # 如果配置了 CDN/自定义域名
                    # 注意: S3_PUBLIC_DOMAIN 应该包含 bucket 名或者路径前缀，视具体配置而定
                    # 这里假设 S3_PUBLIC_DOMAIN = "https://ai.tuoren.com/trai"
                    # object_name = "images/gen/..."
                    # 结果 = "https://ai.tuoren.com/trai/images/gen/..."
                    
                    # 移除可能的末尾斜杠
                    domain = settings.S3_PUBLIC_DOMAIN.rstrip("/")
                    url = f"{domain}/{object_name}"
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
                    
                    # 确定 Bucket
                    # 统一使用 S3_BUCKET_NAME (默认 trai)，不再区分 image/audio 专用 bucket
                    bucket_name = settings.S3_BUCKET_NAME

                    # 这里为了解决用户无法访问 S3 IP 的问题，必须代理流
                    response = await s3.get_object(Bucket=bucket_name, Key=file_key)
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

    # =========================================================================
    # 分片上传支持
    # =========================================================================

    @classmethod
    def get_chunk_dir(cls, upload_id: str) -> Path:
        """获取分片临时存储目录"""
        chunk_dir = cls.BASE_UPLOAD_DIR / ".chunks" / upload_id
        if not chunk_dir.exists():
            chunk_dir.mkdir(parents=True, exist_ok=True)
        return chunk_dir

    @classmethod
    async def save_chunk(cls, upload_id: str, part_number: int, data: bytes) -> str:
        """保存单个分片"""
        chunk_dir = cls.get_chunk_dir(upload_id)
        # 使用 padding 格式文件名方便排序 (part_0001, part_0002...)
        chunk_path = chunk_dir / f"part_{part_number:05d}"
        
        try:
            # 异步写文件
            import aiofiles
            async with aiofiles.open(chunk_path, "wb") as f:
                await f.write(data)
            return str(chunk_path)
        except Exception as e:
            logger.error(f"保存分片失败: {e}")
            raise HTTPException(status_code=500, detail="分片保存失败")

    @classmethod
    async def merge_chunks(cls, upload_id: str, filename: str, total_parts: int, module: str = "common") -> Tuple[str, str, int]:
        """
        合并分片并保存为最终文件
        """
        chunk_dir = cls.get_chunk_dir(upload_id)
        if not chunk_dir.exists():
            raise HTTPException(status_code=404, detail="分片任务不存在或已过期")

        # 1. 检查分片完整性
        # 列出所有 part_xxxxx 文件
        chunks = sorted([p for p in chunk_dir.glob("part_*")])
        if len(chunks) != total_parts:
            # 检查是否有遗漏
            existing_indices = {int(p.name.split('_')[1]) for p in chunks}
            missing = set(range(1, total_parts + 1)) - existing_indices
            if missing:
                raise HTTPException(status_code=400, detail=f"分片不完整，缺失: {list(missing)[:10]}...")
        
        # 2. 合并文件
        date_str = time.strftime("%Y%m%d")
        ext = Path(filename).suffix.lower() or ".bin"
        new_filename = f"{upload_id}{ext}"  # 使用 upload_id 作为文件名，保证唯一性
        
        # 最终合并后的本地临时路径
        merged_temp_path = chunk_dir / new_filename
        
        try:
            with open(merged_temp_path, "wb") as outfile:
                for chunk_path in chunks:
                    with open(chunk_path, "rb") as infile:
                        shutil.copyfileobj(infile, outfile)
            
            file_size = merged_temp_path.stat().st_size
            
            # 3. 移动/上传到最终位置 (复用 save_from_bytes 逻辑，但这里已经有文件了)
            # 为了复用逻辑且支持 S3，我们读取合并后的文件内容再调用 save_from_bytes
            # 或者优化：如果是本地存储，直接 move；如果是 S3，则上传。
            
            object_name = f"{module}/{date_str}/{new_filename}"
            
            if settings.S3_ENABLED:
                # S3 模式：读取文件流上传
                # 注意：对于超大文件，这里应该使用 multipart upload，但为了复用 _save_to_s3，暂且读入内存
                # TODO: 优化 S3 大文件上传
                async with aiofiles.open(merged_temp_path, "rb") as f:
                    file_content = await f.read()
                
                # 获取文件类型以确定 Bucket
                # 统一使用 S3_BUCKET_NAME (默认 trai)，不再区分 image/audio 专用 bucket
                bucket_name = settings.S3_BUCKET_NAME
                
                # 构造一个模拟的 UploadFile (这有点 hack，但能复用 _save_to_s3)
                # 或者直接调用底层 boto3
                
                session = aioboto3.Session()
                async with session.client(
                    's3',
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY,
                    region_name=settings.S3_REGION_NAME
                ) as s3:
                    await s3.put_object(
                        Bucket=bucket_name,
                        Key=object_name,
                        Body=file_content,
                        ACL='public-read'
                    )
                    
                    if settings.S3_PUBLIC_DOMAIN:
                        url = f"{settings.S3_PUBLIC_DOMAIN}/{object_name}"
                    else:
                        url = f"{settings.S3_ENDPOINT_URL}/{bucket_name}/{object_name}"
                        
                    result = (url, object_name, file_size)
            else:
                # 本地模式：移动文件
                final_dir = cls.BASE_UPLOAD_DIR / module / date_str
                if not final_dir.exists():
                    final_dir.mkdir(parents=True, exist_ok=True)
                
                final_path = final_dir / new_filename
                shutil.move(str(merged_temp_path), str(final_path))
                
                relative_path = f"/static/uploads/{module}/{date_str}/{new_filename}"
                result = (relative_path, str(final_path), file_size)
                
            # 4. 清理分片目录
            shutil.rmtree(chunk_dir)
            logger.info(f"分片合并完成并清理: {upload_id} -> {result[0]}")
            
            return result

        except Exception as e:
            logger.error(f"合并分片失败: {e}")
            raise HTTPException(status_code=500, detail=f"合并失败: {str(e)}")

    @classmethod
    def get_uploaded_chunks(cls, upload_id: str) -> List[int]:
        """获取已上传的分片编号列表"""
        chunk_dir = cls.BASE_UPLOAD_DIR / ".chunks" / upload_id
        if not chunk_dir.exists():
            return []
        
        # 提取文件名中的 part_xxxxx
        indices = []
        for p in chunk_dir.glob("part_*"):
            try:
                idx = int(p.name.split('_')[1])
                indices.append(idx)
            except:
                pass
        return sorted(indices)
