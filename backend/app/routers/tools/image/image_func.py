#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/routers/tools/image/image_func.py
# 作者：wuhao
# 日期：2026-02-10 09:35:00
# 描述：图像处理业务逻辑

import os
import uuid
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
from fastapi import UploadFile, HTTPException
from backend.app.utils.logger import logger
from backend.app.utils.image_utils import ImageUtils

# 临时文件存储路径
TEMP_DIR = Path(os.getenv("IMAGE_TEMP_DIR", "backend/temp/images"))

# 线程池用于异步执行耗时操作
executor = ThreadPoolExecutor(max_workers=4)

class ImageFunc:
    """图像处理业务逻辑类"""
    
    @staticmethod
    def _validate_file(file: UploadFile) -> str:
        """
        校验上传文件的安全性和类型
        
        Args:
            file (UploadFile): 上传的文件
            
        Returns:
            str: 安全的文件扩展名
        """
        # 1. 校验文件名安全性 (防止路径穿越)
        filename = os.path.basename(file.filename)
        if not filename or "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
            
        # 2. 校验文件扩展名
        ext = Path(filename).suffix.lower()
        if not ext:
            ext = ".png" # 默认扩展名
            
        # 3. 校验 MIME 类型 (初步)
        if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp", "image/tiff"]:
             # 如果 content_type 不准确，尝试通过 Pillow 验证 (稍后在读取流时验证)
             pass
             
        return ext

    @staticmethod
    def _verify_image_format(file_path: Path):
        """使用 Pillow 严格校验图片格式"""
        try:
            with Image.open(file_path) as img:
                if img.format not in ["JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF"]:
                    raise HTTPException(status_code=400, detail=f"Unsupported image format: {img.format}")
        except Exception:
             if file_path.exists():
                 os.remove(file_path)
             raise HTTPException(status_code=400, detail="Invalid image file content")

    @staticmethod
    async def convert_image(file: UploadFile, format: str = "JPEG", quality: int = 85) -> dict:
        """
        处理图片格式转换/压缩请求
        
        Args:
            format (str): 目标格式 (JPEG, PNG, WEBP)
            quality (int): 图片质量 (1-100)
            
        Returns:
            dict: 处理结果
        """
        # 确保临时目录存在
        if not TEMP_DIR.exists():
            TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # 安全校验
        input_ext = ImageFunc._validate_file(file)
            
        # 根据目标格式确定输出后缀
        format_map = {
            "JPEG": ".jpg",
            "JPG": ".jpg",
            "PNG": ".png",
            "WEBP": ".webp"
        }
        output_ext = format_map.get(format.upper(), ".jpg")
            
        unique_id = str(uuid.uuid4())
        input_filename = f"{unique_id}_in{input_ext}"
        output_filename = f"{unique_id}_out{output_ext}"
        
        input_path = TEMP_DIR / input_filename
        output_path = TEMP_DIR / output_filename

        try:
            # 保存上传的文件
            with open(input_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # 严格校验图片内容
            ImageFunc._verify_image_format(input_path)

            logger.info(f"File uploaded to: {input_path}")
            
            # 异步调用工具类进行转换
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                executor, 
                ImageUtils.convert_format, 
                str(input_path), 
                str(output_path), 
                format, 
                quality
            )
            
            if not success:
                raise HTTPException(status_code=500, detail="Image conversion failed")
                
            # 获取输出文件信息
            info = ImageUtils.get_image_info(str(output_path))
            
            relative_path = f"images/{output_filename}"
            
            return {
                "original_name": file.filename,
                "output_path": str(output_path),
                "relative_path": relative_path,
                "width": info.get("width"),
                "height": info.get("height"),
                "size": info.get("size"),
                "format": info.get("format")
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in convert_image: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if input_path.exists():
                os.remove(input_path)
    @staticmethod
    async def compress_image(file: UploadFile, target_mb: float) -> dict:
        """
        处理图片压缩到指定大小请求
        
        Args:
            file (UploadFile): 上传的图片文件
            target_mb (float): 目标大小 (MB)
            
        Returns:
            dict: 处理结果
        """
        # 确保临时目录存在
        if not TEMP_DIR.exists():
            TEMP_DIR.mkdir(parents=True, exist_ok=True)

        input_ext = ImageFunc._validate_file(file)
            
        # 压缩通常输出为 JPG 以获得更好效果
        output_ext = ".jpg"
            
        unique_id = str(uuid.uuid4())
        input_filename = f"{unique_id}_in{input_ext}"
        output_filename = f"{unique_id}_compressed{output_ext}"
        
        input_path = TEMP_DIR / input_filename
        output_path = TEMP_DIR / output_filename

        try:
            with open(input_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            ImageFunc._verify_image_format(input_path)

            logger.info(f"File uploaded to: {input_path}")
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                executor,
                ImageUtils.compress_to_target_size,
                str(input_path),
                str(output_path),
                target_mb
            )
            
            if not success:
                raise HTTPException(status_code=500, detail="Image compression failed (cannot reach target size)")
                
            info = ImageUtils.get_image_info(str(output_path))
            relative_path = f"images/{output_filename}"
            
            return {
                "original_name": file.filename,
                "output_path": str(output_path),
                "relative_path": relative_path,
                "width": info.get("width"),
                "height": info.get("height"),
                "size": info.get("size"),
                "format": info.get("format")
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in compress_image: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if input_path.exists():
                os.remove(input_path)

    @staticmethod
    async def resize_image(file: UploadFile, width: int = None, height: int = None) -> dict:
        """
        处理图片缩放请求
        
        Args:
            file (UploadFile): 上传的图片文件
            width (int): 目标宽度
            height (int): 目标高度
            
        Returns:
            dict: 处理结果 (包含下载路径)
        """
        if not width and not height:
            raise HTTPException(status_code=400, detail="Width and height cannot be both empty")

        # 确保临时目录存在
        if not TEMP_DIR.exists():
            TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # 安全校验
        ext = ImageFunc._validate_file(file)
            
        unique_id = str(uuid.uuid4())
        input_filename = f"{unique_id}_in{ext}"
        output_filename = f"{unique_id}_out{ext}"
        
        input_path = TEMP_DIR / input_filename
        output_path = TEMP_DIR / output_filename

        try:
            # 保存上传的文件
            with open(input_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # 严格校验图片内容
            ImageFunc._verify_image_format(input_path)

            logger.info(f"File uploaded to: {input_path}")
            
            # 异步调用工具类进行缩放
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                executor,
                ImageUtils.resize_image,
                str(input_path),
                str(output_path),
                width,
                height
            )
            
            if not success:
                raise HTTPException(status_code=500, detail="Image resizing failed")
                
            # 获取输出文件信息
            info = ImageUtils.get_image_info(str(output_path))
            
            # 返回相对路径供前端访问
            relative_path = f"images/{output_filename}"
            
            return {
                "original_name": file.filename,
                "output_path": str(output_path),
                "relative_path": relative_path,
                "width": info.get("width"),
                "height": info.get("height"),
                "size": info.get("size")
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in resize_image: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # 清理输入文件，保留输出文件供下载
            if input_path.exists():
                os.remove(input_path)
