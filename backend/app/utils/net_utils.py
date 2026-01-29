#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/net_utils.py
# 描述：网络相关工具类

import socket
import platform
import subprocess
import os
import re
from loguru import logger

class NetUtils:
    """
    网络工具类
    提供获取本机IP、端口检查与释放等网络相关功能
    """
    
    @staticmethod
    def get_local_ip() -> str:
        """
        获取本机局域网 IP
        :return: IP 地址字符串
        """
        try:
            # 使用 UDP 连接探测本机 IP (不需要实际建立连接)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            logger.warning(f"获取本机 IP 失败，使用默认值: {e}")
            return "127.0.0.1"

    @staticmethod
    def check_and_release_port(port: int) -> bool:
        """
        检查指定端口是否被占用，如果占用则尝试释放（杀掉进程）
        仅支持 Windows 自动释放，其他平台仅提示
        :param port: 端口号
        :return: 是否成功释放（或端口原本就未占用）
        """
        system_platform = platform.system().lower()
        
        # 1. 检查端口是否被占用
        if not NetUtils.is_port_in_use(port):
            logger.info(f"端口 {port} 未被占用，可直接使用")
            return True

        logger.warning(f"端口 {port} 被占用，尝试清理...")

        # 2. 根据平台处理
        if "windows" in system_platform:
            return NetUtils._release_port_windows(port)
        elif "linux" in system_platform or "darwin" in system_platform: # Darwin is macOS
            return NetUtils._release_port_unix(port)
        else:
            logger.warning(f"当前平台 ({system_platform}) 不支持自动释放端口，请手动处理")
            return False

    @staticmethod
    def is_port_in_use(port: int) -> bool:
        """检查端口是否占用"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    @staticmethod
    def _release_port_windows(port: int) -> bool:
        """Windows 平台释放端口"""
        try:
            # 查找占用端口的 PID
            # netstat -ano | findstr :<port>
            cmd_find = f'netstat -ano | findstr :{port}'
            result = subprocess.run(cmd_find, shell=True, capture_output=True, text=True)
            
            if not result.stdout:
                logger.info(f"未检测到端口 {port} 的占用进程 (可能已释放)")
                return True

            # 解析输出获取 PID (取最后一行，防止多行匹配)
            # 示例: "  TCP    0.0.0.0:5789           0.0.0.0:0              LISTENING       12345"
            lines = result.stdout.strip().split('\n')
            pids = set()
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    # 确保是数字且不是 0
                    if pid.isdigit() and pid != '0':
                        pids.add(pid)
            
            if not pids:
                logger.warning(f"无法解析端口 {port} 的 PID")
                return False

            # 杀死所有相关进程
            for pid in pids:
                logger.info(f"正在终止占用端口 {port} 的进程 (PID: {pid})...")
                cmd_kill = f'taskkill /PID {pid} /F'
                kill_result = subprocess.run(cmd_kill, shell=True, capture_output=True, text=True)
                
                if kill_result.returncode == 0:
                    logger.success(f"成功终止进程 {pid}")
                else:
                    logger.error(f"终止进程 {pid} 失败: {kill_result.stderr}")
                    return False
            
            return True

        except Exception as e:
            logger.error(f"Windows 释放端口异常: {e}")
            return False

    @staticmethod
    def _release_port_unix(port: int) -> bool:
        """Linux/MacOS 平台释放端口"""
        try:
            # 尝试使用 lsof 获取 PID
            cmd_find = f"lsof -i :{port} -t"
            result = subprocess.run(cmd_find, shell=True, capture_output=True, text=True)
            
            pids = [p.strip() for p in result.stdout.split('\n') if p.strip()]
            
            if not pids:
                logger.info(f"未检测到端口 {port} 的占用进程")
                return True

            for pid in pids:
                logger.info(f"正在终止占用端口 {port} 的进程 (PID: {pid})...")
                cmd_kill = f"kill -9 {pid}"
                kill_result = subprocess.run(cmd_kill, shell=True, capture_output=True, text=True)
                
                if kill_result.returncode == 0:
                    logger.success(f"成功终止进程 {pid}")
                else:
                    logger.error(f"终止进程 {pid} 失败: {kill_result.stderr}")
                    return False
            return True
            
        except Exception as e:
            logger.error(f"Unix 释放端口异常: {e}")
            return False
