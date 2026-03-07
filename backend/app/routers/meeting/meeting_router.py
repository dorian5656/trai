#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/meeting/meeting_router.py
# 作者：whf
# 日期：2026-03-07
# 描述：会议记录路由定义

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional

from backend.app.utils.pg_utils import get_db
from backend.app.utils.dependencies import get_current_user
from backend.app.utils.response import ResponseHelper
from .meeting_func import meeting_service

router = APIRouter(tags=["会议记录"])


class CreateMeetingRequest(BaseModel):
    """创建会议记录请求"""
    title: str = Field(..., min_length=1, max_length=200, description="会议标题")
    text: str = Field(..., min_length=1, description="会议逐字稿")
    summary: Optional[str] = Field(None, description="会议纪要")


@router.post("/create")
async def create_meeting(
    request: CreateMeetingRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    创建会议记录
    
    Args:
        request: 创建会议记录请求
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        创建成功的会议记录
    """
    user_id = getattr(current_user, "username", str(current_user.id))
    result = await meeting_service.create_meeting(
        user_id=user_id,
        title=request.title,
        text=request.text,
        summary=request.summary,
        db=db
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(result["data"], msg="创建成功")
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


@router.get("/list")
async def get_meeting_list(
    page: int = 1,
    size: int = 20,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    获取会议记录列表
    
    Args:
        page: 页码
        size: 每页数量
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        会议记录列表
    """
    user_id = getattr(current_user, "username", str(current_user.id))
    result = await meeting_service.get_meeting_list(
        user_id=user_id,
        db=db,
        page=page,
        size=size
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(result["data"], msg="获取成功")
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


@router.get("/detail/{meeting_id}")
async def get_meeting_detail(
    meeting_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    获取会议记录详情
    
    Args:
        meeting_id: 会议ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        会议记录详情
    """
    user_id = getattr(current_user, "username", str(current_user.id))
    result = await meeting_service.get_meeting_detail(
        meeting_id=meeting_id,
        user_id=user_id,
        db=db
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(result["data"], msg="获取成功")
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


@router.delete("/delete/{meeting_id}")
async def delete_meeting(
    meeting_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    删除会议记录
    
    Args:
        meeting_id: 会议ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        删除结果
    """
    user_id = getattr(current_user, "username", str(current_user.id))
    result = await meeting_service.delete_meeting(
        meeting_id=meeting_id,
        user_id=user_id,
        db=db
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(None, msg="删除成功")
    return ResponseHelper.error(code=result["code"], msg=result["msg"])
