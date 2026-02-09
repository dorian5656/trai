#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/tools/doc/doc_router.py
# 作者：liuhd
# 日期：2026-02-09 10:35:00
# 描述：文档工具路由定义

from fastapi import APIRouter, UploadFile, File, Form, Depends
from backend.app.routers.tools.doc.doc_func import DocFunc
from backend.app.utils.dependencies import get_current_active_user

router = APIRouter()

@router.post("/md2pdf", summary="Markdown 转 PDF", description="上传 Markdown 文件，转换为 PDF 并返回下载链接")
async def convert_md_to_pdf(
    file: UploadFile = File(..., description="Markdown 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    Markdown 转 PDF 接口
    - 自动处理 Mermaid 图表
    - 上传结果到 S3
    - 发送飞书通知
    """
    # 使用当前登录用户的 username 作为 user_id
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_md_to_pdf(file, user_id=user_id)
