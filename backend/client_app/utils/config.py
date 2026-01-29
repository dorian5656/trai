#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/utils/config.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 客户端配置常量

import sys
import os
from pathlib import Path
from PyQt5.QtCore import QSettings

class Config:
    APP_NAME = "Trae AI Assistant"
    DEFAULT_BACKEND_URL = "http://localhost:5689"
    DEFAULT_USERNAME = "A6666"
    DEFAULT_PASSWORD = "123456"
    
    # 端口配置
    PORT_BACKEND_PROD = 5689
    PORT_BACKEND_DEV = 5889
    PORT_FRONTEND = 5173
    PORT_POSTGRES = 5432
    
    @staticmethod
    def get_settings():
        return QSettings("Trae", "AIAssistant")
        
    @staticmethod
    def get_backend_url():
        settings = Config.get_settings()
        return settings.value("backend_url", Config.DEFAULT_BACKEND_URL)
        
    @staticmethod
    def get_python_path():
        settings = Config.get_settings()
        return settings.value("python_path", "python")

    @staticmethod
    def get_resource_path(relative_path):
        """获取资源文件绝对路径 (支持 PyInstaller 打包)"""
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller 打包后的临时目录
            base_path = Path(sys._MEIPASS)
        else:
            # 开发环境: 当前文件所在目录的上一级 (backend/client_app)
            # utils/config.py -> utils/ -> client_app/
            base_path = Path(__file__).resolve().parent.parent
            
        return str(base_path / relative_path)
