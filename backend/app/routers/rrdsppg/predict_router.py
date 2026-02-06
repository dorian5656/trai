#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/rrdsppg/predict_router.py
# 作者：whf
# 日期：2026-01-26
# 描述：人人都是品牌官 - 智能预测接口 (Router)

from fastapi import APIRouter, File, UploadFile, Form, Request
from typing import Optional
from backend.app.utils.response import ResponseHelper
from backend.app.utils.logger import logger
from backend.app.routers.rrdsppg.predict_func import PredictManager

router = APIRouter()

@router.on_event("startup")
async def startup_event():
    """
    服务启动时加载模型和检查环境
    """
    await PredictManager.initialize()

@router.get("/check_gpu", summary="检查GPU可用性")
async def check_gpu():
    """
    检查系统 GPU 可用性 (Torch & Paddle)

    Returns:
        dict: 包含 torch_gpu 和 paddle_gpu 布尔值的状态字典
    """
    try:
        info = PredictManager.check_gpu()
        return ResponseHelper.success(data=info)
    except Exception as e:
        logger.error(f"GPU检测失败: {e}")
        return ResponseHelper.error(msg=f"GPU检测失败: {str(e)}")

from pydantic import BaseModel, Field

class YoloRequest(BaseModel):
    # conf: Optional[float] = Field(0.25, description="置信度阈值") # 已废弃
    taskId: Optional[int] = Field(None, description="任务ID", examples=[1001])
    userId: Optional[int] = Field(None, description="用户ID", examples=[101])
    type: Optional[int] = Field(None, description="类型", examples=[1])
    itzx: Optional[int] = Field(None, description="来源标识", examples=[0])
    templatePath: Optional[str] = Field(None, description="模板图片URL (用于比对)", examples=["https://example.com/template.jpg"])
    targetPath: Optional[str] = Field(None, description="目标图片URL", examples=["https://example.com/target.jpg"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "taskId": 1001,
                "userId": 101,
                "type": 1,
                "itzx": 0,
                "templatePath": "https://example.com/template.jpg",
                "targetPath": "https://example.com/target.jpg"
            }
        }
    }

import os

