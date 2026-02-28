#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/routers/ai/music_router.py
# 作者：wuhao
# 日期：2026-02-12 17:19:55
# 描述：AI 文生音乐路由

from fastapi import APIRouter

from backend.app.routers.ai.music_func import MusicGenRequest, MusicGenResponse, music_manager
from backend.app.utils.response import ResponseHelper, ResponseModel

router = APIRouter()


@router.post("/generations", response_model=ResponseModel, summary="文生音乐 (ACE-Step1.5 / text-to-audio)")
async def generate_music(request: MusicGenRequest) -> ResponseModel:
    """
    文生音乐接口

    Args:
        request (MusicGenRequest): 生成请求参数
            - prompt (str): 音乐描述提示词 (必填)
            - model_id (str): 模型ID (默认 ACE-Step/Ace-Step1.5)
            - lyrics (str, optional): 自定义歌词
            - duration (float, optional): 目标时长(秒)

    Returns:
        ResponseModel: 统一响应结构 (data=MusicGenResponse)
    """
    try:
        result: MusicGenResponse = await music_manager.generate_music(request)
        return ResponseHelper.success(result)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))


@router.post("/generations/with_cover", response_model=ResponseModel, summary="文生音乐+封面 (ACE-Step1.5 + Tongyi)")
async def generate_music_with_cover(request: MusicGenRequest) -> ResponseModel:
    """
    文生音乐+封面接口

    Args:
        request (MusicGenRequest): 生成请求参数 (同文生音乐)

    Returns:
        ResponseModel: 统一响应结构 (data=MusicWithCoverResponse)
    """
    try:
        from backend.app.routers.ai.music_func import MusicWithCoverResponse
        result: MusicWithCoverResponse = await music_manager.generate_music_with_cover(request)
        return ResponseHelper.success(result)
    except Exception as e:
        return ResponseHelper.error(msg=str(e))
