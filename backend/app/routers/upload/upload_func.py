#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/upload/upload_func.py
# 作者：whf
# 日期：2026-01-27
# 描述：文件上传逻辑与模型

from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import Column, String, BigInteger, Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from backend.app.utils.pg_utils import Base

class UploadResponse(BaseModel):
    """
    文件上传响应
    """
    url: str = Field(..., description="文件访问 URL")
    filename: str = Field(..., description="原始文件名")
    size: int = Field(..., description="文件大小 (字节)")
    content_type: Optional[str] = Field(None, description="MIME 类型")
    local_path: Optional[str] = Field(None, description="本地存储路径 (仅内部调试用)")

class UserImage(Base):
    """用户图片表"""
    __tablename__ = "user_images"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(String(50), nullable=False, comment="用户ID")
    filename = Column(String(255), nullable=False, comment="原始文件名")
    s3_key = Column(String(500), nullable=False, comment="S3对象键")
    url = Column(String, nullable=False, comment="访问URL")
    size = Column(BigInteger, comment="文件大小")
    mime_type = Column(String(100), comment="MIME类型")
    module = Column(String(50), default="common", comment="所属模块")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    created_at = Column(DateTime, server_default=text("NOW()"), comment="创建时间")
    updated_at = Column(DateTime, server_default=text("NOW()"), onupdate=text("NOW()"), comment="更新时间")
