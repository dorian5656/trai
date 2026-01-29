#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/net_utils.py
# 描述：网络相关工具类

import socket
from loguru import logger

class NetUtils:
    """
    网络工具类
    提供获取本机IP等网络相关功能
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
