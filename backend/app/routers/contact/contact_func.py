#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/contact/contact_func.py
# 作者：liuhd
# 日期：2026-02-03
# 描述：联系人/留资业务逻辑

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.logger import logger
from backend.app.utils.email_utils import EmailUtils

# =============================================================================
# Schema 定义
# =============================================================================

class LeadSubmitRequest(BaseModel):
    name: str = Field(..., description="姓名")
    phone: str = Field(..., description="电话")
    product: Optional[str] = Field(None, description="感兴趣产品")
    region: Optional[str] = Field(None, description="区域")
    clientIp: Optional[str] = Field(None, description="客户端IP")
    userAgent: Optional[str] = Field(None, description="浏览器UA")
    submitTime: Optional[str] = Field(None, description="提交时间 (ISO格式)")
    submissionId: Optional[str] = Field(None, description="提交ID (前端生成)")

class LeadSubmitResponse(BaseModel):
    code: int = 200
    msg: str = "提交成功"
    data: Optional[Dict[str, Any]] = None

# =============================================================================
# Manager 逻辑
# =============================================================================

class ContactManager:
    """
    联系人/留资业务管理器
    """
    
    @staticmethod
    async def submit_lead(request: LeadSubmitRequest) -> LeadSubmitResponse:
        """
        提交客户留资信息
        1. 存入数据库
        2. 发送邮件通知
        """
        try:
            # 1. 存入数据库
            insert_sql = """
            INSERT INTO customer_leads (
                name, phone, product, region, client_ip, user_agent, submission_id, submit_time
            ) VALUES (
                :name, :phone, :product, :region, :client_ip, :user_agent, :submission_id, :submit_time
            ) RETURNING id
            """
            
            # 处理时间格式
            submit_time_val = None
            if request.submitTime:
                try:
                    # 尝试解析 ISO 格式，如果失败则让数据库使用默认值或直接存字符串(需调整字段类型)
                    # 这里假设传入的是标准 ISO 字符串，PG 可以直接接收
                    submit_time_val = request.submitTime
                except:
                    pass
            
            # 执行插入
            # 注意: 如果 submission_id 重复，可能会抛出唯一约束异常
            # 我们可以先检查是否存在，或者捕获异常
            
            # 检查重复 (根据 submission_id)
            if request.submissionId:
                check_sql = "SELECT id FROM customer_leads WHERE submission_id = :submission_id"
                existing = await PGUtils.fetch_one(check_sql, {"submission_id": request.submissionId})
                if existing:
                    logger.warning(f"重复提交被拦截: {request.submissionId}")
                    return LeadSubmitResponse(msg="重复提交", data={"id": existing["id"]})

            params = {
                "name": request.name,
                "phone": request.phone,
                "product": request.product,
                "region": request.region,
                "client_ip": request.clientIp,
                "user_agent": request.userAgent,
                "submission_id": request.submissionId,
                "submit_time": submit_time_val or datetime.now()
            }
            
            result = await PGUtils.fetch_one_commit(insert_sql, params)
            new_id = result["id"] if result else None
            
            logger.success(f"客户留资已存入数据库: ID={new_id}, Name={request.name}")
            
            # 2. 发送邮件通知 (异步执行，或者同步执行但捕获异常不影响接口返回)
            # 这里选择同步执行但捕获异常，确保如果邮件发送失败也能记录日志
            try:
                subject = "【驼人官网】新的客户留资信息，请尽快处理！"
                content = f"""
                <h3>驼人官网有新的客户留资信息，请尽快处理！</h3>
                <hr>
                <p><b>【姓名】：</b> {request.name}</p>
                <p><b>【电话】：</b> {request.phone}</p>
                <p><b>【感兴趣产品】：</b> {request.product or '未填写'}</p>
                <p><b>【区域】：</b> {request.region or '未填写'}</p>
                <p><b>【IP地址】：</b> {request.clientIp or '未知'}</p>
                <p><b>【提交时间】：</b> {request.submitTime or '未知'}</p>
                <p><b>【浏览器UA】：</b> {request.userAgent or '未知'}</p>
                <p><b>【提交ID】：</b> {request.submissionId or '无'}</p>
                <hr>
                <p style="color:gray;font-size:12px;">此邮件由 TRAI 系统自动发送，请勿回复。</p>
                """
                
                email_success = EmailUtils.send_email(subject, content, content_type="html")
                if not email_success:
                    logger.error("客户留资邮件发送失败")
            except Exception as e:
                logger.error(f"发送邮件过程发生异常: {e}")
            
            # 3. 发送飞书通知
            try:
                feishu_content = f"🚀【官网留资通知】\n" \
                                 f"👤 姓名: {request.name}\n" \
                                 f"📞 电话: {request.phone}\n" \
                                 f"📦 产品: {request.product or '未填写'}\n" \
                                 f"📍 区域: {request.region or '未填写'}\n" \
                                 f"🌐 IP: {request.clientIp or '未知'}\n" \
                                 f"🕒 时间: {request.submitTime or '未知'}"
                
                # 使用专用 Webhook Token (如果配置了)
                token = settings.FEISHU_GUANWANGLIUZI_WEBHOOK_TOKEN or None
                feishu_bot.send_webhook_message(feishu_content, webhook_token=token)
            except Exception as e:
                logger.error(f"飞书通知发送失败: {e}")

            return LeadSubmitResponse(data={"id": new_id})
            
        except Exception as e:
            logger.error(f"提交客户留资失败: {e}")
            # 如果是唯一约束冲突，可以返回特定错误，这里统一般处理
            if "unique constraint" in str(e).lower():
                 return LeadSubmitResponse(msg="重复提交")
            raise e
