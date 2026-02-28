#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名: build_onedir.py
# 作者: liuhd
# 日期: 2026-02-10 17:00:00
# 描述: PyQt客户端打包脚本 (文件夹模式)

import PyInstaller.__main__
import os
import shutil
import sys
import datetime
from loguru import logger

def build():
    logger.info("开始构建流程 (文件夹模式)...")
    
    # 确保位于正确的目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # 生成带时间戳的文件名
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')
    exe_name = f'TraiClient_{timestamp}'
    
    # 使用绝对路径以避免 PyInstaller 路径解析错误
    config_path = os.path.join(script_dir, 'pages', 'config.json')
    style_path = os.path.join(script_dir, 'styles', 'style.qss')
    icon_dir = os.path.join(script_dir, 'icon')
    icon_file = os.path.join(script_dir, 'icon', 'tr_mascot_local.ico')
    
    # 清理旧的构建产物
    if os.path.exists('dist'):
        logger.info("正在清理 dist 目录...")
        shutil.rmtree('dist')
    if os.path.exists('build'):
        logger.info("正在清理 build 目录...")
        shutil.rmtree('build')

    # PyInstaller 参数
    args = [
        'run.py',
        f'--name={exe_name}',
        '--windowed',  # 无控制台窗口
        '--onedir',    # 文件夹模式
        '--clean',
        '--noconfirm',
        f'--icon={icon_file}',
        # 添加数据文件 (源;目标) - Windows 使用分号
        f'--add-data={config_path};pages',
        f'--add-data={style_path};styles',
        f'--add-data={icon_dir};icon',
        # 隐式导入 (PyQt6 和 requests 通常能自动检测，但为了保险起见显式添加)
        '--hidden-import=PyQt6',
        '--hidden-import=requests',
        '--hidden-import=loguru',
    ]

    logger.info(f"正在运行 PyInstaller，参数: {args}")
    
    try:
        PyInstaller.__main__.run(args)
        logger.success("PyInstaller 构建成功。")
    except Exception as e:
        logger.error(f"PyInstaller 构建失败: {e}")
        sys.exit(1)

    # 构建后操作: 复制 config.json 到根目录以便于编辑
    dist_dir = os.path.join(script_dir, 'dist', exe_name)
    config_src = os.path.join(script_dir, 'pages', 'config.json')
    config_dst = os.path.join(dist_dir, 'config.json')
    
    logger.info(f"正在复制 config.json 到 {config_dst}...")
    try:
        shutil.copy2(config_src, config_dst)
        logger.success("配置文件复制成功。")
    except Exception as e:
        logger.error(f"复制配置文件失败: {e}")

    logger.success(f"构建完成！可执行文件位于:\n{os.path.join(dist_dir, exe_name + '.exe')}")

if __name__ == "__main__":
    build()
