#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/download_utils.py
# 描述：文件下载工具类

import httpx
import os
from pathlib import Path
from backend.app.utils.logger import logger
import uuid

class DownloadUtils:
    """
    下载工具类
    """
    
    @staticmethod
    async def download_image(url: str, save_dir: Path) -> str:
        """
        下载图片到指定目录
        :param url: 图片URL
        :param save_dir: 保存目录
        :return: 本地文件路径
        """
        try:
            # 清理 URL 前后空格和可能的反引号 (用户输入常见错误)
            url = url.strip().strip('`').strip()
            
            # 生成临时文件名
            ext = os.path.splitext(url)[1]
            if not ext or len(ext) > 5: # 简单校验后缀
                ext = ".jpg" # 默认后缀
            
            # 处理可能的 URL 参数
            if '?' in ext:
                ext = ext.split('?')[0]
                
            filename = f"{uuid.uuid4()}{ext}"
            save_path = save_dir / filename
            
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                
                with open(save_path, "wb") as f:
                    f.write(response.content)
                    
            return str(save_path)
        except Exception as e:
            logger.error(f"下载图片失败: {url}, error: {e}")
            raise e
