#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：download_models.py
# 作者：liuhd
# 日期：2025-12-24 11:49:00
# 描述：将 ModelScope 平台上的模型下载到本地

"""
魔塔社区模型下载脚本
model_id = "",准备下载的模型id
local_dir = r"",模型的本地存放路径
"""

import os
import sys
from pathlib import Path
from loguru import logger
from modelscope.hub.snapshot_download import snapshot_download

def main():
    model_id = "TRAI/heart_like"
    local_dir = r"D:\AI\heart_like"
    
    logger.info(f"模型: {model_id}")
    logger.info(f"目标路径: {local_dir}")
    os.makedirs(local_dir, exist_ok=True)

    try:
        logger.info("开始下载（自动断点续传）...")
        final_path = snapshot_download(
            model_id=model_id,
            revision="master",
            local_dir=local_dir,    # 关键：直接指定完整路径
        )
        logger.info(f"下载成功！路径: {os.path.abspath(final_path)}")
    except KeyboardInterrupt:
        logger.warning("用户中断，重新运行可继续下载。")
    except Exception as e:
        logger.error(f"下载失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