@router.post("/predict", summary="智能预测 (自动路由)", openapi_extra={
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "taskId": {"type": "integer", "description": "任务ID"},
                        "userId": {"type": "integer", "description": "用户ID"},
                        "type": {"type": "integer", "description": "任务类型"},
                        "itzx": {"type": "integer", "description": "来源标识", "default": 0},
                        "templatePath": {"type": "string", "description": "模板图片URL"},
                        "targetPath": {"type": "string", "description": "目标图片URL"},
                        "file": {"type": "string", "format": "binary", "description": "图片文件"}
                    }
                }
            },
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "taskId": {"type": "integer", "description": "任务ID"},
                        "userId": {"type": "integer", "description": "用户ID"},
                        "type": {"type": "integer", "description": "任务类型"},
                        "itzx": {"type": "integer", "description": "来源标识", "default": 0},
                        "templatePath": {"type": "string", "description": "模板图片URL"},
                        "targetPath": {"type": "string", "description": "目标图片URL"}
                    }
                }
            }
        }
    }
})
async def predict_auto(
    request: Request
):
    """
    通用预测接口 (支持 Multipart Form 或 JSON Body)

    根据 type 参数自动路由：
    - 公众号转发 (OCR) -> PaddleOCR
    - 视频号 (YOLO + OCR) -> 组合逻辑

    **Args:**

    - `taskId` (int): 任务ID
    - `userId` (int): 用户ID
    - `type` (int): 任务类型
        - `1997929948761825282`: 公众号转发 (OCR)
        - `其他`: 视频号/通用 (YOLO + OCR)
    - `itzx` (int): 来源标识
    - `templatePath` (str): 模板图片URL (用于比对)
    - `targetPath` (str): 目标图片URL
    - `file` (UploadFile): 图片文件 (仅 multipart/form-data 支持)

    **Returns:**

    - `dict`: 预测结果
    """
    try:
        # 手动解析请求
        content_type = request.headers.get("content-type", "").lower()
        
        file = None
        itzx = 0
        targetPath = None
        templatePath = None
        type_val = None 
        taskId = None
        userId = None
        
        if "multipart/form-data" in content_type:
            form = await request.form()
            file = form.get("file")
            if isinstance(file, str): file = None
            itzx = int(form.get("itzx", 0) or 0)
            targetPath = form.get("targetPath")
            templatePath = form.get("templatePath")
            type_val = int(form.get("type", 0) or 0)
            taskId = int(form.get("taskId", 0) or 0)
            userId = int(form.get("userId", 0) or 0)
            
        elif "application/json" in content_type:
            try:
                body = await request.json()
                itzx = int(body.get("itzx", 0) or 0)
                targetPath = body.get("targetPath")
                templatePath = body.get("templatePath")
                type_val = int(body.get("type", 0) or 0)
                taskId = int(body.get("taskId", 0) or 0)
                userId = int(body.get("userId", 0) or 0)
            except Exception as e:
                logger.error(f"JSON解析失败: {e}, Content-Type: {content_type}")
                # 尝试读取 raw body 打印出来以便调试
                try:
                    raw_body = await request.body()
                    logger.error(f"Raw Body: {raw_body.decode('utf-8', errors='ignore')}")
                except:
                    pass
        else:
            logger.warning(f"未知的 Content-Type: {content_type}")
        
        # 必须有 targetPath 和 templatePath
        if not targetPath or not templatePath:
             return ResponseHelper.error(msg="预测任务必须提供 targetPath 和 templatePath")

        # 获取配置的任务类型ID
        OFFICIAL_ACCOUNT_TYPE = int(os.getenv("RRDSPPG_TASK_TYPE_OFFICIAL_ACCOUNT", "1997929948761825282"))
        
        # 构造请求对象 (复用 OcrRequest 模型)
        # 注意: PredictManager.predict_composite 接受 request 对象 (具有 templatePath/targetPath/itzx 属性)
        # PredictManager.predict_ocr_url 也接受 request 对象
        
        req_obj = OcrRequest(
            templatePath=templatePath,
            targetPath=targetPath,
            taskId=taskId or 0,
            userId=userId or 0,
            type=type_val,
            itzx=itzx
        )
        
        # 路由逻辑
        if type_val == OFFICIAL_ACCOUNT_TYPE:
            # 公众号 -> OCR
            results = await PredictManager.predict_ocr_url(req_obj)
        else:
            # 视频号 (或其他) -> 组合逻辑 (OCR + YOLO)
            results = await PredictManager.predict_composite(req_obj)
            
        return ResponseHelper.success(data=results)
            
    except Exception as e:
        return ResponseHelper.error(msg=f"预测失败: {str(e)}")

