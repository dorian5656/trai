#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/monitor/__init__.py
# 作者：whf
# 日期：2026-01-26
# 描述：监控模块路由聚合

from fastapi import APIRouter
from backend.app.routers.monitor.hardware_router import router as hardware_router
from backend.app.routers.monitor.ai_models_router import router as ai_models_router
from backend.app.routers.monitor.health_router import router as health_router

router = APIRouter()

# 注册硬件监控路由 (包括 /env/gpu, /env/system)
router.include_router(hardware_router)

# 注册 AI 模型监控路由 (包括 /models)
router.include_router(ai_models_router)

# 注册健康检查路由 (包括 /health)
router.include_router(health_router)
