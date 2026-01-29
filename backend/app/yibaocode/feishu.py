"""
飞书服务工具类

说明:
- 支持通过 Webhook 发送文本與图片消息;
- 支持使用租户凭证上传图片获取 image_key;
- 可用于医保(NHSA)推送通知集成;
- 读取 .env 中的 FEISHU_WEBHOOK_TOKEN、FEISHU_APP_ID、FEISHU_APP_SECRET;
"""
import os
import json
from typing import Optional, List, Dict, Any
import requests
from dotenv import load_dotenv
try:
    from logger import logger
except ImportError:
    from .logger import logger

load_dotenv()

FEISHU_WEBHOOK_TOKEN = os.getenv("FEISHU_WEBHOOK_TOKEN", "")
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_NHSA_WEBHOOK_TOKEN = os.getenv("FEISHU_NHSA_WEBHOOK_TOKEN", "")
FEISHU_CONTACT_WEBHOOK_TOKEN = os.getenv("FEISHU_CONTACT_WEBHOOK_TOKEN", "")

class FeishuService:
    """
    飞书服务类
    
    功能:
    - 通过 Webhook 发送文本消息;
    - 通过租户凭证上传图片并返回 image_key;
    - 使用 Webhook 发送图片消息;
    - 提供医保(NHSA)通知快捷发送方法;
    """
    def __init__(self) -> None:
        """
        初始化服务实例
        
        从环境变量读取配置:
        - FEISHU_WEBHOOK_TOKEN: Webhook Token
        - FEISHU_APP_ID: 应用 ID
        - FEISHU_APP_SECRET: 应用密钥
        """
        self.base_url = "https://open.feishu.cn/open-apis"
        self.webhook_token = FEISHU_WEBHOOK_TOKEN
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self._tenant_token: Optional[str] = None

    @property
    def webhook_url(self) -> Optional[str]:
        """
        获取 Webhook 完整地址
        """
        if not self.webhook_token:
            return None
        if self.webhook_token.startswith("http"):
            return self.webhook_token
        return f"{self.base_url}/bot/v2/hook/{self.webhook_token}"

    def get_tenant_access_token(self, force: bool = False) -> str:
        """
        获取租户凭证(Access Token)
        
        参数:
        - force: 是否强制刷新
        """
        if self._tenant_token and not force:
            return self._tenant_token
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("tenant_access_token")
        if not token:
            raise RuntimeError(f"no tenant_access_token: {data}")
        self._tenant_token = token
        logger.bind(target="feishu", action="get_token").info("ok")
        return token

    def send_group_message(self, content: str, at_user_ids: Optional[List[str]] = None, webhook_token: Optional[str] = None) -> bool:
        """
        发送文本消息到群(Webhook)
        
        参数:
        - content: 文本内容
        - at_user_ids: 可选, 需要 @ 的用户 ID 列表
        - webhook_token: 可选, 覆盖默认的 Webhook Token
        """
        token = webhook_token or self.webhook_token or FEISHU_NHSA_WEBHOOK_TOKEN
        if not token:
            logger.warning("未配置飞书 Webhook Token")
            return False
        url = token if token.startswith("http") else f"{self.base_url}/bot/v2/hook/{token}"
        msg_text = content
        if at_user_ids:
            for uid in at_user_ids:
                msg_text += f" <at user_id=\"{uid}\"></at>"
        payload = {"msg_type": "text", "content": {"text": msg_text}}
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=20)
            if resp.status_code == 200:
                return True
            logger.error(f"飞书 Webhook HTTP 错误: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"飞书 Webhook 发送失败: {e}")
            return False

    def upload_image(self, image_path: str) -> str:
        """
        上传图片并返回 image_key
        
        参数:
        - image_path: 图片绝对路径
        """
        token = self.get_tenant_access_token()
        url = f"{self.base_url}/im/v1/images"
        with open(image_path, "rb") as f:
            files = {"image": f}
            data = {"image_type": "message"}
            resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, files=files, data=data, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            image_key = (data.get("data") or {}).get("image_key")
            if not image_key:
                raise RuntimeError(f"未返回 image_key: {data}")
            logger.bind(target="feishu", action="upload_image").info("ok")
            return image_key

    def send_image_to_webhook(self, image_key: str, webhook_token: Optional[str] = None) -> bool:
        """
        通过 Webhook 发送图片消息
        
        参数:
        - image_key: 上传后返回的 image_key
        - webhook_token: 可选, 覆盖默认的 Webhook Token
        """
        token = webhook_token or self.webhook_token or FEISHU_NHSA_WEBHOOK_TOKEN
        if not token:
            logger.warning("未配置飞书 Webhook Token")
            return False
        url = token if token.startswith("http") else f"{self.base_url}/bot/v2/hook/{token}"
        payload = {"msg_type": "image", "content": {"image_key": image_key}}
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=20)
            if resp.status_code == 200:
                return True
            logger.error(f"飞书 Webhook HTTP 错误: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"飞书 Webhook 图片发送失败: {e}")
            return False
    
    def send_nhsa_message(self, title: str, message: str, at_user_ids: Optional[List[str]] = None, webhook_token: Optional[str] = None) -> bool:
        """
        发送医保(NHSA)通知到群(Webhook)
        
        参数:
        - title: 标题, 如 "医保任务状态"
        - message: 详细内容
        - at_user_ids: 可选, 需要 @ 的用户 ID 列表
        - webhook_token: 可选, 覆盖默认的 Webhook Token
        """
        content = f"[医保通知] {title}\n{message}"
        target_token = webhook_token or FEISHU_NHSA_WEBHOOK_TOKEN or self.webhook_token
        ok = self.send_group_message(content, at_user_ids=at_user_ids, webhook_token=target_token)
        return ok
    
    def send_contact_message(self, name: str, phone: str, product: str, region: str, ip: str = None, ip_location: str = None) -> bool:
        """
        发送联系人留资信息
        """
        token = FEISHU_CONTACT_WEBHOOK_TOKEN or self.webhook_token
        if not token:
            logger.warning("未配置联系人留资 Webhook Token")
            return False
            
        title = "收到新的官网留资信息"
        content = [
            f"【姓名】： {name}",
            f"【电话】： {phone}",
            f"【感兴趣产品】： {product}",
            f"【区域】： {region}"
        ]
        
        if ip:
            content.append(f"【IP地址】： {ip}")
        if ip_location:
            content.append(f"【IP归属地】： {ip_location}")
        
        return self.send_rich_post(title, content, webhook_token=token)
    
    def send_rich_post(self, title: str, lines: List[str], webhook_token: Optional[str] = None) -> bool:
        token = webhook_token or self.webhook_token or FEISHU_NHSA_WEBHOOK_TOKEN
        if not token:
            logger.warning("未配置飞书 Webhook Token")
            return False
        url = token if token.startswith("http") else f"{self.base_url}/bot/v2/hook/{token}"
        content_blocks = [[{"tag": "text", "text": line}] for line in lines]
        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": content_blocks
                    }
                }
            }
        }
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=20)
            if resp.status_code == 200:
                return True
            logger.error(f"飞书卡片 HTTP 错误: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"飞书卡片发送失败: {e}")
            return False
    
    def send_post(self, title: str, paragraphs: List[List[Dict[str, Any]]], webhook_token: Optional[str] = None) -> bool:
        """
        发送富文本卡片(Post)，支持混合元素:
        - 文本: {"tag":"text","text":"内容"}
        - 链接: {"tag":"a","text":"标题","href":"https://..."}
        - @用户: {"tag":"at","user_id":"ou_xxx"}
        - 图片: {"tag":"img","image_key":"img_xxx"}
        
        参数:
        - title: 卡片标题
        - paragraphs: 段落列表，每个段落是元素列表
        - webhook_token: 可选，覆盖默认 Token
        """
        token = webhook_token or self.webhook_token or FEISHU_NHSA_WEBHOOK_TOKEN
        if not token:
            logger.warning("未配置飞书 Webhook Token")
            return False
        url = token if token.startswith("http") else f"{self.base_url}/bot/v2/hook/{token}"
        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": paragraphs
                    }
                }
            }
        }
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=20)
            if resp.status_code == 200:
                return True
            logger.error(f"飞书卡片 HTTP 错误: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"飞书卡片发送失败: {e}")
            return False

feishu_service = FeishuService()
