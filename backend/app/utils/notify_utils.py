#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/notify_utils.py
# 作者：liuhd
# 日期：2026-02-09 10:45:00
# 描述：系统通知工具类 (飞书/邮件等)

from backend.app.utils.feishu_utils import feishu_bot
from backend.app.utils.logger import logger

class NotifyUtils:
    """系统通知工具"""

    @staticmethod
    def send_text(content: str):
        """发送文本通知"""
        try:
            feishu_bot.send_webhook_message(content)
        except Exception as e:
            logger.error(f"发送文本通知失败: {e}")

    @staticmethod
    def send_card(title: str, content: list):
        """发送卡片通知"""
        # TODO: 适配通用卡片格式转飞书卡片
        pass

    @staticmethod
    def send_file_upload_card(filename: str, url: str, user: str, size: int):
        """发送文件上传通知"""
        try:
            size_mb = size / 1024 / 1024
            size_str = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{size/1024:.2f} KB"
            
            card = {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📂 文件上传通知"
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
                                    "content": f"**文件名**\n{filename}"
                                }
                            },
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**用户**\n{user}"
                                }
                            },
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**大小**\n{size_str}"
                                }
                            }
                        ]
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "下载/预览"
                                },
                                "type": "primary",
                                "url": url
                            }
                        ]
                    }
                ]
            }
            feishu_bot.send_webhook_card(card)
        except Exception as e:
            logger.warning(f"飞书通知发送失败: {e}")

    @staticmethod
    def send_md_conversion_card(filename: str, url: str, duration: float):
        """发送 Markdown 转换完成卡片"""
        try:
            card = {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📄 文档转换完成"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "fields": [
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**源文件**\n{filename}"
                                }
                            },
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**耗时**\n{duration:.2f}s"
                                }
                            }
                        ]
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "下载 PDF"
                                },
                                "url": url,
                                "type": "primary"
                            }
                        ]
                    }
                ]
            }
            feishu_bot.send_webhook_card(card)
        except Exception as e:
            logger.error(f"发送卡片通知失败: {e}")
