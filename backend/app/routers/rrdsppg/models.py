#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/rrdsppg/models.py
# 作者：whf
# 日期：2026-02-06
# 描述：人人都是品牌官 - 数据库模型

from sqlalchemy import Column, String, BigInteger, Integer, Float, DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.app.utils.pg_utils import Base

class RrdsppgPrediction(Base):
    """人人都是品牌官-预测记录表"""
    __tablename__ = "rrdsppg_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    task_id = Column(BigInteger, comment="任务ID")
    user_id = Column(BigInteger, comment="用户ID")
    type = Column(Integer, comment="任务类型")
    itzx = Column(Integer, comment="来源标识")
    
    template_path = Column(Text, comment="原始模板图片URL")
    target_path = Column(Text, comment="原始目标图片URL")
    
    # 转存后的 S3 地址
    template_s3_url = Column(Text, comment="模板图片S3地址")
    target_s3_url = Column(Text, comment="目标图片S3地址")
    
    similarity_score = Column(Float, comment="相似度得分")
    result_json = Column(JSONB, comment="完整预测结果")
    
    created_at = Column(DateTime, server_default=text("NOW()"), comment="创建时间")
