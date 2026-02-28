#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/llm_study/llama3_1/download_model.py
# 作者：liuhd
# 日期：2026-02-11
# 描述：Llama3.1-8B-Instruct 模型下载脚本
# 参考：https://github.com/datawhalechina/self-llm/blob/master/models/Llama3_1/01-Llama3_1-8B-Instruct%20FastApi%20%E9%83%A8%E7%BD%B2%E8%B0%83%E7%94%A8.md

import os
from pathlib import Path
from modelscope import snapshot_download

def download_model():
    """
    下载 Llama-3.1-8B-Instruct 模型
    """
    # 获取项目根目录 (假设当前文件在 backend/app/llm_study/llama3_1/)
    # 向上回溯 4 层到 backend/
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    
    # 设置模型保存路径: backend/app/models/
    # 注意：根据 .gitignore 规则，backend/app/models/ 下的大型模型目录应被忽略
    model_root = base_dir / "app" / "models"
    
    print(f"准备下载模型，保存路径: {model_root}")
    
    if not model_root.exists():
        model_root.mkdir(parents=True, exist_ok=True)
        print(f"创建模型目录: {model_root}")

    try:
        # 使用 modelscope 下载
        # revision='master' 代表下载最新版本
        model_dir = snapshot_download(
            'LLM-Research/Meta-Llama-3.1-8B-Instruct', 
            cache_dir=str(model_root), 
            revision='master'
        )
        print(f"✅ 模型下载成功，路径: {model_dir}")
        return model_dir
    except Exception as e:
        print(f"❌ 模型下载失败: {e}")
        return None

if __name__ == "__main__":
    download_model()
