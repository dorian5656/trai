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
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.feishu_utils import feishu_bot
import asyncio
import io
import json

from backend.app.config import settings

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
                logger.warning("调整尺寸参数 (width/height) 均为空")
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
                
                logger.info(f"正在调整图片尺寸: {input_path} -> {width}x{height}")
                
                resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
                
                # 确保输出目录存在
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    
                resized_img.save(output_path)
                logger.info(f"图片已保存至: {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"调整图片尺寸失败: {e}")
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
                logger.info(f"正在转换图片格式: {input_path} -> {format} (质量={quality})")
                
                # 如果是 RGBA 转 JPG，需要先转为 RGB (JPG 不支持透明度)
                if format.upper() in ["JPEG", "JPG"] and img.mode in ["RGBA", "P"]:
                    img = img.convert("RGB")
                
                # 确保输出目录存在
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    
                img.save(output_path, format=format, quality=quality)
                logger.info(f"图片已转换并保存至: {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"转换图片格式失败: {e}")
            return False

    @staticmethod
    async def image_to_ico(input_path: str, output_path: str, sizes: list = None, user_id: str = None) -> str:
        """
        将图片转换为 ICO 图标，并上传 S3、记录数据库及发送飞书通知
        
        Args:
            input_path (str): 输入图片路径
            output_path (str): 输出 ICO 路径
            sizes (list): 包含的图标尺寸列表，默认包含常见尺寸
            user_id (str): 用户ID (用于归属记录)
            
        Returns:
            str: 生成的 ICO 文件的 URL (如果启用S3) 或 本地绝对路径
        """
        if sizes is None:
            # 默认尺寸，包含常见分辨率
            sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
            
        try:
            # 1. 转换并保存 ICO
            preview_bytes = None
            with Image.open(input_path) as img:
                logger.info(f"正在转换图片为 ICO: {input_path} -> {output_path}")
                
                # 确保是 RGBA 模式以保留透明度
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # 确保输出目录存在
                output_dir = os.path.dirname(output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    
                img.save(output_path, format='ICO', sizes=sizes)
                logger.info(f"ICO 已保存至: {output_path}")
                
                # 生成预览图 (PNG)
                try:
                    preview_buffer = io.BytesIO()
                    preview_img = img.copy()
                    # 限制预览图大小，避免过大
                    preview_img.thumbnail((300, 300))
                    preview_img.save(preview_buffer, format='PNG')
                    preview_bytes = preview_buffer.getvalue()
                except Exception as e:
                    logger.warning(f"生成预览图失败: {e}")
            
            # 2. 上传 S3 并记录数据库
            final_url = str(output_path)
            
            # 无论是否有 user_id，都进行上传
            # 如果没有 user_id，使用 'anonymous' 或 'guest' 作为路径的一部分
            upload_user_id = user_id if user_id else "guest"
            
            try:
                # 上传生成的 ICO
                file_bytes = Path(output_path).read_bytes()
                file_size = Path(output_path).stat().st_size
                
                # 构造 S3 Key
                s3_key = f"images/{upload_user_id}/{uuid.uuid4()}_{Path(output_path).name}"
                
                url, key, size = await UploadUtils.save_from_bytes(
                    file_bytes, 
                    Path(output_path).name, 
                    module="image_convert", 
                    content_type="image/x-icon"
                )
                final_url = url
                logger.info(f"ICO 已上传至 S3: {url}")
                
                # 仅在有 user_id 时记录到 user_images 表
                if user_id:
                    try:
                        insert_sql = """
                            INSERT INTO user_images (
                                user_id, filename, s3_key, url, size, mime_type, module, source, meta_data
                            ) VALUES (
                                :user_id, :filename, :s3_key, :url, :size, :mime_type, :module, :source, :meta_data
                            )
                        """
                        params = {
                            "user_id": user_id,
                            "filename": Path(output_path).name,
                            "s3_key": key,
                            "url": url,
                            "size": size,
                            "mime_type": "image/x-icon",
                            "module": "image_convert",
                            "source": "converted",
                            "meta_data": json.dumps({
                                "original_file": Path(input_path).name, 
                                "type": "img2ico",
                                "sizes": str(sizes)
                            })
                        }
                        await PGUtils.execute_update(insert_sql, params)
                        logger.info(f"ICO 记录已保存至数据库")
                    except Exception as e:
                        logger.error(f"ICO 记录保存数据库失败: {e}")
                
                # 发送飞书通知 (仅在有 user_id 时，避免匿名请求骚扰)
                if user_id:
                    try:
                        # 上传预览图获取 img_key (使用 asyncio.to_thread 避免阻塞)
                        img_key = None
                        if preview_bytes:
                            try:
                                img_key = await asyncio.to_thread(feishu_bot.upload_image, preview_bytes)
                            except Exception as e:
                                logger.warning(f"上传预览图到飞书失败: {e}")

                        card_content = {
                            "config": {"wide_screen_mode": True},
                            "header": {
                                "title": {"tag": "plain_text", "content": "🖼️ 图片转 ICO 完成"},
                                "template": "blue"
                            },
                            "elements": [
                                {
                                    "tag": "div",
                                    "text": {"tag": "lark_md", "content": f"**用户**: {user_id}\n**原文件名**: {Path(input_path).name}\n**转换尺寸**: {sizes}"}
                                },
                                {
                                    "tag": "action",
                                    "actions": [
                                        {
                                            "tag": "button",
                                            "text": {"tag": "plain_text", "content": "下载 ICO"},
                                            "url": url,
                                            "type": "primary"
                                        }
                                    ]
                                }
                            ]
                        }
                        
                        # 如果有 img_key，添加图片元素
                        if img_key:
                            card_content["elements"].insert(0, {
                                "tag": "img",
                                "img_key": img_key,
                                "alt": {
                                    "tag": "plain_text",
                                    "content": "ICO 预览"
                                }
                            })

                        # 使用配置的文生图 Webhook Token 发送通知
                        webhook_token = settings.FEISHU_IMAGE_GEN_WEBHOOK_TOKEN
                        # 使用 asyncio.to_thread 修复同步函数 await 错误
                        await asyncio.to_thread(feishu_bot.send_webhook_card, card_content, webhook_token=webhook_token)
                        logger.info(f"飞书通知发送成功 (Token: {webhook_token[:5]}***)")
                    except Exception as e:
                        logger.warning(f"飞书通知发送失败: {e}")

            except Exception as e:
                logger.error(f"ICO 上传 S3 失败: {e}")
            
            return final_url
            
        except Exception as e:
            logger.error(f"转换 ICO 失败: {e}")
            raise e

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
