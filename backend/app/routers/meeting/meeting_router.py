#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/meeting/meeting_router.py
# 作者：whf
# 日期：2026-03-07
# 描述：会议记录路由定义

from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional, Any


from backend.app.utils.pg_utils import get_db
from backend.app.utils.dependencies import get_current_user
from backend.app.utils.response import ResponseHelper
from .meeting_func import meeting_service

router = APIRouter(tags=["会议"])


class CreateMeetingRequest(BaseModel):
    """创建新会议请求"""
    title: str = Field(default_factory=lambda: f"会议_{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", min_length=1, max_length=200, description="会议标题")
    start_time: datetime = Field(..., description="会议开始时间")


class AddRecordRequest(BaseModel):
    """添加发言记录请求"""
    meeting_id: int = Field(..., description="会议ID")
    user_id: str = Field(..., description="发言用户ID")
    speaker_name: str = Field(..., description="发言者姓名")
    content: str = Field(..., description="发言内容")
    record_time: datetime = Field(..., description="发言时间")
    audio_file_key: Optional[str] = Field(None, description="音频文件唯一标识")
    audio_file_url: Optional[str] = Field(None, description="音频文件访问URL")
    audio_duration: Optional[int] = Field(0, description="音频时长（秒）")
    audio_format: Optional[str] = Field(None, description="音频格式")
    audio_size: Optional[int] = Field(0, description="音频文件大小（字节）")
    parent_id: Optional[int] = Field(0, description="回复的父记录ID")


class UpdateRecordRequest(BaseModel):
    """更新发言记录请求"""
    record_id: int = Field(..., description="要更新的发言记录ID")
    content: str = Field(..., description="新的发言内容")


class UpdateMeetingRequest(BaseModel):
    """更新会议属性请求"""
    meeting_id: int = Field(..., description="会议ID")
    title: Optional[str] = Field(None, description="新的会议标题")





@router.post("/create", summary="创建新会议")
async def create_meeting(
    request: CreateMeetingRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    创建一个新的会议，返回会议主信息。
    
    Args:
        request: 创建新会议请求
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        创建成功的会议信息
    """
    user_id = current_user.username
    
    result = await meeting_service.create_meeting(
        user_id=user_id,
        title=request.title,
        start_time=request.start_time,
        db=db
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(result["data"], msg="创建成功")
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


@router.get("/list", summary="获取会议列表")
async def get_meeting_list(
    page: int = 1,
    size: int = 20,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    获取当前用户主持的会议列表。
    
    Args:
        page: 页码
        size: 每页数量
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        会议列表
    """
    user_id = current_user.username
    
    result = await meeting_service.get_meeting_list(
        user_id=user_id,
        db=db,
        page=page,
        size=size
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(result["data"], msg="获取成功")
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


@router.get("/detail/{meeting_id}", summary="获取会议详情")
async def get_meeting_detail(
    meeting_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    获取会议详情，包括所有发言记录。
    
    Args:
        meeting_id: 会议ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        会议详情
    """
    user_id = current_user.username
    
    result = await meeting_service.get_meeting_detail(
        meeting_id=meeting_id,
        user_id=user_id,
        db=db
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(result["data"], msg="获取成功")
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


@router.post("/delete/{meeting_id}", summary="删除会议")
async def delete_meeting(
    meeting_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    删除会议（逻辑删除）。
    
    Args:
        meeting_id: 会议ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        删除结果
    """
    user_id = current_user.username
    
    result = await meeting_service.delete_meeting(
        meeting_id=meeting_id,
        user_id=user_id,
        db=db
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(None, msg="删除成功")
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


@router.post("/record/add", summary="添加发言记录")
async def add_meeting_record(
    request: AddRecordRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    向指定会议中添加一条发言记录。
    
    Args:
        request: 添加发言记录请求
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        新创建的发言记录ID
    """


    result = await meeting_service.add_meeting_record(
        db=db,
        **request.dict()
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(result["data"], msg="添加成功")
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


@router.post("/record/update", summary="更新发言记录")
async def update_meeting_record(
    request: UpdateRecordRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    更新一条指定的发言记录内容。
    
    Args:
        request: 更新发言记录请求
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        更新结果
    """
    user_id = current_user.username
    
    result = await meeting_service.update_meeting_record(
        record_id=request.record_id,
        new_content=request.content,
        user_id=user_id,
        db=db
    )
    
    if result["code"] == 200:
        return ResponseHelper.success(None, msg=result["msg"])
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


@router.post("/update", summary="更新会议属性")
async def update_meeting(
    request: UpdateMeetingRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    更新会议的属性，如标题。
    """
    user_id = current_user.username

    # The meeting_id is passed as a positional argument, so it must be removed from the kwargs
    update_payload = request.dict(exclude_unset=True)
    update_payload.pop('meeting_id', None)

    result = await meeting_service.update_meeting(
        meeting_id=request.meeting_id,
        user_id=user_id,
        db=db,
        **update_payload
    )
    if result["code"] == 200:
        return ResponseHelper.success(None, msg=result["msg"])
    return ResponseHelper.error(code=result["code"], msg=result["msg"])


