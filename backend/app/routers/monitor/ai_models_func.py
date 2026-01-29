#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/monitor/ai_models_func.py
# 作者：whf
# 日期：2026-01-26
# 描述：模型管理服务逻辑 (Func)

import os
from pathlib import Path
from typing import List, Dict, Optional
from backend.app.utils.logger import logger
from backend.app.utils.pg_utils import PGUtils
from backend.app.config import settings

class ModelManager:
    """
    模型管理服务
    负责扫描模型文件、同步数据库状态、获取模型配置
    """
    
    MODEL_BASE_DIR = settings.BASE_DIR / "app" / "models"
    
    @classmethod
    async def initialize(cls):
        """
        初始化：建表、扫描、同步
        """
        # 1. 确保表存在 (现在由 DBInitializer 在启动时统一处理，这里仅作为保险或手动调用入口)
        # 实际生产中通常由 DBInitializer 统一初始化，这里可以跳过
        pass
        
        # 2. 扫描并同步
        await cls.sync_models()
        
    @classmethod
    async def sync_models(cls):
        """
        扫描目录并同步到数据库
        """
        logger.info("正在同步 AI 模型信息...")
        
        # 1. 扫描文件系统
        found_models = []
        
        # 遍历 models 目录 (假设两级结构: type/file.pt 或 name/file.pt)
        # 这里简化处理：递归查找 .pt, .onnx, .pdmodel
        extensions = {'.pt', '.onnx', '.pdmodel'}
        
        for root, _, files in os.walk(cls.MODEL_BASE_DIR):
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in extensions:
                    # 识别类型
                    if 'yolo' in file.lower() or 'like' in file.lower():
                        m_type = 'yolo'
                    elif 'ocr' in file.lower() or 'paddle' in file.lower():
                        m_type = 'ocr'
                    else:
                        m_type = 'other'
                        
                    rel_path = os.path.relpath(os.path.join(root, file), cls.MODEL_BASE_DIR)
                    full_path = str(Path(root) / file)
                    
                    found_models.append({
                        "name": os.path.splitext(file)[0],
                        "filename": file, # 使用文件名作为唯一标识
                        "type": m_type,
                        "path": full_path
                    })
        
        # 2. 同步到数据库
        for model in found_models:
            # 检查是否存在
            exists_sql = "SELECT id FROM ai_model_registry WHERE filename = :filename"
            rows = await PGUtils.fetch_all(exists_sql, {"filename": model["filename"]})
            
            if not rows:
                # 新增
                logger.info(f"发现新模型: {model['filename']}")
                insert_sql = """
                INSERT INTO ai_model_registry (name, filename, type, description, is_enabled, use_gpu, status)
                VALUES (:name, :filename, :type, :desc, TRUE, TRUE, 'pending')
                """
                await PGUtils.execute_ddl(insert_sql, {
                    "name": model["name"],
                    "filename": model["filename"],
                    "type": model["type"],
                    "desc": f"自动扫描发现的模型，路径: {model['path']}"
                })
            else:
                # 已存在，更新 path 描述 (如果需要)
                pass
                
        # 3. 标记数据库中存在但文件已丢失的模型
        # (暂略，可后续实现将 status 设为 missing)
        
        logger.success(f"模型同步完成: 扫描到 {len(found_models)} 个模型")

    @classmethod
    async def get_model_config(cls, filename: str) -> Optional[Dict]:
        """
        获取模型配置
        """
        sql = "SELECT * FROM ai_model_registry WHERE filename = :filename"
        rows = await PGUtils.fetch_all(sql, {"filename": filename})
        if rows:
            return dict(rows[0])
        return None

    @classmethod
    async def update_model_status(cls, filename: str, status: str, error_msg: str = None):
        """
        更新模型状态
        """
        sql = """
        UPDATE ai_model_registry 
        SET status = :status, error_msg = :error, updated_at = NOW()
        WHERE filename = :filename
        """
        await PGUtils.execute_ddl(sql, {
            "status": status,
            "error": error_msg,
            "filename": filename
        })

    @classmethod
    async def get_all_models(cls) -> List[Dict]:
        """
        获取所有模型列表
        """
        sql = "SELECT * FROM ai_model_registry ORDER BY type, name"
        rows = await PGUtils.fetch_all(sql)
        return [dict(row) for row in rows]
