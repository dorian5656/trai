#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/meeting/meeting_func.py
# 作者：whf
# 日期：2026-03-07
# 描述：会议记录业务逻辑封装

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Text, text as sql_text, select, and_, desc, update,
    BigInteger, SmallInteger, Integer, ForeignKey, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from backend.app.utils.pg_utils import Base
from backend.app.utils.logger import logger



# class Meeting(Base):
#     """会议记录表"""
#     __tablename__ = "meetings"
#
#     id = Column(UUID(as_uuid=True), primary_key=True, server_default=sql_text("gen_random_uuid()"))
#     user_id = Column(String(50), nullable=False, comment="用户ID")
#     title = Column(String(200), nullable=False, comment="会议标题")
#     text = Column(Text, comment="会议逐字稿")
#     summary = Column(Text, comment="会议纪要")
#     created_at = Column(DateTime, server_default=sql_text("NOW()"), comment="创建时间")
#     updated_at = Column(DateTime, server_default=sql_text("NOW()"), onupdate=sql_text("NOW()"), comment="更新时间")


class MeetingMain(Base):
    """会议主表"""
    __tablename__ = "meeting_main"

    id = Column(BigInteger, primary_key=True, comment="会议唯一ID（数据库自动生成）")
    meeting_title = Column(String(255), nullable=False, comment="会议标题")
    meeting_no = Column(String(64), nullable=False, unique=True, comment="会议编号（业务规则生成）")
    start_time = Column(TIMESTAMP(timezone=True), nullable=False, comment="会议开始时间（带时区）")
    end_time = Column(TIMESTAMP(timezone=True), nullable=True, comment="会议结束时间（实时会议可为NULL）")
    user_id = Column(String(50), nullable=False, comment="主持人用户ID，关联sys_users.username")
    status = Column(SmallInteger, nullable=False, server_default=sql_text("1"), comment="会议状态：1-进行中 2-已结束 3-已取消")
    created_at = Column(TIMESTAMP(timezone=True), server_default=sql_text("CURRENT_TIMESTAMP"), comment="创建时间")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=sql_text("CURRENT_TIMESTAMP"), comment="更新时间")


class MeetingRecord(Base):
    """会议记录明细表"""
    __tablename__ = "meeting_record"

    id = Column(BigInteger, primary_key=True, comment="记录唯一ID")
    meeting_id = Column(BigInteger, ForeignKey("meeting_main.id"), nullable=False, comment="关联会议主表ID")
    user_id = Column(String(50), nullable=False, comment="发言用户ID，关联sys_users.username")
    speaker_name = Column(String(64), nullable=False, comment="发言者姓名")
    content = Column(Text, nullable=False, comment="发言内容（语音转文字结果）")
    record_time = Column(TIMESTAMP(timezone=True), nullable=False, comment="发言时间")
    audio_file_key = Column(String(255), nullable=True, comment="音频文件唯一标识（如OSS的object key）")
    audio_file_url = Column(String(512), nullable=True, comment="音频文件访问URL（带有效期的签名URL）")
    audio_duration = Column(Integer, server_default=sql_text("0"), comment="音频时长（秒）")
    audio_format = Column(String(16), nullable=True, comment="音频格式（如mp3/wav/aac）")
    audio_size = Column(BigInteger, server_default=sql_text("0"), comment="音频文件大小（字节）")
    parent_id = Column(BigInteger, server_default=sql_text("0"), comment="回复/引用的父记录ID")
    is_deleted = Column(SmallInteger, server_default=sql_text("0"), comment="软删除：0-未删 1-已删")
    created_at = Column(TIMESTAMP(timezone=True), server_default=sql_text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=sql_text("CURRENT_TIMESTAMP"))



class MeetingManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        pass

    async def create_meeting(self, user_id: str, title: str, start_time: datetime, db=None) -> dict:
        """
        创建新会议
        
        Args:
            user_id: 主持人用户ID (username)
            title: 会议标题
            start_time: 会议开始时间
            db: 数据库会话
            
        Returns:
            创建成功的会议信息
        """
        try:
            # 1. 生成业务会议编号 (这里使用您在txt中设计的方案1：日期+部门+序号)
            # 注意：这部分代码为了演示，直接写入。在生产环境中，部门代码和数据库连接应通过配置管理
            date_str = datetime.now().strftime("%Y%m%d")
            # 假设部门代码为'GNR' (General)
            dept_code = "GNR"
            # 查询当天该部门的会议数量来生成序号
            count_query = select(func.count()).select_from(MeetingMain).where(
                MeetingMain.meeting_no.like(f"{date_str}-{dept_code}-%")
            )
            count = await db.scalar(count_query)
            seq = f"{count + 1:03d}"
            meeting_no = f"{date_str}-{dept_code}-{seq}"

            # 2. 创建会议主记录
            new_meeting = MeetingMain(
                meeting_title=title,
                meeting_no=meeting_no,
                start_time=start_time,
                user_id=user_id,
                status=1  # 1-进行中
            )
            db.add(new_meeting)
            await db.commit()
            await db.refresh(new_meeting)

            logger.info(f"✅ [Meeting] 新会议创建成功: {new_meeting.id} ({new_meeting.meeting_no})")
            
            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "id": new_meeting.id,
                    "meeting_title": new_meeting.meeting_title,
                    "meeting_no": new_meeting.meeting_no,
                    "start_time": new_meeting.start_time.isoformat(),
                    "user_id": new_meeting.user_id,
                    "status": new_meeting.status
                }
            }
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ [Meeting] 创建新会议失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"创建失败: {str(e)}"}

    async def get_meeting_list(self, user_id: str, db=None, page: int = 1, size: int = 20) -> dict:
        """
        获取当前用户主持的会议列表
        
        Args:
            user_id: 当前用户ID
            db: 数据库会话
            page: 页码
            size: 每页数量
            
        Returns:
            会议列表
        """
        try:
            # 作为参与者的会议也应该被查询到，这里暂时只实现查询自己主持的会议
            # 计算总数
            count_query = select(func.count()).select_from(MeetingMain).where(
                and_(
                    MeetingMain.user_id == user_id,
                    MeetingMain.status != 3  # 排除已删除/取消的
                )
            )
            total = await db.scalar(count_query)

            # 分页查询
            offset = (page - 1) * size
            query = (
                select(MeetingMain)
                .where(
                    and_(
                        MeetingMain.user_id == user_id,
                        MeetingMain.status != 3  # 排除已删除/取消的
                    )
                )
                .order_by(desc(MeetingMain.start_time))
                .offset(offset)
                .limit(size)
            )
            
            result = await db.execute(query)
            meetings = result.scalars().all()

            items = []
            for meeting in meetings:
                items.append({
                    "id": meeting.id,
                    "meeting_title": meeting.meeting_title,
                    "meeting_no": meeting.meeting_no,
                    "start_time": meeting.start_time.isoformat(),
                    "status": meeting.status
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

    async def get_meeting_detail(self, meeting_id: int, user_id: str, db=None) -> dict:
        """
        获取会议详情，包括所有发言记录
        
        Args:
            meeting_id: 会议ID
            user_id: 当前用户ID (用于权限校验)
            db: 数据库会话
            
        Returns:
            会议详情
        """
        try:
            # 1. 查询会议主信息
            query_main = select(MeetingMain).where(
                and_(
                    MeetingMain.id == meeting_id,
                    MeetingMain.user_id == user_id  # 简单权限校验：只有主持人能看
                )
            )
            result_main = await db.execute(query_main)
            meeting = result_main.scalar_one_or_none()

            if not meeting:
                return {"code": 404, "msg": "会议不存在或您没有权限查看"}

            # 2. 查询所有关联的发言记录
            query_records = (
                select(MeetingRecord)
                .where(MeetingRecord.meeting_id == meeting_id)
                .order_by(MeetingRecord.record_time)
            )
            result_records = await db.execute(query_records)
            records = result_records.scalars().all()

            # 3. 组装发言记录
            record_items = []
            for record in records:
                record_items.append({
                    "id": record.id,
                    "speaker_name": record.speaker_name,
                    "content": record.content,
                    "record_time": record.record_time.isoformat(),
                    "audio_duration": record.audio_duration
                })

            # 4. 组装最终返回结果
            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "id": meeting.id,
                    "meeting_title": meeting.meeting_title,
                    "meeting_no": meeting.meeting_no,
                    "start_time": meeting.start_time.isoformat(),
                    "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
                    "user_id": meeting.user_id,
                    "status": meeting.status,
                    "records": record_items
                }
            }
        except Exception as e:
            logger.error(f"❌ [Meeting] 获取会议详情失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"获取失败: {str(e)}"}

    async def delete_meeting(self, meeting_id: int, user_id: str, db=None) -> dict:
        """
        删除会议（逻辑删除）
        
        Args:
            meeting_id: 会议ID
            user_id: 当前用户ID
            db: 数据库会话
            
        Returns:
            删除结果
        """
        try:
            # 权限校验：只有主持人可以删除
            query = select(MeetingMain).where(
                and_(
                    MeetingMain.id == meeting_id,
                    MeetingMain.user_id == user_id
                )
            )
            
            result = await db.execute(query)
            meeting = result.scalar_one_or_none()

            if not meeting:
                return {"code": 404, "msg": "会议不存在或您没有权限删除"}

            # 逻辑删除：更新主表状态为“已取消” (status=3)
            meeting.status = 3
            meeting.end_time = datetime.now() # 记录删除/取消时间
            
            # 逻辑删除所有关联的发言记录
            update_stmt = (
                update(MeetingRecord)
                .where(MeetingRecord.meeting_id == meeting_id)
                .values(is_deleted=1)
            )
            await db.execute(update_stmt)
            
            await db.commit()

            logger.info(f"✅ [Meeting] 会议记录逻辑删除成功: {meeting_id}")
            
            return {"code": 200, "msg": "删除成功"}
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ [Meeting] 删除会议记录失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"删除失败: {str(e)}"}


    async def add_meeting_record(self, meeting_id: int, user_id: str, speaker_name: str, content: str, record_time: datetime, db=None, **kwargs) -> dict:
        """
        向会议中添加一条发言记录

        Args:
            meeting_id: 会议ID
            speaker_user_id: 发言用户ID
            speaker_name: 发言者姓名
            content: 发言内容
            record_time: 发言时间
            db: 数据库会话
            **kwargs: 其他音频相关字段

        Returns:
            创建成功的发言记录
        """
        try:
            # 可以在此添加权限校验，例如检查用户是否是会议的参与者

            new_record = MeetingRecord(
                meeting_id=meeting_id,
                user_id=user_id,
                speaker_name=speaker_name,
                content=content,
                record_time=record_time,
                audio_file_key=kwargs.get("audio_file_key"),
                audio_file_url=kwargs.get("audio_file_url"),
                audio_duration=kwargs.get("audio_duration", 0),
                audio_format=kwargs.get("audio_format"),
                audio_size=kwargs.get("audio_size", 0),
                parent_id=kwargs.get("parent_id", 0)
            )
            db.add(new_record)
            await db.commit()
            await db.refresh(new_record)

            logger.info(f"✅ [Meeting] 发言记录添加成功: {new_record.id} (会议ID: {meeting_id})")

            return {"code": 200, "msg": "success", "data": {"record_id": new_record.id}}

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ [Meeting] 添加发言记录失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"添加失败: {str(e)}"}


    async def update_meeting_record(self, record_id: int, new_content: str, user_id: str, db=None) -> dict:
        """
        更新一条发言记录的内容

        Args:
            record_id: 发言记录ID
            new_content: 新的发言内容
            user_id: 当前用户ID (用于权限校验)
            db: 数据库会话

        Returns:
            更新结果
        """
        try:
            # 1. 查找记录是否存在
            query = select(MeetingRecord).where(MeetingRecord.id == record_id)
            result = await db.execute(query)
            record = result.scalar_one_or_none()

            if not record:
                return {"code": 404, "msg": "发言记录不存在"}

            # 2. 权限校验 (简单实现：检查该记录所属的会议是否由当前用户主持)
            # 在复杂系统中，可能需要检查用户是否为会议参与者等更精细的权限
            meeting_query = select(MeetingMain).where(
                and_(
                    MeetingMain.id == record.meeting_id,
                    MeetingMain.user_id == user_id
                )
            )
            meeting = await db.scalar(meeting_query)

            if not meeting:
                return {"code": 403, "msg": "您没有权限修改此记录"}

            # 3. 更新内容
            record.content = new_content
            await db.commit()

            logger.info(f"✅ [Meeting] 发言记录更新成功: {record_id}")
            return {"code": 200, "msg": "更新成功"}

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ [Meeting] 更新发言记录失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"更新失败: {str(e)}"}


    async def update_meeting(self, meeting_id: int, user_id: str, db=None, **kwargs) -> dict:
        """
        更新会议的属性，如标题等

        Args:
            meeting_id: 会议ID
            user_id: 当前用户ID (用于权限校验)
            db: 数据库会话
            **kwargs: 要更新的字段，如 title="新标题"

        Returns:
            更新结果
        """
        try:
            # 权限校验：只有主持人可以修改
            query = select(MeetingMain).where(
                and_(
                    MeetingMain.id == meeting_id,
                    MeetingMain.user_id == user_id
                )
            )
            result = await db.execute(query)
            meeting = result.scalar_one_or_none()

            if not meeting:
                return {"code": 404, "msg": "会议不存在或您没有权限修改"}

            # 动态更新字段
            updated_fields = 0
            if "title" in kwargs and kwargs["title"]:
                meeting.meeting_title = kwargs["title"]
                updated_fields += 1
            
            # 未来可在这里扩展其他字段的更新，例如：
            # if "status" in kwargs:
            #     meeting.status = kwargs["status"]
            #     updated_fields += 1

            if updated_fields > 0:
                await db.commit()
                logger.info(f"✅ [Meeting] 会议属性更新成功: {meeting_id}")
                return {"code": 200, "msg": "更新成功"}
            else:
                return {"code": 400, "msg": "没有提供任何有效的更新字段"}

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ [Meeting] 更新会议属性失败: {e}", exc_info=True)
            return {"code": 500, "msg": f"更新失败: {str(e)}"}


# 全局单例
meeting_service = MeetingManager()
