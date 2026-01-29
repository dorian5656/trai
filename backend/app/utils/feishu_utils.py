#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/feishu_utils.py
# 作者：whf
# 日期：2026-01-27
# 描述：飞书工具类 (Webhook/Token)

import requests
from backend.app.config import settings
from backend.app.utils.logger import logger

class FeishuBot:
    """
    飞书机器人工具类
    """
    
    def __init__(self):
        # 默认使用配置中的 FEISHU_TRAI_WEBHOOK_TOKEN
        self.default_webhook_token = settings.FEISHU_TRAI_WEBHOOK_TOKEN
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET

    def send_webhook_message(self, content: str, webhook_token: str = None):
        """
        发送文本消息到飞书群 (Webhook方式)
        :param content: 消息内容
        :param webhook_token: 可选，指定发送的群 Webhook Token。如果不传则使用默认配置。
        """
        token = webhook_token or self.default_webhook_token
        
        if not token:
            logger.warning("未配置 Webhook Token, 跳过发送飞书消息")
            return

        url = f"https://open.feishu.cn/open-apis/bot/v2/hook/{token}"
        headers = {"Content-Type": "application/json"}
        data = {
            "msg_type": "text",
            "content": {
                "text": content
            }
        }

        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            # 飞书V2 Webhook有时返回code,有时StatusCode,视具体版本
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info(f"飞书消息发送成功: {content[:20]}...")
            else:
                logger.error(f"飞书消息发送失败: {result}")
        except Exception as e:
            logger.error(f"飞书消息发送异常: {e}")

    def get_tenant_access_token(self):
        """
        获取 tenant_access_token (用于调用飞书服务端API)
        """
        if not self.app_id or not self.app_secret:
            logger.error("未配置 FEISHU_APP_ID 或 FEISHU_APP_SECRET, 无法获取 tenant_access_token")
            return None

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            if result.get("code") == 0:
                logger.info("获取 tenant_access_token 成功")
                return result.get("tenant_access_token")
            else:
                logger.error(f"获取 tenant_access_token 失败: {result}")
                return None
        except Exception as e:
            logger.error(f"获取 tenant_access_token 异常: {e}")
            return None

# 单例实例
feishu_bot = FeishuBot()
