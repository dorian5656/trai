#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/config.py
# 作者：whf
# 日期：2026-01-26
# 描述：应用配置管理

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

from urllib.parse import quote_plus

class Settings(BaseSettings):
    # 基础配置
    PROJECT_NAME: str = "TRAI Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api_trai/v1"
    
    # 环境配置
    ENV: str = os.getenv("ENV", "dev")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 5689))
    
    # PostgreSQL 数据库配置
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "itzx")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """
        构造 SQLAlchemy 数据库连接 URI
        """
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # 路径配置
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    @property
    def MODEL_PATH_HEART_LIKE(self) -> Path:
        """YOLO Heart Like 模型路径"""
        # Updated to match actual file structure: yolo/yolo11/heart_like/heart_like.pt
        return self.BASE_DIR / "app" / "models" / "yolo" / "yolo11" / "heart_like" / "heart_like.pt"

    # 日志配置
    LOG_LEVEL: str = "INFO"

    # RRDSPPG OCR 配置
    RRDSPPG_OCR_FILTER_REMOVE_LETTERS: bool = False
    RRDSPPG_OCR_FILTER_REMOVE_DIGITS: bool = False
    RRDSPPG_OCR_FILTER_REMOVE_PUNCTUATION: bool = False
    RRDSPPG_OCR_FILTER_REMOVE_BEFORE_KEYWORD: str = ""
    RRDSPPG_OCR_FILTER_REMOVE_AFTER_KEYWORD: str = ""
    
    # RRDSPPG YOLO 配置
    RRDSPPG_YOLO_REQUIRED_CLASSES: str = ""
    
    # RRDSPPG 任务类型
    RRDSPPG_TASK_TYPE_OFFICIAL_ACCOUNT: str = ""
    RRDSPPG_TASK_TYPE_VIDEO_ACCOUNT: str = ""
    
    # 企业微信配置
    WECOM_TRAI_ROBOT_KEY: str = os.getenv("WECOM_TRAI_ROBOT_KEY", "")
    WECOM_CORP_ID: str = os.getenv("WECOM_CORP_ID", "")
    WECOM_CORP_SECRET: str = os.getenv("WECOM_CORP_SECRET", "")
    WECOM_AGENT_ID: str = os.getenv("WECOM_AGENT_ID", "")
    WECOM_SYNC_ON_STARTUP: bool = os.getenv("WECOM_SYNC_ON_STARTUP", "false").lower() == "true"
    
    # 飞书配置
    FEISHU_TRAI_WEBHOOK_TOKEN: str = os.getenv("FEISHU_TRAI_WEBHOOK_TOKEN", "")
    FEISHU_GUANWANGLIUZI_WEBHOOK_TOKEN: str = os.getenv("FEISHU_GUANWANGLIUZI_WEBHOOK_TOKEN", "")
    FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")
    
    # 安全配置 (JWT)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    
    # DeepSeek API 配置
    DEEPSEEK_API_BASE: str = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")

    # S3 对象存储配置
    S3_ENABLED: bool = os.getenv("S3_ENABLED", "false").lower() == "true"
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "trai-uploads")
    S3_IMAGE_BUCKET_NAME: str = os.getenv("S3_IMAGE_BUCKET_NAME", "trai_images")
    S3_SPEECH_BUCKET_NAME: str = os.getenv("S3_SPEECH_BUCKET_NAME", "trai_speech")
    S3_REGION_NAME: str = os.getenv("S3_REGION_NAME", "us-east-1")
    S3_PUBLIC_DOMAIN: str = os.getenv("S3_PUBLIC_DOMAIN", "")

    # Dify AI 配置
    DIFY_API_BASE_URL: str = os.getenv("DIFY_API_BASE_URL", "http://192.168.100.119:8098/v1")
    
    # 兼容 DeepSeek 变量 (如果 .env 中使用的是 DEEPSEEK_API_BASE)
    @property
    def MODEL_API_BASE(self) -> str:
        # 优先使用 DIFY_API_BASE_URL，如果为空则使用 DEEPSEEK_API_BASE
        # 注意：这里我们做一个简单的逻辑，因为 DIFY_API_BASE_URL 有默认值
        # 我们可以检查 DEEPSEEK_API_BASE 是否被设置为非默认值
        if self.DEEPSEEK_API_BASE and "api.deepseek.com" not in self.DEEPSEEK_API_BASE:
             return self.DEEPSEEK_API_BASE
        return self.DIFY_API_BASE_URL

    # 官网助手 Key
    DIFY_GUANWANG_API_KEY: str = os.getenv("DIFY_GUANWANG_API_KEY", "")
    # 财务助手 Key (预留)
    DIFY_CAIWU_API_KEY: str = os.getenv("DIFY_CAIWU_API_KEY", "")
    
    # 邮件推送配置 (SMTP)
    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "smtp.qq.com")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", 465))
    EMAIL_USER: str = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
    
    # 邮件收件人配置
    EMAIL_TO_DEFAULT_QQ: str = os.getenv("EMAIL_TO_DEFAULT_QQ", "")
    EMAIL_TO_DEFAULT_163: str = os.getenv("EMAIL_TO_DEFAULT_163", "")

    @property
    def EMAIL_TO_DEFAULT(self) -> list[str]:
        """
        获取合并后的默认收件人列表 (QQ + 163)
        """
        emails = []
        for src in [self.EMAIL_TO_DEFAULT_QQ, self.EMAIL_TO_DEFAULT_163]:
            if src:
                # 支持逗号分隔
                emails.extend([e.strip() for e in src.split(",") if e.strip()])
        return emails

    # 兼容旧配置 (如果需要)
    @property
    def DIFY_API_KEY(self) -> str:
        """兼容旧代码，默认返回官网助手 Key"""
        return self.DIFY_GUANWANG_API_KEY

    @property
    def DIFY_APPS(self) -> dict:
        """获取所有已配置的 Dify 应用"""
        apps = {}
        if self.DIFY_GUANWANG_API_KEY:
            apps["guanwang"] = self.DIFY_GUANWANG_API_KEY
        if self.DIFY_CAIWU_API_KEY:
            apps["caiwu"] = self.DIFY_CAIWU_API_KEY
        return apps

    # 兼容旧配置 (如果需要)
    @property
    def DEEPSEEK_API_KEY(self) -> str:
        return self.AI_API_KEY

    class Config:
        case_sensitive = True
        env_file = str(Path(__file__).resolve().parent.parent / ".env")
        extra = "ignore" # 忽略多余的环境变量

settings = Settings()
