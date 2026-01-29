#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：run.py
# 作者：whf
# 日期：2026-01-26 16:15:00
# 描述：后端服务启动脚本

import uvicorn
import os
import sys
import sys
from pathlib import Path
from dotenv import load_dotenv

# 1. 优先加载环境变量 (必须在导入项目模块之前)
env_dev_path = Path(__file__).parent / ".env.dev"
env_path = Path(__file__).parent / ".env"
loaded_env = None

if env_dev_path.exists():
    load_dotenv(env_dev_path, override=True)
    loaded_env = env_dev_path
elif env_path.exists():
    load_dotenv(env_path)
    loaded_env = env_path

# 2. 添加项目根目录到 sys.path (必须在导入后端模块之前)
sys.path.append(str(Path(__file__).parent.parent))

# 3. 导入日志和模块
from backend.app.utils.logger import logger

if loaded_env:
    logger.success(f"已加载环境变量: {loaded_env}")
else:
    logger.warning(f"未找到环境变量文件: .env 或 .env.dev")

import asyncio
import argparse
from backend.app.utils.net_utils import NetUtils
from backend.app.utils.db_init import DBInitializer
from backend.app.utils.wecom_utils import wecom_bot
from backend.app.utils.feishu_utils import feishu_bot

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="TRAI Backend Service")
    parser.add_argument("--host", type=str, help="Bind host")
    parser.add_argument("--port", type=int, help="Bind port")
    parser.add_argument("--env", type=str, help="Environment (dev/prod)")
    args, _ = parser.parse_known_args()

    # 确定环境 (命令行 > 环境变量 > 默认值)
    env = args.env or os.getenv("ENV", "dev")
    
    # 确定 Host
    host = args.host or os.getenv("HOST", "0.0.0.0")

    # 确定 Port
    # 优先级: 命令行 > ENV_DEV_PORT > ENV_PORT > PORT > 默认值
    port = args.port
    if not port:
        # 依次尝试读取环境变量
        port_str = os.getenv("ENV_DEV_PORT")
        if not port_str:
            port_str = os.getenv("ENV_PORT")
        if not port_str:
            port_str = os.getenv("PORT")
            
        logger.info(f"Port resolution: ENV_DEV_PORT={os.getenv('ENV_DEV_PORT')}, ENV_PORT={os.getenv('ENV_PORT')}, PORT={os.getenv('PORT')}, Selected={port_str}")

        # 如果找到了配置，转换为整数
        if port_str:
            port = int(port_str)
        else:
            port = 5689 # 默认值

    # 将解析后的端口写入环境变量，确保 Settings 能读取到一致的端口
    os.environ["PORT"] = str(port)

    # 4. 自动检查并清理端口 (支持 Windows/Linux/MacOS)
    # 必须在启动任何服务前执行，确保端口可用
    if not NetUtils.check_and_release_port(port):
        logger.error(f"端口 {port} 占用且无法自动清理，服务启动终止")
        sys.exit(1)

    logger.info(f"正在启动服务 - 环境: {env}")
    
    # 检查 Dify 配置
    from backend.app.config import settings
    dify_apps = settings.DIFY_APPS
    if dify_apps:
        logger.info(f"🤖 [Dify] 检测到 {len(dify_apps)} 个 Dify 应用配置: {', '.join(dify_apps.keys())}")
    else:
        logger.warning("⚠️ [Dify] 未检测到任何 Dify 应用配置 (DIFY_GUANWANG_API_KEY 等)")

    # 扫描本地模型
    from backend.app.utils.ai_utils import AIUtils
    local_models = AIUtils.scan_local_models()
    if local_models:
        logger.info(f"🧠 [AI] 扫描到 {len(local_models)} 个本地模型: {', '.join(local_models)}")
        # 针对 Z-Image-Turbo 的特殊提示
        for model in local_models:
            if "Z-Image-Turbo" in model:
                logger.info(f"✨ [AI] 发现图像生成模型: {model}")
                logger.warning(f"⚠️ [AI] 注意: {model} 需要较大显存，若启动失败请检查 GPU 资源")
    else:
        logger.warning("⚠️ [AI] 未扫描到 backend/app/models 下的任何模型")

    # 检查 ModelScope 模型 (Qwen-VL 等)
    from backend.app.utils.modelscope_utils import ModelScopeUtils
    if ModelScopeUtils.check_model_exists("Qwen3-VL-4B-Instruct"):
        logger.info(f"👁️ [ModelScope] 检测到多模态模型: Qwen3-VL-4B-Instruct")
    else:
        logger.warning(f"⚠️ [ModelScope] 未检测到 Qwen3-VL-4B-Instruct, 相关功能将不可用")

    # 初始化数据库
    try:
        initializer = DBInitializer()
        asyncio.run(initializer.run())
        
        # 发送启动通知
        notify_msg = f"🚀 TRAI 后端服务已启动\n🌍 环境: {env}\n🔌 端口: {port}\n✅ 数据库初始化完成"
        wecom_bot.send_message(notify_msg)
        feishu_bot.send_webhook_message(notify_msg)
        
    except Exception as e:
        logger.error(f"数据库初始化过程发生错误: {e}")
        # 发送错误通知
        error_msg = f"❌ TRAI 后端服务启动异常\n❌ 错误信息: {str(e)}"
        wecom_bot.send_message(error_msg)
        feishu_bot.send_webhook_message(error_msg)

    # 启动服务
    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        reload=(env == "dev"),
        log_level="info"
    )

if __name__ == "__main__":
    main()
