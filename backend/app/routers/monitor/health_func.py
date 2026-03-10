#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/monitor/health_func.py
# 作者：whf
# 日期：2026-02-05
# 描述：系统健康检查业务逻辑

import time
import os
from typing import Dict, Any
from sqlalchemy import text
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.logger import logger
from backend.app.config import settings
from pathlib import Path

class HealthManager:
    """
    健康检查管理器
    """
    
    @staticmethod
    async def check_system_status() -> Dict[str, Any]:
        """
        全面检查系统状态
        """
        status = {
            "status": "ok",
            "timestamp": int(time.time()),
            "checks": {
                "database": {"status": "unknown"},
                "ai_models": {"status": "unknown"},
                "storage": {"status": "unknown"}
            }
        }
        
        # 1. 检查数据库 (连接 + 关键表)
        db_status = await HealthManager._check_database()
        status["checks"]["database"] = db_status
        if db_status["status"] != "ok":
            status["status"] = "degraded"
            
        # 2. 检查本地 AI 模型
        model_status = HealthManager._check_ai_models()
        status["checks"]["ai_models"] = model_status
        
        # 3. 检查存储 (S3/Local)
        storage_status = HealthManager._check_storage()
        status["checks"]["storage"] = storage_status
        
        return status

    @staticmethod
    async def _check_database() -> Dict[str, Any]:
        """检查数据库连接和关键表"""
        result = {"status": "ok", "details": {}}
        try:
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # 检查连接
                await conn.execute(text("SELECT 1"))
                result["details"]["connection"] = "ok"
                
                # 检查关键表
                required_tables = ["users", "user_images", "chat_messages", "chat_sessions"]
                missing_tables = []
                for table in required_tables:
                    # 使用 information_schema 检查表是否存在
                    res = await conn.execute(
                        text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :table"),
                        {"table": table}
                    )
                    if not res.scalar():
                        missing_tables.append(table)
                
                if missing_tables:
                    result["status"] = "error"
                    result["details"]["missing_tables"] = missing_tables
                else:
                    result["details"]["tables"] = "all_present"
                    
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"Health check DB error: {e}")
            
        return result

    @staticmethod
    def _check_ai_models() -> Dict[str, Any]:
        """检查本地 AI 模型是否存在"""
        result = {"status": "ok", "models": []}
        try:
            # 基础模型目录
            base_model_dir = settings.BASE_DIR / "app" / "models"
            if not base_model_dir.exists():
                result["status"] = "warning"
                result["error"] = "Model directory not found"
                return result

            # 扫描常见模型目录
            # 这里简单列出目录下的子目录作为模型
            models = []
            for item in base_model_dir.glob("*"):
                if item.is_dir():
                    models.append(item.name)
            
            result["models"] = models
            # 简单判断: 如果列表为空，可能没有下载模型
            if not models:
                result["status"] = "warning"
                result["message"] = "No local models found"
                
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            
        return result

    @staticmethod
    def _check_storage() -> Dict[str, Any]:
        """检查存储配置"""
        result = {"status": "ok", "type": "local"}
        if settings.S3_ENABLED:
            result["type"] = "s3"
            # 简单检查 S3 配置是否完整
            if not settings.S3_ENDPOINT_URL or not settings.S3_ACCESS_KEY:
                result["status"] = "warning"
                result["message"] = "S3 enabled but config missing"
        else:
            # 检查本地上传目录
            upload_dir = settings.BASE_DIR / "static" / "uploads"
            if not upload_dir.exists():
                try:
                    upload_dir.mkdir(parents=True, exist_ok=True)
                    result["message"] = "Upload directory created"
                except Exception as e:
                    result["status"] = "error"
                    result["error"] = f"Cannot create upload dir: {e}"
                    
        return result
