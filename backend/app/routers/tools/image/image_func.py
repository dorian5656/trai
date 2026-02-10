#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/routers/tools/image/image_func.py
# 作者：wuhao
# 日期：2026-02-10 09:35:00
# 描述：图像处理业务逻辑

import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
from backend.app.utils.logger import logger
from backend.app.utils.image_utils import ImageUtils

# 临时文件存储路径
TEMP_DIR = Path("backend/temp/images")

class ImageFunc:
    """图像处理业务逻辑类"""
    
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

        # 生成唯一文件名
        input_ext = Path(file.filename).suffix
        if not input_ext:
            input_ext = ".png"
            
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
            
            logger.info(f"File uploaded to: {input_path}")
            
            # 调用工具类进行转换
            success = ImageUtils.convert_format(str(input_path), str(output_path), format, quality)
            
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

        input_ext = Path(file.filename).suffix
        if not input_ext:
            input_ext = ".png"
            
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
            
            logger.info(f"File uploaded to: {input_path}")
            
            success = ImageUtils.compress_to_target_size(str(input_path), str(output_path), target_mb)
            
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

        # 生成唯一文件名
        ext = Path(file.filename).suffix
        if not ext:
            ext = ".png" # 默认扩展名
            
        unique_id = str(uuid.uuid4())
        input_filename = f"{unique_id}_in{ext}"
        output_filename = f"{unique_id}_out{ext}"
        
        input_path = TEMP_DIR / input_filename
        output_path = TEMP_DIR / output_filename

        try:
            # 保存上传的文件
            with open(input_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            logger.info(f"File uploaded to: {input_path}")
            
            # 调用工具类进行缩放
            success = ImageUtils.resize_image(str(input_path), str(output_path), width, height)
            
            if not success:
                raise HTTPException(status_code=500, detail="Image resizing failed")
                
            # 获取输出文件信息
            info = ImageUtils.get_image_info(str(output_path))
            
            # 返回相对路径供前端访问 (假设有静态文件服务挂载了 backend/temp)
            # 或者返回临时下载链接
            # 这里返回相对路径，配合 file_proxy 或 static mount 使用
            relative_path = f"images/{output_filename}"
            
            return {
                "original_name": file.filename,
                "output_path": str(output_path),
                "relative_path": relative_path,
                "width": info.get("width"),
                "height": info.get("height"),
                "size": info.get("size")
            }
            
        except Exception as e:
            logger.error(f"Error in resize_image: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # 清理输入文件，保留输出文件供下载 (可配合定时任务清理)
            if input_path.exists():
                os.remove(input_path)
