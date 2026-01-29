#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/logger.py
# 作者：whf
# 日期：2026-01-26
# 描述：日志管理类，封装 loguru

import sys
from pathlib import Path
from loguru import logger as _logger

class LogManager:
    """
    日志管理器
    
    职责:
    1. 统一配置日志格式和输出
    2. 提供标准的 info/error/warning/debug 方法
    3. 支持日志文件轮转和保留策略
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._configure_logger()
        return cls._instance

    def _configure_logger(self):
        """
        配置 loguru
        """
        # 移除默认的 handler
        _logger.remove()
        
        # 定义日志格式
        # 时间 | 级别 | 模块:行号 | 消息
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        
        # 1. 控制台输出
        _logger.add(
            sys.stdout,
            format=log_format,
            level="INFO",
            colorize=True
        )
        
        # 2. 文件输出 (按天轮转，保留100天)
        # 确保 logs 目录存在 (backend/logs)
        # __file__ = backend/app/utils/logger.py
        # parent = utils
        # parent.parent = app
        # parent.parent.parent = backend
        log_path = Path(__file__).resolve().parent.parent.parent / "logs"
        if not log_path.exists():
            log_path.mkdir(exist_ok=True)
            
        _logger.add(
            log_path / "trai_{time:YYYY-MM-DD}.log",
            rotation="00:00",  # 每天午夜轮转
            retention="100 days", # 保留100天
            compression="zip", # 压缩旧日志
            format=log_format,
            level="INFO",
            encoding="utf-8"
        )
        
        self.logger = _logger

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
        
    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)
        
    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
        
    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)
        
    def success(self, msg: str, *args, **kwargs):
        self.logger.success(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)

# 单例实例
logger = LogManager()
