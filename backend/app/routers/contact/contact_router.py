#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/contact/contact_router.py
# 作者：liuhd
# 日期：2026-02-03
# 描述：联系人/留资路由模块

from fastapi import APIRouter
from backend.app.routers.contact.contact_func import (
    ContactManager,
    LeadSubmitRequest,
    LeadSubmitResponse
)

router = APIRouter()

@router.post("/lead", response_model=LeadSubmitResponse, summary="提交客户留资信息")
async def submit_lead(request: LeadSubmitRequest) -> LeadSubmitResponse:
    """
    提交客户留资信息接口
    
    Args:
        request (LeadSubmitRequest): 客户留资请求参数
            - name (str): 姓名 (必填)
            - phone (str): 电话 (必填)
            - product (str, optional): 感兴趣产品
            - region (str, optional): 区域
            - clientIp (str, optional): 客户端IP
            - userAgent (str, optional): 浏览器UA
            - submitTime (str, optional): 提交时间 (ISO格式)
            - submissionId (str, optional): 提交ID (前端生成，用于去重)
        
    Returns:
        LeadSubmitResponse: 提交结果响应
            - code (int): 状态码 (200: 成功)
            - msg (str): 提示信息
            - data (dict): 返回数据
                - id (int): 新生成的留资记录ID
    """
    return await ContactManager.submit_lead(request)
