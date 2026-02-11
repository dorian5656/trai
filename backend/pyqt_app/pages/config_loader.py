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
        """获取配置字典"""
        if cls._instance is None:
            cls._instance = ConfigLoader()
        return cls._instance._config

    @classmethod
    def get_instance(cls):
        """获取 ConfigLoader 实例"""
        if cls._instance is None:
            cls._instance = ConfigLoader()
        return cls._instance

    def __init__(self):
        if ConfigLoader._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            self.config_path = ""
            self._config = self._load_config()

    def _load_config(self):
        """加载配置文件，优先查找当前工作目录"""
        config = {}
        
        # 1. 优先查找当前运行目录下的 config.json (用户自定义配置)
        user_config_path = os.path.join(os.getcwd(), CONFIG_FILE)
        
        # 2. 其次查找同级目录 (开发环境)
        dev_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
        
        # 3. 最后查找内置资源 (打包环境)
        frozen_config_path = ""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            frozen_config_path = os.path.join(base_path, 'pages', CONFIG_FILE)

        # 确定使用的配置文件路径
        if os.path.exists(user_config_path):
            self.config_path = user_config_path
        elif os.path.exists(dev_config_path):
            self.config_path = dev_config_path
        elif frozen_config_path and os.path.exists(frozen_config_path):
            self.config_path = frozen_config_path
        else:
            # 如果都不存在，默认设为用户目录，方便后续保存生成
            self.config_path = user_config_path

        # 读取配置
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as e:
                logger.error(f"读取配置文件失败: {e}, 配置为空")
        else:
            logger.warning(f"未找到配置文件: {CONFIG_FILE}, 配置为空")
        
        return config

    def save_config(self, new_config_str):
        """保存配置字符串到文件"""
        try:
            # 校验 JSON 格式
            new_config = json.loads(new_config_str)
            
            # 确定保存路径：如果当前使用的是内置资源路径(打包环境且无外置配置)，则保存到当前工作目录
            save_path = self.config_path
            if getattr(sys, 'frozen', False) and sys._MEIPASS in self.config_path:
                 save_path = os.path.join(os.getcwd(), CONFIG_FILE)

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(new_config, indent=4, ensure_ascii=False))
            
            # 更新内存中的配置和路径
            self._config = new_config
            self.config_path = save_path
            return True, "保存成功"
        except json.JSONDecodeError as e:
            return False, f"JSON 格式错误: {e}"
        except Exception as e:
            return False, f"保存失败: {e}"

    def get_config_text(self):
        """获取配置文件的文本内容"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                return "{}"
        return json.dumps(self._config, indent=4, ensure_ascii=False)

    def reload(self):
        """重新加载配置"""
        self._config = self._load_config()
        return self._config

    def _deep_update(self, base_dict, update_dict):
        """递归更新嵌套字典"""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

# 全局便捷访问
config = ConfigLoader.get_config()
