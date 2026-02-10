#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/routers/tools/image/image_router.py
# 作者：wuhao
# 日期：2026-02-10 09:35:00
# 描述：图像处理路由定义

from fastapi import APIRouter, UploadFile, File, Form, Query
from backend.app.routers.tools.image.image_func import ImageFunc
from backend.app.utils.response import Response, ResponseCode

router = APIRouter(
    prefix="/tools/image",
    tags=["Tools-Image"],
    responses={404: {"description": "Not found"}},
)

@router.post("/convert", summary="图片格式转换")
async def convert_image(
    file: UploadFile = File(..., description="上传的图片文件"),
    format: str = Form("JPEG", description="目标格式 (JPEG/PNG/WEBP)"),
    quality: int = Form(85, description="图片质量 (1-100)")
):
    """
    转换图片格式或调整质量
    
    - **file**: 图片文件
    - **format**: 目标格式 (默认 JPEG)
    - **quality**: 质量 (默认 85)
    """
    try:
        result = await ImageFunc.convert_image(file, format, quality)
        return Response.success(data=result, msg="Convert successful")
    except Exception as e:
        return Response.error(code=ResponseCode.BAD_REQUEST, msg=str(e))

@router.post("/compress", summary="图片压缩到指定大小")
async def compress_image(
    file: UploadFile = File(..., description="上传的图片文件"),
    target_mb: float = Form(..., description="目标大小 (MB), 如 3.0")
):
    """
    智能压缩图片到指定文件大小
    
    - **file**: 图片文件
    - **target_mb**: 目标文件大小 (MB)
    
    注意: 会优先降低质量，若不满足则会缩小尺寸。输出格式默认为 JPEG。
    """
    try:
        result = await ImageFunc.compress_image(file, target_mb)
        return Response.success(data=result, msg="Compression successful")
    except Exception as e:
        return Response.error(code=ResponseCode.BAD_REQUEST, msg=str(e))

@router.post("/resize", summary="图片尺寸调整")
async def resize_image(
    file: UploadFile = File(..., description="上传的图片文件"),
    width: int = Form(None, description="目标宽度 (px)"),
    height: int = Form(None, description="目标高度 (px)")
):
    """
    上传图片并调整尺寸
    
    - **file**: 图片文件
    - **width**: 目标宽度 (可选)
    - **height**: 目标高度 (可选)
    
    注意: width 和 height 至少需要提供一个。如果只提供一个，将保持纵横比缩放。
    """
    try:
        result = await ImageFunc.resize_image(file, width, height)
        return Response.success(data=result, msg="Resize successful")
    except Exception as e:
        return Response.error(code=ResponseCode.BAD_REQUEST, msg=str(e))
