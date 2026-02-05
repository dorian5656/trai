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

    def upload_image(self, image_data: bytes) -> str:
        """
        上传图片到飞书并获取 image_key
        :param image_data: 图片二进制数据
        :return: image_key or None
        """
        token = self.get_tenant_access_token()
        if not token:
            return None

        url = "https://open.feishu.cn/open-apis/im/v1/images"
        headers = {"Authorization": f"Bearer {token}"}
        
        # 飞书上传图片要求 multipart/form-data，且 key 为 image，并指定 image_type
        files = {
            "image": ("image.png", image_data, "image/png")
        }
        data = {
            "image_type": "message"
        }

        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            result = response.json()
            if result.get("code") == 0:
                image_key = result.get("data", {}).get("image_key")
                logger.info(f"飞书图片上传成功, image_key: {image_key}")
                return image_key
            else:
                logger.error(f"飞书图片上传失败: {result}")
                return None
        except Exception as e:
            logger.error(f"飞书图片上传异常: {e}")
            return None

    def send_webhook_post(self, title: str, content: list, webhook_token: str = None):
        """
        发送富文本消息 (Post) 到飞书 Webhook (带重试机制)
        :param title: 标题
        :param content: 富文本内容列表 (二维数组，外层是段落，内层是元素)
        :param webhook_token: Webhook Token
        """
        import time
        token = webhook_token or self.default_webhook_token
        if not token:
            return

        url = f"https://open.feishu.cn/open-apis/bot/v2/hook/{token}"
        headers = {"Content-Type": "application/json"}
        
        post_content = {
            "zh_cn": {
                "title": title,
                "content": content
            }
        }
        
        data = {
            "msg_type": "post",
            "content": {
                "post": post_content
            }
        }

        max_retries = 3
        retry_delay = 2  # 初始延迟 2秒

        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=data, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                # 检查是否成功
                if result.get("code") == 0 or result.get("StatusCode") == 0:
                    logger.info(f"飞书 Post 消息发送成功: {title}")
                    return
                
                # 检查是否频率限制 (11232: frequency limited)
                if result.get("code") == 11232:
                    logger.warning(f"飞书频率限制 (Attempt {attempt+1}/{max_retries}): {result.get('msg')}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                        continue
                else:
                    logger.error(f"飞书 Post 消息发送失败: {result}")
                    break
                    
            except Exception as e:
                logger.error(f"飞书 Post 消息发送异常: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    break
        
        # 如果重试后仍然失败，尝试降级为纯文本发送 (提取 content 中的文本信息)
        logger.warning(f"飞书 Post 消息发送最终失败，尝试降级为文本发送: {title}")
        try:
            text_lines = [f"【{title}】"]
            for paragraph in content:
                for element in paragraph:
                    if element.get("tag") == "text":
                        text_lines.append(element.get("text", ""))
                    elif element.get("tag") == "img":
                        text_lines.append("(图片已生成，但富文本发送失败，请查看链接)")
                    elif element.get("tag") == "a":
                        text_lines.append(f"{element.get('text', 'link')}: {element.get('href', '')}")
            
            fallback_content = "\n".join(text_lines)
            self.send_webhook_message(fallback_content, webhook_token)
        except Exception as e:
            logger.error(f"飞书降级发送也失败: {e}")

# 单例实例
feishu_bot = FeishuBot()
