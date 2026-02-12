#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/models/tool_log.py
# 作者：liuhd
# 日期：2026-02-12
# 描述：工具使用日志模型

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.sql import func
from backend.app.utils.pg_utils import Base

class ToolUsageLog(Base):
    """
    工具使用日志表
    记录所有工具类功能的使用情况 (如 视频转GIF, PDF转Word等)
    """
    __tablename__ = "tool_usage_logs"

    id = Column(String(36), primary_key=True, comment="主键ID") # UUID
    user_id = Column(String(50), index=True, nullable=False, comment="用户ID")
    tool_name = Column(String(50), index=True, nullable=False, comment="工具名称")
    input_source = Column(Text, nullable=True, comment="输入源 (文件路径/URL)")
    output_result = Column(Text, nullable=True, comment="输出结果 (文件路径/URL)")
    params = Column(JSON, nullable=True, comment="参数 (JSON)")
    status = Column(String(20), default="success", comment="状态: success/failed")
    error_msg = Column(Text, nullable=True, comment="错误信息")
    client_ip = Column(String(50), nullable=True, comment="客户端IP")
    duration_ms = Column(Float, nullable=True, comment="耗时(ms)")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<ToolUsageLog(tool={self.tool_name}, user={self.user_id}, status={self.status})>"
