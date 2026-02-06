#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：config_loader.py
# 作者：liuhd
# 日期：2026-02-06 11:55:00
# 描述：配置文件加载器 (PyQt6 GUI版)

import os
import json
import sys
from loguru import logger

# 配置文件名
CONFIG_FILE = "config.json"

class ConfigLoader:
    _instance = None
    _config = None

    @classmethod
    def get_config(cls):
        """获取配置单例"""
        if cls._instance is None:
            cls._instance = ConfigLoader()
        return cls._instance._config

    def __init__(self):
        if ConfigLoader._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            self._config = self._load_config()

    def _load_config(self):
        """加载配置文件，优先查找当前工作目录"""
        config = {}
        
        # 尝试在当前目录查找 config.json
        config_path = os.path.join(os.getcwd(), CONFIG_FILE)
        
        # 如果当前目录不存在，尝试在 pages 目录 (即本文件所在目录)
        if not os.path.exists(config_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, CONFIG_FILE)
            
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as e:
                logger.error(f"读取配置文件失败: {e}, 配置为空")
        else:
            logger.warning(f"未找到配置文件: {CONFIG_FILE}, 配置为空")
        
        return config

    def _deep_update(self, base_dict, update_dict):
        """递归更新嵌套字典"""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

# 全局便捷访问
config = ConfigLoader.get_config()
