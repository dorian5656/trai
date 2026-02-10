#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/models/ai_video.py
# 作者：liuhd
# 日期：2026-02-06
# 描述：AI 视频任务模型

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from backend.app.utils.pg_utils import Base

class AIVideoTask(Base):
    """
    AI 视频生成任务表
    """
    __tablename__ = "ai_video_tasks"

    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    task_id = Column(String(64), unique=True, index=True, nullable=False, comment="任务ID (UUID)")
    user_id = Column(String(64), index=True, nullable=True, comment="用户ID")
    
    prompt = Column(Text, nullable=False, comment="提示词")
    model = Column(String(64), default="Wan2.1-T2V-1.3B", comment="模型名称")
    
    status = Column(String(32), default="pending", index=True, comment="状态: pending/processing/success/failed")
    
    video_url = Column(String(512), nullable=True, comment="视频地址 (S3/Local)")
    cover_url = Column(String(512), nullable=True, comment="封面图地址")
    
    width = Column(Integer, nullable=True, comment="宽度")
    height = Column(Integer, nullable=True, comment="高度")
    duration = Column(Float, nullable=True, comment="视频时长(秒)")
    cost_time = Column(Float, nullable=True, comment="生成耗时(秒)")
    
    error_msg = Column(Text, nullable=True, comment="错误信息")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<AIVideoTask(id={self.id}, task_id={self.task_id}, status={self.status})>"
