#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/utils/image_utils.py
# 作者：wuhao
# 日期：2026-02-10 09:35:00
# 描述：图像处理工具类，提供图片缩放、格式转换等功能

import os
import uuid
from pathlib import Path
from PIL import Image
from backend.app.utils.logger import logger

class ImageUtils:
    """图像处理工具类"""

    @staticmethod
    def resize_image(input_path: str, output_path: str, width: int = None, height: int = None) -> bool:
        """
        调整图片尺寸
        
        Args:
            input_path (str): 输入图片路径
            output_path (str): 输出图片路径
            width (int, optional): 目标宽度. Defaults to None.
            height (int, optional): 目标高度. Defaults to None.
            
        Returns:
            bool: 是否成功
        """
        try:
            if not width and not height:
                logger.warning("Resize params (width/height) are both empty")
                return False

            with Image.open(input_path) as img:
                original_width, original_height = img.size
                
                # 计算目标尺寸，保持纵横比
                if width and not height:
                    ratio = width / original_width
                    height = int(original_height * ratio)
                elif height and not width:
                    ratio = height / original_height
                    width = int(original_width * ratio)
                
                # 如果两者都指定，则强制拉伸或裁剪（这里暂时采用强制拉伸，可根据需求修改）
                
                logger.info(f"Resizing image: {input_path} -> {width}x{height}")
                
                resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
                
                # 确保输出目录存在
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    
                resized_img.save(output_path)
                logger.info(f"Image saved to: {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"Resize image failed: {e}")
            return False

    @staticmethod
    def convert_format(input_path: str, output_path: str, format: str = "JPEG", quality: int = 85) -> bool:
        """
        转换图片格式
        
        Args:
            input_path (str): 输入图片路径
            output_path (str): 输出图片路径
            format (str): 目标格式 (JPEG, PNG, WEBP等). Defaults to "JPEG".
            quality (int): 图片质量 (1-100), 仅对 JPG/WEBP 有效. Defaults to 85.
            
        Returns:
            bool: 是否成功
        """
        try:
            with Image.open(input_path) as img:
                logger.info(f"Converting image: {input_path} -> {format} (q={quality})")
                
                # 如果是 RGBA 转 JPG，需要先转为 RGB (JPG 不支持透明度)
                if format.upper() in ["JPEG", "JPG"] and img.mode in ["RGBA", "P"]:
                    img = img.convert("RGB")
                
                # 确保输出目录存在
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    
                img.save(output_path, format=format, quality=quality)
                logger.info(f"Image converted to: {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"Convert image failed: {e}")
            return False

    @staticmethod
    def compress_to_target_size(input_path: str, output_path: str, target_size_mb: float, step: int = 5, min_quality: int = 10) -> bool:
        """
        压缩图片到指定文件大小 (MB)
        
        Args:
            input_path (str): 输入路径
            output_path (str): 输出路径
            target_size_mb (float): 目标大小 (MB)
            step (int): 每次调整质量的步长. Defaults to 5.
            min_quality (int): 最低质量. Defaults to 10.
            
        Returns:
            bool: 是否成功
        """
        try:
            target_size_bytes = target_size_mb * 1024 * 1024
            file_size = os.path.getsize(input_path)
            
            if file_size <= target_size_bytes:
                logger.info(f"Image size ({file_size/1024/1024:.2f}MB) is already smaller than target ({target_size_mb}MB)")
                # 直接复制
                with Image.open(input_path) as img:
                    img.save(output_path)
                return True
                
            with Image.open(input_path) as img:
                # 如果是 PNG/RGBA，先转为 RGB (JPG 压缩更有效)
                if img.mode in ["RGBA", "P"]:
                    img = img.convert("RGB")
                
                # 迭代压缩
                quality = 95
                while quality >= min_quality:
                    # 保存到内存或临时文件检查大小
                    img.save(output_path, format="JPEG", quality=quality)
                    current_size = os.path.getsize(output_path)
                    
                    logger.info(f"Compressing (q={quality}): {current_size/1024/1024:.2f}MB / Target: {target_size_mb}MB")
                    
                    if current_size <= target_size_bytes:
                        logger.info(f"Compression success at quality={quality}")
                        return True
                        
                    quality -= step
                
                # 如果质量降到最低仍不满足，尝试缩小尺寸 (resize)
                logger.warning("Quality compression reached limit, trying resize...")
                width, height = img.size
                scale = 0.9
                while scale > 0.1:
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    resized.save(output_path, format="JPEG", quality=min_quality)
                    
                    current_size = os.path.getsize(output_path)
                    logger.info(f"Resizing (scale={scale:.1f}): {current_size/1024/1024:.2f}MB")
                    
                    if current_size <= target_size_bytes:
                        return True
                    scale -= 0.1
                    
                return False # 无法压缩到目标大小
                
        except Exception as e:
            logger.error(f"Compress to target size failed: {e}")
            return False

    @staticmethod
    def get_image_info(file_path: str) -> dict:
        """
        获取图片信息
        
        Args:
            file_path (str): 图片路径
            
        Returns:
            dict: 图片信息 (width, height, format, mode)
        """
        try:
            with Image.open(file_path) as img:
                return {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                    "size": os.path.getsize(file_path)
                }
        except Exception as e:
            logger.error(f"Get image info failed: {e}")
            return {}
