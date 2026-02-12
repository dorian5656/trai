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
import datetime
import json
import paramiko
from loguru import logger
from dotenv import load_dotenv

def upload_to_server(local_file_path, exe_name, timestamp):
    """上传文件到服务器并更新 version.json"""
    # 加载 .env 配置
    # 假设 .env 在 backend 目录下
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(env_path)

    host = os.getenv("DEPLOY_SERVER_HOST")
    port = int(os.getenv("DEPLOY_SERVER_PORT", 22))
    user = os.getenv("DEPLOY_SERVER_USER")
    password = os.getenv("DEPLOY_SERVER_PASSWORD")
    remote_dir = os.getenv("DEPLOY_REMOTE_DIR")
    
    if not all([host, user, password, remote_dir]):
        raise ValueError("部署配置不完整，请检查 .env 文件中的 DEPLOY_SERVER_* 变量")
    
    logger.info(f"开始上传文件到服务器: {host}")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port, user, password)
        
        sftp = ssh.open_sftp()
        
        # 确保远程目录存在
        try:
            sftp.mkdir(remote_dir)
        except IOError:
            pass
            
        # 1. 上传 EXE 文件
        remote_file_path = f"{remote_dir}/{exe_name}.exe"
        logger.info(f"正在上传 {exe_name}.exe ...")
        sftp.put(local_file_path, remote_file_path)
        logger.success(f"EXE 上传成功: {remote_file_path}")
        
        # 2. 更新 version.json
        version_file = f"{remote_dir}/version.json"
        version_data = {
            "version": timestamp,
            "latest_version": timestamp,
            "release_date": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "download_url": f"/static/exe/{exe_name}.exe",
            "update_log": f"1. 自动构建更新 ({timestamp})\n2. 修复若干已知问题\n3. 提升稳定性",
            "description": f"最新版本客户端 {timestamp}，建议更新。",
            "force_update": False
        }
        
        # 将 JSON 写入临时文件再上传，或者直接通过 SSH 执行命令写入
        version_json_str = json.dumps(version_data, indent=4, ensure_ascii=False)
        with sftp.file(version_file, 'w') as f:
            f.write(version_json_str)
        
        logger.success(f"version.json 更新成功: {version_file}")
        
        sftp.close()
        ssh.close()
        
    except Exception as e:
        logger.error(f"上传或更新服务器失败: {e}")
        raise

def build():
    logger.info("开始构建流程 (单文件模式)...")
    
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
        '--onefile',   # 单文件可执行程序
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

    target_path_candidates = [
        os.path.join(script_dir, 'dist', exe_name + '.exe'),
        os.path.join(script_dir, exe_name + '.exe'),
        os.path.join(script_dir, 'dist', exe_name, exe_name + '.exe'),
    ]
    built_exe_path = None
    for p in target_path_candidates:
        if os.path.exists(p):
            built_exe_path = p
            break
    if not built_exe_path:
        for root, _, files in os.walk(script_dir):
            for f in files:
                if f == exe_name + '.exe':
                    built_exe_path = os.path.join(root, f)
                    break
            if built_exe_path:
                break
    if not built_exe_path:
        logger.error("未找到打包生成的可执行文件")
        sys.exit(1)
    logger.success(f"\n构建完成！可执行文件位于:\n{built_exe_path}")
    
    # 自动上传到服务器
    try:
        upload_to_server(built_exe_path, exe_name, timestamp)
    except Exception as e:
        logger.error(f"自动化部署流程失败: {e}")
        # 这里可以选择是否退出，或者仅记录错误

if __name__ == "__main__":
    build()
