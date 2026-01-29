import httpx
from typing import Dict, Any, Optional
try:
    from logger import logger
except ImportError:
    from .logger import logger
import os
from dotenv import load_dotenv
import requests

load_dotenv()

# 微信小程序配置 (五号文档)
WECHAT_APPID = os.getenv("WUHAOWENDANG_APPID", "mock_appid")
WECHAT_SECRET = os.getenv("WUHAOWENDANG_SECRET", "mock_secret")
TEMPLATE_ID = os.getenv("WUHAOWENDANG_TEMPLATE_ID", "jJu5iFfNhdxb47ed163lVPpRvq8qEci7yINOd611Z7I")

# 企业微信群机器人配置
WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"
WECHAT_ROBOT_KEY = os.getenv("WECHAT_ROBOT_KEY", "d4bebcd5-0788-4d50-83c0-5cc273882168") # 默认使用项目中的 Key

class WeChatService:
    """
    处理微信小程序操作和群机器人通知的服务。
    """

    @staticmethod
    def send_group_message(content: str, key: str = None) -> bool:
        """
        发送文本消息到企业微信群机器人。
        
        Args:
            content: 要发送的文本内容。
            key: 可选的机器人 Key。如果未提供，则使用默认的 WECHAT_ROBOT_KEY。
        """
        robot_key = key or WECHAT_ROBOT_KEY
        if not robot_key:
            logger.warning("未配置企业微信机器人 Key。")
            return False
            
        url = f"{WECHAT_WEBHOOK_URL}?key={robot_key}"
        headers = {"Content-Type": "application/json"}
        data = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }
        
        try:
            # 使用 requests 进行同步调用以保持兼容性，或切换到 httpx 进行异步调用
            response = requests.post(url, json=data, headers=headers, timeout=5)
            if response.status_code == 200:
                # 检查微信 API 响应代码
                res_json = response.json()
                if res_json.get('errcode') == 0:
                    return True
                else:
                    logger.error(f"企业微信 webhook 错误: {res_json}")
                    return False
            else:
                logger.error(f"企业微信 webhook HTTP 错误: {response.text}")
                return False
        except Exception as e:
            logger.error(f"发送企业微信群消息失败: {e}")
            return False

    @staticmethod
    async def get_access_token() -> str:
        """
        获取微信 Access Token。
        在实际场景中，应该缓存此 Token（Redis/内存），因为它在 7200 秒后过期。
        """
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WECHAT_APPID}&secret={WECHAT_SECRET}"
        
        # 对于没有真实凭据的开发/演示环境，返回模拟 token
        if WECHAT_APPID == "mock_appid":
            logger.info("使用模拟微信 access token")
            return "mock_access_token"

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url)
                data = resp.json()
                if "access_token" in data:
                    return data["access_token"]
                else:
                    logger.error(f"获取 access token 失败: {data}")
                    return ""
            except Exception as e:
                logger.error(f"获取 access token 网络错误: {e}")
                return ""

    @staticmethod
    async def send_subscribe_message(openid: str, page: str, data: Dict[str, Any]) -> bool:
        """
        向用户发送订阅消息。
        
        Args:
            openid: 用户的 OpenID
            page: 点击通知时跳转的页面
            data: 模板数据
        """
        token = await WeChatService.get_access_token()
        if not token:
            return False

        url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}"
        
        payload = {
            "touser": openid,
            "template_id": TEMPLATE_ID,
            "page": page,
            "data": data,
            "miniprogram_state": "developer" # developer, trial, formal
        }

        logger.info(f"准备向 {openid} 发送微信消息。Payload: {payload}")

        if token == "mock_access_token":
            logger.success(f"[MOCK] 成功向 {openid} 发送订阅消息")
            return True

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json=payload)
                result = resp.json()
                if result.get("errcode") == 0:
                    logger.success(f"成功向 {openid} 发送订阅消息")
                    return True
                else:
                    logger.error(f"发送消息失败: {result}")
                    return False
            except Exception as e:
                logger.error(f"发送消息网络错误: {e}")
                return False

wechat_service = WeChatService()
