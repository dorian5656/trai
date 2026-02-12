#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/tools/media/media_func.py
# 作者：liuhd
# 日期：2026-02-12 11:30:00
# 描述：媒体工具业务逻辑

import time
import shutil
import tempfile
import json
from pathlib import Path
from fastapi import UploadFile, HTTPException
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.media_utils import MediaUtils
from backend.app.utils.feishu_utils import feishu_bot
from backend.app.utils.pg_utils import PGUtils

class MediaFunc:
    """媒体处理业务逻辑"""

    @staticmethod
    async def _record_tool_usage(
        user_id: str, 
        tool_name: str, 
        input_source: str, 
        output_result: str = None, 
        params: dict = None, 
        status: str = "success", 
        error_msg: str = None, 
        duration_ms: float = 0
    ):
        """记录工具使用日志"""
        try:
            sql = """
            INSERT INTO tool_usage_logs (
                user_id, tool_name, input_source, output_result, params, status, error_msg, duration_ms
            ) VALUES (
                :user_id, :tool_name, :input_source, :output_result, :params, :status, :error_msg, :duration_ms
            )
            """
            params_json = json.dumps(params, ensure_ascii=False) if params else None
            await PGUtils.execute_update(sql, {
                "user_id": user_id,
                "tool_name": tool_name,
                "input_source": input_source,
                "output_result": output_result,
                "params": params_json,
                "status": status,
                "error_msg": error_msg,
                "duration_ms": duration_ms
            })
        except Exception as e:
            logger.error(f"记录工具日志失败: {e}")

    @staticmethod
    async def _generic_convert(
        file: UploadFile, 
        allowed_exts: tuple, 
        convert_func: callable, 
        user_id: str, 
        success_msg_type: str = "转换成功",
        max_size_mb: int = 50,
        **kwargs
    ) -> dict:
        start_time = time.time()
        filename = file.filename
        tool_name = "video2gif" # 暂时硬编码，可优化
        
        if not filename.lower().endswith(allowed_exts):
             raise HTTPException(status_code=400, detail=f"不支持的文件类型: {filename}. 仅支持 {allowed_exts}")

        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            input_path = temp_dir / filename
            file_size = 0
            
            try:
                # 分块读取并检查大小
                with input_path.open("wb") as buffer:
                    while content := await file.read(1024 * 1024):  # 1MB chunks
                        file_size += len(content)
                        if file_size > max_size_mb * 1024 * 1024:
                            raise HTTPException(status_code=400, detail=f"文件过大，限制 {max_size_mb}MB")
                        buffer.write(content)
            except HTTPException as he:
                raise he
            except Exception as e:
                logger.error(f"保存文件失败: {e}")
                raise HTTPException(status_code=500, detail="文件保存失败")

            try:
                # 调用转换函数，传入 kwargs
                result = await convert_func(input_path, user_id=user_id, **kwargs)
                duration = time.time() - start_time
                
                # result is url (str)
                # 尝试上传 GIF 预览图到飞书 (用于卡片展示)
                image_key = None
                gif_path = input_path.with_suffix('.gif')
                if gif_path.exists():
                    try:
                        # 读取文件内容上传
                        image_key = feishu_bot.upload_image(gif_path.read_bytes())
                    except Exception as e:
                        logger.warning(f"飞书上传预览图失败: {e}")

                # 构造飞书交互式卡片
                card = {
                    "config": {
                        "wide_screen_mode": True
                    },
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"✅ {success_msg_type}"
                        },
                        "template": "green"
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "fields": [
                                {
                                    "is_short": True,
                                    "text": {
                                        "tag": "lark_md",
                                        "content": f"**文件**: {filename}"
                                    }
                                },
                                {
                                    "is_short": True,
                                    "text": {
                                        "tag": "lark_md",
                                        "content": f"**用户**: {user_id}"
                                    }
                                },
                                {
                                    "is_short": True,
                                    "text": {
                                        "tag": "lark_md",
                                        "content": f"**耗时**: {duration:.2f}s"
                                    }
                                }
                            ]
                        }
                    ]
                }

                # 如果有预览图，添加图片模块
                if image_key:
                    card["elements"].append({
                        "tag": "img",
                        "img_key": image_key,
                        "alt": {
                            "tag": "plain_text",
                            "content": "GIF 预览"
                        },
                        "mode": "fit_horizontal"
                    })

                # 添加跳转按钮
                card["elements"].append({
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "下载/查看 GIF"
                            },
                            "url": result,
                            "type": "primary"
                        }
                    ]
                })

                # 发送卡片消息
                feishu_bot.send_webhook_card(card, webhook_token=settings.FEISHU_IMAGE_GEN_WEBHOOK_TOKEN)
                
                # 记录到数据库
                await MediaFunc._record_tool_usage(
                    user_id=user_id,
                    tool_name=tool_name,
                    input_source=filename,
                    output_result=result,
                    params=kwargs,
                    status="success",
                    duration_ms=duration * 1000
                )
                
                return {"code": 200, "msg": "OK", "data": {"url": result, "filename": Path(result).name, "duration": f"{duration:.2f}s"}}
            except Exception as e:
                logger.error(f"转换失败: {e}")
                error_msg = str(e)
                duration = time.time() - start_time
                
                feishu_bot.send_webhook_message(f"❌ {success_msg_type}失败: {filename}\n错误: {error_msg}")
                
                # 记录失败日志
                await MediaFunc._record_tool_usage(
                    user_id=user_id,
                    tool_name=tool_name,
                    input_source=filename,
                    params=kwargs,
                    status="failed",
                    error_msg=error_msg,
                    duration_ms=duration * 1000
                )
                
                raise HTTPException(status_code=500, detail=f"转换失败: {error_msg}")

    @staticmethod
    async def convert_video_to_gif(file: UploadFile, user_id: str = "system", fps: int = 10, width: int = 320) -> dict:
        return await MediaFunc._generic_convert(
            file, 
            ('.mp4', '.avi', '.mov', '.mkv'), 
            MediaUtils.video_to_gif, 
            user_id, 
            "视频转GIF",
            fps=fps,
            width=width
        )
