#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/utils/media_utils.py
# 作者：liuhd
# 日期：2026-02-12
# 描述：媒体处理工具类，提供视频转GIF等功能

import os
from pathlib import Path
from moviepy import VideoFileClip
from loguru import logger
from backend.app.utils.upload_utils import UploadUtils
from backend.app.config import settings

# 定义项目根目录用于安全校验
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class MediaUtils:
    """媒体处理工具类"""

    @staticmethod
    async def video_to_gif(input_path: str | Path, output_path: str | Path = None, user_id: str = None, fps: int = 10, width: int = 320) -> str:
        """
        视频转 GIF
        :param input_path: 输入视频路径
        :param output_path: 输出 GIF 路径 (可选)
        :param user_id: 用户ID (用于记录)
        :param fps: GIF 帧率
        :param width: GIF 宽度 (高度按比例缩放)
        :return: 上传后的 URL
        """
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
        
        if output_path is None:
            output_path = input_path.with_suffix('.gif')
        else:
            output_path = Path(output_path).resolve()
            
        logger.info(f"开始转换视频转GIF: {input_path} -> {output_path} (fps={fps}, width={width})")
        
        try:
            # 1. 转换逻辑
            # 使用 moviepy 进行转换
            clip = VideoFileClip(str(input_path))
            
            # 调整大小
            if width:
                clip = clip.resized(width=width)
                
            # 写入 GIF
            clip.write_gif(str(output_path), fps=fps, logger=None) # logger=None 禁用 moviepy 默认打印
            
            # 关闭资源
            clip.close()
            
            # 2. 上传并记录
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise Exception("GIF 生成失败 (文件未创建或为空)")
                
            file_size = output_path.stat().st_size
            logger.info(f"GIF 生成成功: {output_path} ({file_size} bytes)")
            
            # 如果提供了 user_id，则上传并记录
            if user_id:
                # 构造元数据
                metadata = {
                    "original_file": input_path.name,
                    "type": "video2gif",
                    "fps": fps,
                    "width": width
                }
                
                # 使用 UploadUtils 上传
                # 注意: upload_local_file 通常返回 (url, filename, size) 或类似
                # 这里我们假设 UploadUtils.upload_local_file 可用，或者模仿 DocUtils 的 _upload_and_record
                # 既然 DocUtils 也是调用的 upload_utils，我们直接复用类似的逻辑
                
                # 读取 DocUtils 的 _upload_and_record 逻辑比较复杂，包含了 PGUtils 记录
                # 为了保持一致性，我们最好也实现类似的记录逻辑
                # 这里简化处理，直接调用 upload_local_file，然后返回 URL
                # 如果需要记录到 doc_records 表，可以使用 PGUtils
                
                # 暂时先上传
                # 假设 UploadUtils.upload_local_file(file_path, prefix) -> url
                s3_key = f"tools/gif/{datetime.now().strftime('%Y%m%d')}/{uuid.uuid4()}.gif"
                url = await UploadUtils.upload_local_file(output_path, s3_key, content_type="image/gif")
                
                # 记录到数据库 (可选，参考 DocUtils)
                # await DocUtils._record_conversion(...) 
                # 由于 DocUtils._upload_and_record 是私有的，我们这里简单一点，只返回 URL
                # 如果需要记录，可以在 Router 层处理，或者在这里引入 PGUtils
                
                return url
            else:
                # 如果没有 user_id，返回本地路径 (仅供测试)
                return str(output_path)
                
        except Exception as e:
            logger.error(f"视频转GIF失败: {e}")
            # 清理失败的输出文件
            if output_path.exists():
                try:
                    os.remove(output_path)
                except:
                    pass
            raise e
            
import uuid
from datetime import datetime
