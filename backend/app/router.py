#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/router.py
# 作者：whf
# 日期：2026-01-26
# 描述：统一路由注册

from fastapi import APIRouter
from backend.app.routers.rrdsppg import predict_router as rrdsppg
from backend.app.routers.auth import auth_router
from backend.app.routers.users import users_router
from backend.app.routers.ai import chat_router as ai_chat
from backend.app.routers.ai import image_router as ai_image
from backend.app.routers.upload import upload_router
from backend.app.routers import monitor
from backend.app.routers import wecom
from backend.app.routers import dify
from backend.app.routers import speech

api_router = APIRouter()

# 注册 认证路由
api_router.include_router(auth_router.router, prefix="/auth", tags=["认证管理"])
# 注册 用户路由
api_router.include_router(users_router.router, prefix="/users", tags=["用户管理"])
# 注册 上传路由
api_router.include_router(upload_router.router, prefix="/upload", tags=["文件上传"])
# 注册 AI 路由
api_router.include_router(ai_chat.router, prefix="/ai", tags=["AI 智能对话"])
api_router.include_router(ai_image.router, prefix="/ai/image", tags=["AI 图像服务"])
# 注册 监控路由
api_router.include_router(monitor.router, prefix="/monitor", tags=["系统监控"])
# 注册 人人都是品牌官 业务路由
api_router.include_router(rrdsppg.router, prefix="/rrdsppg", tags=["人人都是品牌官"])
# 注册 企业微信路由
api_router.include_router(wecom.router, prefix="/wecom", tags=["企业微信"])
# 注册 Dify 路由
api_router.include_router(dify.router, prefix="/dify", tags=["Dify AI"])
# 注册 语音路由
api_router.include_router(speech.router, prefix="/speech", tags=["语音服务"])
