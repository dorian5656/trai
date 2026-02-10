#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: build_onefile.py
# 作者: liuhd
# 日期: 2026-02-10 17:00:00
# 描述: PyQt客户端打包脚本 (单文件模式)

import PyInstaller.__main__
import os
import shutil
import sys

def build():
    print("开始构建流程 (单文件模式)...")
    
    # 确保位于正确的目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # 清理旧的构建产物
    if os.path.exists('dist'):
        print("正在清理 dist 目录...")
        shutil.rmtree('dist')
    if os.path.exists('build'):
        print("正在清理 build 目录...")
        shutil.rmtree('build')

    # PyInstaller 参数
    args = [
        'run.py',
        '--name=TraiClient',
        '--windowed',  # 无控制台窗口
        '--onefile',   # 单文件可执行程序
        '--clean',
        '--noconfirm',
        '--icon=icon/tr_mascot_local.ico',
        # 添加数据文件 (源;目标) - Windows 使用分号
        '--add-data=pages/config.json;pages',
        '--add-data=styles/style.qss;styles',
        '--add-data=icon;icon',
        # 隐式导入 (PyQt6 和 requests 通常能自动检测，但为了保险起见显式添加)
        '--hidden-import=PyQt6',
        '--hidden-import=requests',
        '--hidden-import=loguru',
    ]

    print(f"正在运行 PyInstaller，参数: {args}")
    
    try:
        PyInstaller.__main__.run(args)
        print("PyInstaller 构建成功。")
    except Exception as e:
        print(f"PyInstaller 构建失败: {e}")
        sys.exit(1)

    print(f"\n构建完成！可执行文件位于:\n{os.path.join(script_dir, 'dist', 'TraiClient.exe')}")

if __name__ == "__main__":
    build()
