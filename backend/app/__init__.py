#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/__init__.py
# 作者：whf
# 日期：2026-01-26
# 描述：应用初始化

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from backend.app.utils.logger import logger
from backend.app.config import settings

def create_app() -> FastAPI:
    """
    创建 FastAPI 应用实例
    """
    from backend.app.router import api_router
    from backend.app.utils.net_utils import NetUtils
    from backend.app.middlewares.log_middleware import RequestLogMiddleware

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="TRAI 后端服务 (Modular Structure)",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
    )

    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册请求日志中间件
    app.add_middleware(RequestLogMiddleware)

    # 注册路由
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # 引入环境同步工具
    from backend.app.utils.env_sync import EnvSync
    from backend.app.routers.monitor.ai_models_func import ModelManager

    @app.on_event("startup")
    async def startup_event():
        logger.info(f"服务启动: {settings.PROJECT_NAME} ({settings.ENV})")
        
        # 0. 数据库初始化与 Dify 同步
        from backend.app.utils.db_init import DBInitializer
        logger.info("🚀 [Startup] 正在检查数据库并同步 Dify 应用配置...")
        await DBInitializer().run()
        
        # 1. 同步环境配置到数据库
        await EnvSync.sync()

        # 2. 初始化 AI 模型管理器 (创建默认文件夹)
        await ModelManager.initialize()

        # 3. 预加载视频生成模型 (Eager Loading)
        # 根据需求：自动选择显存最空闲的 GPU 并加载
        from backend.app.routers.ai.video_func import VideoManager
        # 使用 asyncio.create_task 后台加载，不阻塞服务启动响应，但会占用 GPU 资源
        import asyncio
        asyncio.create_task(VideoManager.preload_model())

        # 初始化静态资源目录 (backend/static)
        # 用于存放 exe、图片等静态文件
        base_path = Path(__file__).resolve().parent.parent
        static_path = base_path / "static"
        
        # 定义需要自动创建的子目录结构
        # 包含: doc(文档), exe(可执行), other(其他), uploads(上传), releases(发布), gen(生成)
        sub_dirs = ["doc", "exe", "other", "uploads", "releases", "gen", "uploads/temp"]
        
        if not static_path.exists():
            static_path.mkdir(parents=True, exist_ok=True)
            logger.success(f"新建静态资源根目录: {static_path}")
        
        # 自动创建分类子目录
        for sub_dir in sub_dirs:
            sub_path = static_path / sub_dir
            if not sub_path.exists():
                sub_path.mkdir(parents=True, exist_ok=True)
                logger.success(f"新建静态分类目录: {sub_dir}")

        logger.info(f"静态资源目录检查完成: {static_path} ({', '.join(sub_dirs)})")

        # 挂载静态目录 (可选，方便直接访问)
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

        local_ip = NetUtils.get_local_ip()
        logger.info(f"监听地址: http://{settings.HOST}:{settings.PORT}")
        logger.info(f"本机地址: http://{local_ip}:{settings.PORT}")
        logger.info(f"文档地址: http://{local_ip}:{settings.PORT}{settings.API_V1_STR}/docs")
        logger.info(f"静态资源: http://{local_ip}:{settings.PORT}/static")

        # 启动时同步企业微信数据
        if settings.WECOM_SYNC_ON_STARTUP:
            logger.info("🚀 [Startup] 检测到 WECOM_SYNC_ON_STARTUP=true, 开始同步企业微信数据...")
            # 异步执行，不阻塞启动? 
            # 这里的 startup_event 是支持 async 的，所以 await 会阻塞启动直到同步完成。
            # 如果数据量巨大建议后台执行，但考虑到是启动初始化，阻塞以确保数据就绪也是合理的。
            try:
                from backend.app.routers.wecom.wecom_func import wecom_service
                await wecom_service.sync_data()
                logger.success("✅ [Startup] 企业微信数据同步完成")
            except Exception as e:
                logger.error(f"❌ [Startup] 企业微信数据同步失败: {e}")
        else:
            logger.info("ℹ️ [Startup] WECOM_SYNC_ON_STARTUP=false, 跳过企业微信数据同步")

    @app.get("/")
    async def root():
        return {"code": 200, "msg": "OK", "data": {"service": settings.PROJECT_NAME}}

    return app

# app = create_app()
