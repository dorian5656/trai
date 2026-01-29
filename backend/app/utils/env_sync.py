#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/app/utils/env_sync.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 自动同步 .env 配置到数据库

import hashlib
import socket
from pathlib import Path
from sqlalchemy import text
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.logger import logger

class EnvSync:
    """
    环境配置同步工具
    """
    
    @staticmethod
    def get_env_content():
        """读取 .env 文件内容"""
        # 定位到 backend 目录 (假设当前文件在 backend/app/utils/)
        base_dir = Path(__file__).resolve().parent.parent.parent
        env_path = base_dir / ".env"
        
        # 也可以尝试检测 .env.dev, 但通常我们只备份默认的 .env 或者当前生效的
        # 如果需要备份 dev，可以扩展逻辑
        
        if not env_path.exists():
            return None
            
        try:
            return env_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"读取 .env 失败: {e}")
            return None

    @staticmethod
    def calculate_hash(content):
        """计算 MD5 哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    @staticmethod
    async def sync():
        """同步逻辑"""
        try:
            content = EnvSync.get_env_content()
            if not content:
                logger.warning("未找到 .env 文件，跳过配置同步")
                return
                
            current_hash = EnvSync.calculate_hash(content)
            # 获取简单的机器标识
            try:
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                machine_info = f"{hostname} ({ip})"
            except:
                machine_info = "Unknown"
            
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # 检查 sys_env_logs 表是否存在 (防止启动时表还没建好)
                # 但 db_init 应该先运行。这里假设表已存在。
                
                # 检查最新的记录
                result = await conn.execute(
                    text("SELECT env_hash FROM sys_env_logs ORDER BY created_at DESC LIMIT 1")
                )
                last_record = result.one_or_none()
                
                # 如果没有记录，或者哈希不一致，则插入
                if not last_record or last_record.env_hash != current_hash:
                    await conn.execute(
                        text("""
                            INSERT INTO sys_env_logs (env_hash, env_content, machine_info)
                            VALUES (:env_hash, :env_content, :machine_info)
                        """),
                        {
                            "env_hash": current_hash,
                            "env_content": content,
                            "machine_info": machine_info
                        }
                    )
                    action = "初始化" if not last_record else "更新"
                    logger.info(f"✅ 环境配置已{action}备份到数据库 (Hash: {current_hash[:8]})")
                else:
                    logger.info(f"✅ 环境配置未变更，跳过备份 (Hash: {current_hash[:8]})")
        except Exception as e:
            logger.error(f"环境配置同步失败: {e}")
