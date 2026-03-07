#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/app/utils/iflytek_asr_client.py
# 作者: Gemini
# 日期: 2026-03-03
# 描述: 讯飞实时语音转写 WebSocket 客户端

import asyncio
import base64
import hashlib
import hmac
import json
from urllib.parse import urlencode
import ssl
from datetime import datetime
from time import mktime
from wsgiref.handlers import format_date_time

import websockets

from backend.app.config import settings
from backend.app.utils.logger import logger

class IFlytekASRClient:
    """
    用于对接讯飞实时语音转写服务的客户端。
    """
    def __init__(self, on_result_callback, on_error_callback):
        self.app_id = settings.IFLYTEK_APPID
        self.api_key = settings.IFLYTEK_API_KEY
        self.api_secret = settings.IFLYTEK_API_SECRET
        self.host = "office-api-ast-dx.iflyaisol.com"
        self.uri = "/ast/communicate/v1"
        self.websocket = None
        self.on_result = on_result_callback
        self.on_error = on_error_callback
        self._is_connected = False
        self._session_id = None
        self._receiver_task = None

    def _create_url(self):
        """
        生成带有认证参数的 WebSocket URL。
        """
        # 根据讯飞大模型版实时转写文档生成 URL
        utc_now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+0000')
        
        # 构造 base_string
        params = {
            "appId": self.app_id,
            "accessKeyId": self.api_key,
            "lang": "autodialect",
            "samplerate": 16000,
            "audio_encode": "pcm_s16le",
            "utc": utc_now,
            "role_type": 2, # 开启说话人分离（盲分）
        }
        
        # 1. 按参数名升序排序
        sorted_params = sorted(params.items())
        
        # 2. 对键值进行 URL 编码并拼接
        base_string_parts = []
        for key, value in sorted_params:
            base_string_parts.append(f"{urlencode({key: value}).replace('=', '=')}")
        base_string = "&".join(base_string_parts)

        # 3. HmacSHA1 加密
        signature = hmac.new(self.api_secret.encode('utf-8'), base_string.encode('utf-8'), digestmod=hashlib.sha1).digest()
        
        # 4. Base64 编码
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        # 5. 添加签名到参数中
        params["signature"] = signature_b64
        
        # 最终 URL
        return f"wss://{self.host}{self.uri}?{urlencode(params)}"

    async def connect(self):
        """
        建立到讯飞的 WebSocket 连接。
        """
        if self._is_connected:
            logger.warning("讯飞客户端已连接，无需重复连接。")
            return

        auth_url = self._create_url()
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            logger.info("正在连接到讯飞 ASR 服务...")
            self.websocket = await websockets.connect(auth_url, ssl=ssl_context)
            self._is_connected = True
            logger.success("✅ 成功连接到讯飞 ASR 服务。")
            self._receiver_task = asyncio.create_task(self._receive_loop())
        except Exception as e:
            logger.error(f"❌ 连接讯飞 ASR 服务失败: {e}")
            self._is_connected = False
            await self.on_error(f"连接讯飞 ASR 服务失败: {e}")

    async def _receive_loop(self):
        """
        循环接收来自讯飞的消息。
        """
        try:
            while self._is_connected:
                message = await self.websocket.recv()
                message_data = json.loads(message)
                
                msg_type = message_data.get("msg_type")

                if msg_type == "action":
                    action_data = message_data.get("data", {})
                    if action_data.get("action") == "started":
                        self._session_id = action_data.get('sessionId')
                        logger.info(f"讯飞会话开始，Session ID: {self._session_id}")
                    else:
                        logger.warning(f"收到未知的讯飞 action: {message}")

                elif msg_type == "result":
                    res_type = message_data.get("res_type")
                    if res_type == "asr":
                        # 正常的识别结果
                        await self.on_result(message_data.get('data'))
                    elif res_type == "frc":
                        # 异常结果
                        error_desc = message_data.get("data", {}).get("desc", "未知错误")
                        logger.error(f"讯飞服务返回异常: {error_desc}")
                        await self.on_error(error_desc)
                    else:
                        logger.warning(f"收到未知的讯飞 result 类型: {message}")
                
                else:
                    logger.warning(f"收到未知的讯飞消息类型 (msg_type): {message}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"与讯飞的连接已关闭: {e}")
            await self.on_error("讯飞服务器主动断开连接") # 通知上层
        except Exception as e:
            logger.error(f"处理讯飞消息时出错: {e}")
            await self.on_error(f"处理讯飞消息时出错: {e}")
        finally:
            self._is_connected = False

    async def send_audio(self, audio_chunk):
        """
        发送音频数据块。
        """
        if not self._is_connected or not self.websocket:
            logger.error("无法发送音频：未连接到讯飞服务。")
            return

        try:
            await self.websocket.send(audio_chunk)
        except Exception as e:
            logger.error(f"发送音频到讯飞时出错: {e}")
            await self.on_error(f"发送音频到讯飞时出错: {e}")
            self._is_connected = False

    async def close(self):
        """
        关闭与讯飞的连接。
        """
        if not self.websocket:
            return

        logger.info("正在关闭与讯飞的连接...")
        try:
            if self._is_connected and self._session_id:
                await self.websocket.send(json.dumps({"end": True, "sessionId": self._session_id}))
            
            if self._receiver_task and not self._receiver_task.done():
                await asyncio.wait_for(self._receiver_task, timeout=5.0)

        except asyncio.TimeoutError:
            logger.warning("等待讯飞关闭连接超时。")
        except Exception as e:
            logger.error(f"关闭讯飞连接时出错: {e}")
        finally:
            if self.websocket:
                try:
                    await self.websocket.close()
                except Exception:
                    pass
            self._is_connected = False
            logger.info("与讯飞的连接已关闭。")

