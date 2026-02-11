#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/routers/tools/image/image_router.py
# 作者：wuhao
# 日期：2026-02-10 09:35:00
# 描述：图像处理路由定义

from fastapi import APIRouter, UploadFile, File, Form, Query, Depends
from backend.app.routers.tools.image.image_func import ImageFunc
from backend.app.utils.response import ResponseHelper as Response, ResponseCode
from backend.app.utils.dependencies import get_current_active_user
from backend.app.utils.image_utils import ImageUtils
from backend.app.utils.logger import logger
from backend.app.config import settings
import shutil
import uuid
import os
from pathlib import Path

router = APIRouter(
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

@router.post("/image2ico", summary="图片转 ICO")
async def image_to_ico(
    file: UploadFile = File(...),
    sizes: str = Form(None, description="尺寸列表，例如: 256,128,64"),
    current_user = Depends(get_current_active_user)
):
    """
    将上传的图片转换为 ICO 图标
    - 支持 PNG, JPG, BMP 等常见格式
    - 自动保留透明度 (RGBA)
    - 转换后自动上传 S3
    """
    # 兼容 Pydantic 模型对象或字典
    user_id = getattr(current_user, "username", None)
    if not user_id and isinstance(current_user, dict):
         user_id = current_user.get("username")
    
    # 1. 保存上传文件到临时目录
    # 使用 settings.BASE_DIR 确保路径正确，避免出现 backend/backend/static/...
    temp_dir = settings.BASE_DIR / "static/uploads/temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    file_ext = Path(file.filename).suffix
    temp_input_path = temp_dir / f"{uuid.uuid4()}{file_ext}"
    temp_output_path = temp_input_path.with_suffix(".ico")
    
    try:
        with open(temp_input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. 解析尺寸参数
        size_list = None
        if sizes:
            try:
                # 假设输入格式为 "256,128,64"
                dims = [int(s.strip()) for s in sizes.split(",") if s.strip().isdigit()]
                if dims:
                    size_list = [(d, d) for d in dims]
            except Exception as e:
                logger.warning(f"解析尺寸参数失败: {e}, 将使用默认尺寸")
                
        # 3. 执行转换
        result_url = await ImageUtils.image_to_ico(
            input_path=str(temp_input_path),
            output_path=str(temp_output_path),
            sizes=size_list,
            user_id=user_id
        )
        
        # 如果 result_url 是 http 开头，说明上传 S3 成功，本地文件可以删除
        if result_url.startswith("http") and temp_output_path.exists():
            try:
                os.remove(temp_output_path)
            except Exception as e:
                logger.warning(f"删除临时 ICO 文件失败: {e}")
        
        # 4. 返回结果
        return Response.success(data={
            "url": result_url,
            "filename": temp_output_path.name
        }, msg="转换成功")
        
    except Exception as e:
        logger.error(f"图片转 ICO 接口异常: {e}")
        return Response.error(code=ResponseCode.BAD_REQUEST, msg=f"转换失败: {str(e)}")
    finally:
        # 清理输入文件
        if temp_input_path.exists():
            try:
                os.remove(temp_input_path)
            except:
                pass

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
