#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/meeting/meeting_func.py
# 作者：whf
# 日期：2026-03-07
# 描述：会议记录业务逻辑封装

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Text, text as sql_text, select, and_, desc
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.app.utils.pg_utils import Base
from backend.app.utils.logger import logger


class Meeting(Base):
    """会议记录表"""
    __tablename__ = "meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sql_text("gen_random_uuid()"))
    user_id = Column(String(50), nullable=False, comment="用户ID")
    title = Column(String(200), nullable=False, comment="会议标题")
    text = Column(Text, comment="会议逐字稿")
    summary = Column(Text, comment="会议纪要")
    created_at = Column(DateTime, server_default=sql_text("NOW()"), comment="创建时间")
    updated_at = Column(DateTime, server_default=sql_text("NOW()"), onupdate=sql_text("NOW()"), comment="更新时间")


class MeetingManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        pass

    async def create_meeting(self, user_id: str, title: str, text: str, summary: Optional[str] = None, db=None) -> dict:
        """
        创建会议记录
        
        Args:
            user_id: 用户ID
            title: 会议标题
            text: 会议逐字稿
            summary: 会议纪要（可选）
            db: 数据库会话
            
        Returns:
            创建成功的会议记录
        """
        try:
            meeting = Meeting(
                user_id=user_id,
                title=title,
                text=text,
                summary=summary
            )
            db.add(meeting)
            await db.commit()
            await db.refresh(meeting)

            logger.info(f"✅ [Meeting] 会议记录创建成功: {meeting.id}")
            
            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "id": str(meeting.id),
                    "title": meeting.title,
                    "text": meeting.text,
                    "summary": meeting.summary,
                    "created_at": meeting.created_at.isoformat() if meeting.created_at else None
                }
            }
        except Exception as e:
            logger.error(f"❌ [Meeting] 创建会议记录失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"创建失败: {str(e)}"}

    async def get_meeting_list(self, user_id: str, db=None, page: int = 1, size: int = 20) -> dict:
        """
        获取会议记录列表
        
        Args:
            user_id: 用户ID
            db: 数据库会话
            page: 页码
            size: 每页数量
            
        Returns:
            会议记录列表
        """
        try:
            # 计算总数
            count_query = select(func.count()).select_from(Meeting).where(Meeting.user_id == user_id)
            total = await db.scalar(count_query)

            # 分页查询
            offset = (page - 1) * size
            query = (
                select(Meeting)
                .where(Meeting.user_id == user_id)
                .order_by(desc(Meeting.created_at))
                .offset(offset)
                .limit(size)
            )
            
            result = await db.execute(query)
            meetings = result.scalars().all()

            items = []
            for meeting in meetings:
                items.append({
                    "id": str(meeting.id),
                    "title": meeting.title,
                    "created_at": meeting.created_at.isoformat() if meeting.created_at else None
                })

            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "items": items,
                    "total": total,
                    "page": page,
                    "size": size
                }
            }
        except Exception as e:
            logger.error(f"❌ [Meeting] 获取会议列表失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"获取失败: {str(e)}"}

    async def get_meeting_detail(self, meeting_id: str, user_id: str, db=None) -> dict:
        """
        获取会议记录详情
        
        Args:
            meeting_id: 会议ID
            user_id: 用户ID
            db: 数据库会话
            
        Returns:
            会议记录详情
        """
        try:
            query = select(Meeting).where(
                and_(
                    Meeting.id == meeting_id,
                    Meeting.user_id == user_id
                )
            )
            
            result = await db.execute(query)
            meeting = result.scalar_one_or_none()

            if not meeting:
                return {"code": 404, "msg": "会议记录不存在"}

            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "id": str(meeting.id),
                    "title": meeting.title,
                    "text": meeting.text,
                    "summary": meeting.summary,
                    "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
                    "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None
                }
            }
        except Exception as e:
            logger.error(f"❌ [Meeting] 获取会议详情失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"获取失败: {str(e)}"}

    async def delete_meeting(self, meeting_id: str, user_id: str, db=None) -> dict:
        """
        删除会议记录
        
        Args:
            meeting_id: 会议ID
            user_id: 用户ID
            db: 数据库会话
            
        Returns:
            删除结果
        """
        try:
            query = select(Meeting).where(
                and_(
                    Meeting.id == meeting_id,
                    Meeting.user_id == user_id
                )
            )
            
            result = await db.execute(query)
            meeting = result.scalar_one_or_none()

            if not meeting:
                return {"code": 404, "msg": "会议记录不存在"}

            await db.delete(meeting)
            await db.commit()

            logger.info(f"✅ [Meeting] 会议记录删除成功: {meeting_id}")
            
            return {"code": 200, "msg": "删除成功"}
        except Exception as e:
            logger.error(f"❌ [Meeting] 删除会议记录失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"删除失败: {str(e)}"}


# 全局单例
meeting_service = MeetingManager()