@router.post("/predict/yolo", summary="YOLO 目标检测", openapi_extra={
    "requestBody": {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "taskId": {"type": "integer", "description": "任务ID"},
                        "userId": {"type": "integer", "description": "用户ID"},
                        "type": {"type": "integer", "description": "任务类型"},
                        "itzx": {"type": "integer", "description": "来源标识", "default": 0},
                        "templatePath": {"type": "string", "description": "模板图片URL"},
                        "targetPath": {"type": "string", "description": "目标图片URL"},
                        "file": {"type": "string", "format": "binary", "description": "图片文件"}
                    }
                }
            },
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "taskId": {"type": "integer", "description": "任务ID"},
                        "userId": {"type": "integer", "description": "用户ID"},
                        "type": {"type": "integer", "description": "任务类型"},
                        "itzx": {"type": "integer", "description": "来源标识", "default": 0},
                        "templatePath": {"type": "string", "description": "模板图片URL"},
                        "targetPath": {"type": "string", "description": "目标图片URL"}
                    }
                }
            }
        }
    }
})
async def predict_yolo(
    request: Request
):
    """
    上传图片进行 YOLO 目标检测 (支持 Multipart Form 或 JSON Body)

    根据 type 参数自动路由：
    - 公众号转发 (OCR) -> PaddleOCR (ID配置在环境变量)
    - 视频号 (YOLO) -> YOLO (ID配置在环境变量)

    **Args:**

    - `taskId` (int): 任务ID
    - `userId` (int): 用户ID
    - `type` (int): 任务类型
    - `itzx` (int): 来源标识
    - `templatePath` (str): 模板图片URL
    - `targetPath` (str): 目标图片URL
    - `file` (UploadFile): 图片文件 (仅 multipart/form-data 支持)

    **Returns:**

    - `dict`: 检测结果
    """
    try:
        # 手动解析请求
        content_type = request.headers.get("content-type", "")
        
        file = None
        # conf = 0.25 # 默认值
        itzx = 0
        targetPath = None
        templatePath = None
        type_val = None # 任务类型
        taskId = None
        userId = None
        
        if "multipart/form-data" in content_type:
            # Form Data 处理
            form = await request.form()
            file = form.get("file") # UploadFile or None
            if isinstance(file, str): file = None # 避免空字符串被当做文件
            
            # conf = float(form.get("conf", 0.25))
            itzx = int(form.get("itzx", 0) or 0)
            targetPath = form.get("targetPath")
            templatePath = form.get("templatePath")
            type_val = int(form.get("type", 0) or 0)
            taskId = int(form.get("taskId", 0) or 0)
            userId = int(form.get("userId", 0) or 0)
            
        elif "application/json" in content_type:
            # JSON Body 处理
            try:
                body = await request.json()
                # conf = float(body.get("conf", 0.25))
                itzx = int(body.get("itzx", 0) or 0)
                targetPath = body.get("targetPath")
                templatePath = body.get("templatePath")
                type_val = int(body.get("type", 0) or 0)
                taskId = int(body.get("taskId", 0) or 0)
                userId = int(body.get("userId", 0) or 0)
            except:
                pass
        
        # 自动路由逻辑
        
        # 获取配置的任务类型ID
        # 默认值保持与之前一致
        OFFICIAL_ACCOUNT_TYPE = int(os.getenv("RRDSPPG_TASK_TYPE_OFFICIAL_ACCOUNT", "1997929948761825282"))
        
        # 公众号转发 -> PaddleOCR
        if type_val == OFFICIAL_ACCOUNT_TYPE:
            if not targetPath or not templatePath:
                return ResponseHelper.error(msg="公众号转发任务(OCR)必须提供 targetPath 和 templatePath")
                
            # 构造 OCR 请求对象 (复用 OcrRequest 模型)
            ocr_req = OcrRequest(
                templatePath=templatePath,
                targetPath=targetPath,
                taskId=taskId or 0,
                userId=userId or 0,
                type=type_val,
                itzx=itzx
            )
            results = await PredictManager.predict_ocr_url(ocr_req)
            return ResponseHelper.success(data=results)
            
        # 默认 (包括视频号) -> YOLO
        else:
            results = await PredictManager.predict_yolo(file, itzx, targetPath, templatePath)
            return ResponseHelper.success(data=results)
            
    except Exception as e:
        return ResponseHelper.error(msg=f"预测失败: {str(e)}")

from pydantic import BaseModel, Field

from typing import Optional

class OcrRequest(BaseModel):
    templatePath: str = Field(..., description="模板图片URL")
    targetPath: str = Field(..., description="目标图片URL")
    taskId: int = Field(..., description="任务ID")
    userId: int = Field(..., description="用户ID")
    type: int = Field(..., description="类型")
    itzx: Optional[int] = Field(None, description="来源标识")

@router.post("/predict/paddleocr", summary="PaddleOCR 文字识别")
async def predict_ocr(
    request: OcrRequest
):
    """
    根据 URL 下载图片并进行 OCR 文字识别

    **Args:**

    - `request` (OcrRequest): OCR 请求参数
        - `templatePath` (str): 模板图片URL
        - `targetPath` (str): 目标图片URL
        - `taskId` (int): 任务ID
        - `userId` (int): 用户ID
        - `type` (int): 类型
        - `itzx` (int, optional): 来源标识

    **Returns:**

    - `dict`: OCR 识别结果
    """
    try:
        results = await PredictManager.predict_ocr_url(request)
        return ResponseHelper.success(data=results)
    except Exception as e:
        return ResponseHelper.error(msg=f"预测失败: {str(e)}")

@router.post("/hello", summary="Hello World接口")
async def hello():
    """
    Hello World 测试接口

    Returns:
        dict: {"message": "helloword"}
    """
    return ResponseHelper.success(data={"message": "helloword"})
