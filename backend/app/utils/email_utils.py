#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/email_utils.py
# 作者：liuhd
# 日期：2026-02-03
# 描述：邮件发送工具类 (支持 SMTP SSL)

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from typing import List, Union, Optional
from backend.app.config import settings
from backend.app.utils.logger import logger

class EmailUtils:
    """
    邮件发送工具类
    支持发送文本、HTML邮件，支持多收件人
    """

    @staticmethod
    def send_email(
        subject: str,
        content: str,
        receivers: Optional[Union[str, List[str]]] = None,
        content_type: str = "plain"
    ) -> bool:
        """
        发送邮件

        Args:
            subject (str): 邮件主题
            content (str): 邮件内容
            receivers (Union[str, List[str]], optional): 收件人列表. 默认为 None (使用配置的默认收件人).
            content_type (str, optional): 内容类型 ("plain" 或 "html"). 默认为 "plain".

        Returns:
            bool: 发送成功返回 True, 失败返回 False
        """
        # 1. 获取配置
        mail_host = settings.EMAIL_HOST
        mail_port = settings.EMAIL_PORT
        mail_user = settings.EMAIL_USER
        mail_pass = settings.EMAIL_PASSWORD
        
        if not all([mail_host, mail_port, mail_user, mail_pass]):
            logger.warning("邮件配置不完整，无法发送邮件。请检查 .env 配置 (EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD)")
            return False

        # 2. 处理收件人
        if receivers is None:
            receivers = settings.EMAIL_TO_DEFAULT
            
        if not receivers:
            logger.warning("未指定收件人，且无默认收件人配置")
            return False
            
        if isinstance(receivers, str):
            # 支持逗号分隔的字符串
            if "," in receivers:
                receivers = [r.strip() for r in receivers.split(",")]
            else:
                receivers = [receivers]

        # 3. 构造邮件对象
        message = MIMEMultipart()
        
        # 标准化 From 头 (避免 550 Error)
        # 格式: Display Name <email@example.com>
        message['From'] = formataddr(("TRAI Notification", mail_user))
        
        # 收件人显示处理
        if len(receivers) == 1:
            message['To'] = receivers[0] # 单个直接显示邮箱
        else:
            message['To'] = ",".join(receivers) # 多个用逗号连接
            
        message['Subject'] = Header(subject, 'utf-8')

        # 添加正文
        message.attach(MIMEText(content, content_type, 'utf-8'))

        try:
            logger.info(f"正在连接 SMTP 服务器: {mail_host}:{mail_port} ...")
            
            # 4. 连接 SMTP 服务器 (使用 SSL)
            if mail_port == 465:
                smtp_obj = smtplib.SMTP_SSL(mail_host, mail_port)
            else:
                # 非 SSL 连接 (通常是 25 端口，或 587 STARTTLS)
                smtp_obj = smtplib.SMTP(mail_host, mail_port)
                # 如果是 587，可能需要 starttls
                if mail_port == 587:
                    smtp_obj.starttls()
            
            # 5. 登录
            logger.info(f"正在登录邮箱: {mail_user} ...")
            smtp_obj.login(mail_user, mail_pass)
            
            # 6. 发送
            logger.info(f"正在发送邮件给: {receivers} ...")
            smtp_obj.sendmail(mail_user, receivers, message.as_string())
            
            # 7. 退出
            smtp_obj.quit()
            logger.success("✅ 邮件发送成功")
            return True
            
        except smtplib.SMTPException as e:
            logger.error(f"❌ 邮件发送失败 (SMTP错误): {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 邮件发送失败 (未知错误): {e}")
            return False

if __name__ == "__main__":
    # 简单的本地测试逻辑 (非正式单元测试)
    # 注意：直接运行此文件可能无法加载 .env，建议使用单独的 test 脚本或在项目环境下运行
    pass
