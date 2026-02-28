#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：upload_models.py
# 作者：liuhd
# 日期：2026-02-02 17:25:00
# 描述：将本地模型文件夹下的所有文件上传到 ModelScope 平台

import os
import shutil
import sys
from loguru import logger
from modelscope.hub.api import HubApi

# ============== 配置区（请按需修改）===============
# 替换为你的实际用户名/模型名
MODEL_ID = "TRAI/heart_like"
# 本地模型文件存放目录
LOCAL_DIR = r"D:\AI\TRAI\heart_like" 
# 替换为你的 ModelScope Access Token
ACCESS_TOKEN = "ms-a04e0d45-5264-451d-942c-7638c05a5c93"  
# ============== 配置结束 ========================

def cleanup_temp_dir(model_dir):
    """清理 SDK 可能残留的临时 Git 目录"""
    temp_dirs = [
        os.path.join(model_dir, '._____temp'),
        os.path.join(model_dir, '.git')  # 极少数情况可能残留
    ]
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"已清理残留目录: {temp_dir}")
            except Exception as e:
                logger.warning(f"清理 {temp_dir} 时出错: {e}")

def main():
    # 1. 验证目录和文件
    if not os.path.isdir(LOCAL_DIR):
        logger.error(f"错误: 模型目录不存在 → {LOCAL_DIR}")
        sys.exit(1)
    # 检查目录是否为空
    if not os.listdir(LOCAL_DIR):
        logger.error(f"错误: 模型目录为空 → {LOCAL_DIR}")
        sys.exit(1)
    
    # 2. 清理残留临时目录（关键步骤！）
    cleanup_temp_dir(LOCAL_DIR)
    
    # 3. 初始化 API 并登录
    api = HubApi()
    try:
        api.login(ACCESS_TOKEN)
        logger.success("ModelScope 账号登录成功")
    except Exception as e:
        logger.error(f"登录失败: {e}")
        logger.info("请访问: https://modelscope.cn/my/access/token 获取有效Token")
        sys.exit(1)
    
    # 4. 使用新版 upload_folder 上传
    logger.info(f"开始上传模型至 ModelScope: {MODEL_ID}")
    logger.info(f"本地目录: {LOCAL_DIR}")
    
    try:
        api.upload_folder(
            folder_path=LOCAL_DIR,
            repo_id=MODEL_ID,
            repo_type='model',
            commit_message='Update model files'  # 可选：提交说明
        )
        logger.success("上传成功！")
        logger.info(f"模型主页: https://www.modelscope.cn/models/{MODEL_ID}")
        logger.info(f"文件列表: https://www.modelscope.cn/models/{MODEL_ID}/files")
    except Exception as e:
        logger.error(f"上传失败: {type(e).__name__}: {e}")
        logger.info("排查建议:")
        logger.info("1. 确认 ACCESS_TOKEN 有效")
        logger.info("2. 确认 MODEL_ID 中的用户名与你的账号完全一致（区分大小写）")
        logger.info("3. 检查网络是否可访问 ModelScope")
        logger.info("4. 运行: pip install -U modelscope 确保 SDK 为最新版")
        sys.exit(1)

if __name__ == "__main__":
    main()