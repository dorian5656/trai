#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/wecom_utils.py
# 作者：whf
# 日期：2026-01-27
# 描述：企业微信工具类 (Webhook/通讯录)

import requests
from backend.app.config import settings
from backend.app.utils.logger import logger

class WeComBot:
    """
    企业微信机器人工具类
    """
    
    def __init__(self):
        self.webhook_key = settings.WECOM_TRAI_ROBOT_KEY
        # 企业微信 API 域名 (官方固定为 qyapi.weixin.qq.com)
        self.api_domain = "qyapi.weixin.qq.com"
        self.webhook_url = f"https://{self.api_domain}/cgi-bin/webhook/send?key={self.webhook_key}"

    def send_message(self, content: str):
        """
        发送文本消息到企业微信群
        :param content: 消息内容
        """
        if not self.webhook_key:
            logger.warning("未配置 WECOM_TRAI_ROBOT_KEY, 跳过发送企业微信消息")
            return

        headers = {"Content-Type": "application/json"}
        data = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }

        try:
            response = requests.post(self.webhook_url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            if result.get("errcode") == 0:
                logger.info(f"企业微信消息发送成功: {content[:20]}...")
            else:
                logger.error(f"企业微信消息发送失败: {result}")
        except Exception as e:
            logger.error(f"企业微信消息发送异常: {e}")

class WeComApp:
    """
    企业微信应用工具类 (API交互)
    """
    def __init__(self, corp_id: str = None, corp_secret: str = None):
        self.corp_id = corp_id or settings.WECOM_CORP_ID
        self.corp_secret = corp_secret or settings.WECOM_CORP_SECRET
        self.access_token = None
        self.token_expires_at = 0
        
        if not self.corp_id or not self.corp_secret:
            logger.warning("未配置 WECOM_CORP_ID 或 WECOM_CORP_SECRET, 无法使用企业微信API")
            
        # 企业微信 API 域名
        self.api_domain = "qyapi.weixin.qq.com"

    def _get_access_token(self) -> str:
        """
        获取 Access Token (简单缓存)
        """
        import time
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        url = f"https://{self.api_domain}/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.corp_secret}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") == 0:
                self.access_token = data.get("access_token")
                # 提前 200 秒过期，防止边界问题
                self.token_expires_at = time.time() + data.get("expires_in", 7200) - 200
                return self.access_token
            else:
                logger.error(f"获取企业微信 Access Token 失败: {data}")
                raise Exception(f"Get Token Failed: {data}")
        except Exception as e:
            logger.error(f"获取企业微信 Access Token 异常: {e}")
            raise

    def get_user_info(self, user_id: str):
        """
        获取用户信息
        """
        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/user/get?access_token={token}&userid={user_id}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"获取企业微信用户信息失败: {e}")
            raise

    def get_user_id_by_code(self, code: str):
        """
        通过 OAuth2 code 获取成员信息 (UserId)
        """
        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/user/getuserinfo?access_token={token}&code={code}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") == 0:
                # 成功: {"UserId":"USERID", "DeviceId":"...", "errcode":0, ...}
                # 失败(非企业成员): {"OpenId":"OPENID", "errcode":0, ...}
                if "UserId" in data:
                    return data["UserId"]
                else:
                    logger.warning(f"Code换取信息成功但无UserId (可能是非企业成员): {data}")
                    return None
            else:
                logger.error(f"Code换取成员信息失败: {data}")
                raise Exception(f"WeCom Code Error: {data.get('errmsg')}")
        except Exception as e:
            logger.error(f"获取企业微信成员UserId异常: {e}")
            raise

    def get_department_list(self, department_id: int = None):
        """
        获取部门列表
        """
        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/department/list?access_token={token}"
        if department_id is not None:
            url += f"&id={department_id}"
        
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"获取企业微信部门列表失败: {e}")
            raise

    def get_department_users(self, department_id: int, fetch_child: int = 0, simple: bool = False):
        """
        获取部门成员
        :param department_id: 部门ID
        :param fetch_child: 1/0：是否递归获取子部门下面的成员
        :param simple: True=获取成员摘要(user/simplelist), False=获取成员详情(user/list)
        """
        token = self._get_access_token()
        api_path = "user/simplelist" if simple else "user/list"
        url = f"https://{self.api_domain}/cgi-bin/{api_path}?access_token={token}&department_id={department_id}&fetch_child={fetch_child}"
        
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"获取企业微信部门成员失败: {e}")
            raise

# 单例实例
wecom_bot = WeComBot()
wecom_app = WeComApp()
