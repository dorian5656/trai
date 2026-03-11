#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/ai/chat_func.py
# 作者：whf
# 日期：2026-01-27
# 描述：AI 模块业务逻辑 (DeepSeek API)

import httpx
import os
import uuid
import json
from sqlalchemy import text
from backend.app.utils.pg_utils import PGUtils
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.modelscope_utils import ModelScopeUtils

# =============================================================================
# Schema 定义 (AI)
# =============================================================================

class Message(BaseModel):
    """
    对话消息模型
    """
    role: str = Field(..., description="角色 (user/assistant/system)", examples=["user"])
    content: Union[str, List[Dict[str, Any]]] = Field(..., description="消息内容 (文本或多模态列表)", examples=["Hello, how are you?"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "role": "user",
                "content": "Hello, how are you?"
            }
        }
    }

class ChatRequest(BaseModel):
    """
    AI 对话请求模型
    """
    messages: List[Message] = Field(..., description="历史消息列表")
    model: str = Field("deepseek-chat", description="模型名称 (deepseek-chat/Qwen3-VL-4B-Instruct)", examples=["deepseek-chat"])
    temperature: float = Field(0.7, description="温度系数 (0-2)", examples=[0.7])
    max_tokens: int = Field(512, description="最大 Token 数", examples=[512])
    session_id: Optional[str] = Field(None, description="会话ID (若不传则自动生成)", examples=["uuid-v4-string"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Tell me a joke."}
                ],
                "model": "deepseek-chat",
                "temperature": 0.7,
                "max_tokens": 512
            }
        }
    }

class ChatResponse(BaseModel):
    """
    AI 对话响应模型
    """
    reply: str = Field(..., description="AI 回复内容")
    model: str = Field(..., description="使用的模型")
    usage: Dict[str, Any] = Field({}, description="Token 使用统计")
    session_id: Optional[str] = Field(None, description="会话ID")

class AIManager:
    """
    AI 模块业务逻辑管理器
    """
    
    @staticmethod
    async def save_message(session_id: str, user_id: str, role: str, content: Union[str, List[Dict[str, Any]]], model: str = None):
        """保存对话消息到数据库"""
        try:
            # 如果 content 是列表 (多模态)，序列化为 JSON 字符串
            if isinstance(content, list):
                content_str = json.dumps(content, ensure_ascii=False)
            else:
                content_str = str(content)

            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                await conn.execute(
                    text("""
                        INSERT INTO chat_messages (session_id, user_id, role, content, model)
                        VALUES (:session_id, :user_id, :role, :content, :model)
                    """),
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "role": role,
                        "content": content_str,
                        "model": model
                    }
                )
        except Exception as e:
            logger.error(f"❌ 保存对话消息失败: {e}")

    @staticmethod
    async def get_session_messages(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取指定会话的历史消息列表 (按时间正序)
        """
        try:
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # 查询最近的 N 条消息，然后按时间正序排列
                # 注意: 我们需要先按时间倒序取 limit 条，再反转回来
                result = await conn.execute(
                    text("""
                        SELECT role, content
                        FROM (
                            SELECT role, content, created_at
                            FROM chat_messages
                            WHERE session_id = :session_id AND is_deleted = FALSE
                            ORDER BY created_at DESC
                            LIMIT :limit
                        ) sub
                        ORDER BY created_at ASC
                    """),
                    {"session_id": session_id, "limit": limit}
                )
                
                messages = []
                for row in result:
                    content = row.content
                    # 尝试解析 JSON (兼容多模态存储)
                    try:
                        if content and content.strip().startswith("[") and content.strip().endswith("]"):
                            parsed = json.loads(content)
                            if isinstance(parsed, list):
                                # 转换为 OpenAI/DeepSeek 兼容的格式
                                # 如果是纯文本列表，转回字符串；如果是多模态结构，保持原样
                                # 这里简化处理，直接使用解析后的对象，Pydantic 会处理序列化
                                content = parsed
                    except:
                        pass
                        
                    messages.append({"role": row.role, "content": content})
                
                return messages
        except Exception as e:
            logger.error(f"获取会话历史失败: {e}")
            return []

    @staticmethod
    async def chat_completion(request: ChatRequest, user_id: str = "anonymous") -> ChatResponse:
        """
        统一对话入口 (支持 DeepSeek API 和 本地 ModelScope 模型)
        """
        session_id = request.session_id or str(uuid.uuid4())
        
        # 记录用户消息 (只记录最后一条 user 消息)
        # 注意: 如果 request.messages 包含历史消息，我们只存最后一条新的
        if request.messages and request.messages[-1].role == 'user':
            await AIManager.save_message(session_id, user_id, 'user', request.messages[-1].content, request.model)

        # === 上下文构建逻辑 ===
        # 1. 提取 System Prompt (如果有)
        system_message = None
        if request.messages and request.messages[0].role == 'system':
            system_message = request.messages[0].model_dump()
            
        # 2. 获取数据库中的历史消息 (包含刚才保存的最新一条 user 消息)
        # 默认获取最近 20 条，避免 Token 超限
        history_messages = await AIManager.get_session_messages(session_id, limit=20)
        
        # 3. 组装最终发送给模型的消息列表
        # 优先级: System Prompt -> Database History
        final_messages = []
        if system_message:
            final_messages.append(system_message)
        
        # 如果数据库有历史，使用数据库历史 (它已经包含了最新的 user 消息)
        if history_messages:
            final_messages.extend(history_messages)
        else:
            # 如果数据库没查到 (异常情况)，回退到使用请求中的 messages
            final_messages.extend([msg.model_dump() for msg in request.messages if msg.role != 'system'])

        reply = ""
        usage = {}

        # 1. 检查是否为本地 ModelScope 模型
        if ModelScopeUtils.check_model_exists(request.model):
            try:
                logger.info(f"路由到本地 ModelScope 模型: {request.model}")
                
                reply = await ModelScopeUtils.chat_completion(
                    messages=final_messages,
                    model_name=request.model,
                    max_new_tokens=request.max_tokens or 512
                )
                usage = {"local_inference": True}
                
            except Exception as e:
                logger.error(f"本地模型推理失败: {e}")
                raise ValueError(f"Local model inference failed: {e}")

        # 2. 否则走 DeepSeek API (默认)
        else:
            if not settings.DEEPSEEK_API_KEY:
                raise ValueError("DeepSeek API Key not configured")
                
            url = f"{settings.DEEPSEEK_API_BASE}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"
            }
            
            payload = {
                "model": request.model,
                "messages": final_messages,
                "temperature": request.temperature,
                "stream": False
            }
            
            if request.max_tokens:
                payload["max_tokens"] = request.max_tokens
                
            try:
                # 使用 trust_env=False 忽略系统代理设置，防止 500 错误
                async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                    logger.info(f"发送 DeepSeek 请求: model={request.model}, msg_count={len(final_messages)}")
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    reply = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    logger.info(f"DeepSeek 响应成功: usage={usage}")
                    
            except Exception as e:
                logger.error(f"DeepSeek API 请求失败: {e}")
                raise ValueError(f"DeepSeek API failed: {e}")

        # 记录 AI 回复
        await AIManager.save_message(session_id, user_id, 'assistant', reply, request.model)

        return ChatResponse(
            reply=reply,
            model=request.model,
            usage=usage,
            session_id=session_id
        )

    @staticmethod
    async def rename_chat_session(session_id: str, user_id: str, new_name: str) -> None:
        """
        重命名会话
        """
        try:
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # 1. 确保 chat_sessions 表存在 (Lazy creation)
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        session_id VARCHAR(50) PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        name VARCHAR(255),
                        created_at TIMESTAMP(0) DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                        updated_at TIMESTAMP(0) DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
                    );
                    CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
                """))
                
                # 2. 插入或更新
                # 先检查是否存在
                result = await conn.execute(
                    text("SELECT 1 FROM chat_sessions WHERE session_id = :session_id AND user_id = :user_id"),
                    {"session_id": session_id, "user_id": user_id}
                )
                
                if result.scalar():
                    # 更新
                    await conn.execute(
                        text("UPDATE chat_sessions SET name = :name, updated_at = (NOW() AT TIME ZONE 'Asia/Shanghai') WHERE session_id = :session_id AND user_id = :user_id"),
                        {"name": new_name, "session_id": session_id, "user_id": user_id}
                    )
                else:
                    # 插入 (可能是旧会话，第一次命名)
                    # 确保该 session_id 在 messages 表里确实属于该用户
                    msg_check = await conn.execute(
                        text("SELECT 1 FROM chat_messages WHERE session_id = :session_id AND user_id = :user_id LIMIT 1"),
                        {"session_id": session_id, "user_id": user_id}
                    )
                    if msg_check.scalar():
                        await conn.execute(
                            text("INSERT INTO chat_sessions (session_id, user_id, name) VALUES (:session_id, :user_id, :name)"),
                            {"session_id": session_id, "user_id": user_id, "name": new_name}
                        )
                    else:
                        raise ValueError("Session not found or permission denied")
                        
                logger.info(f"会话重命名成功: {session_id} -> {new_name}")
                
        except Exception as e:
            logger.error(f"重命名会话失败: {e}")
            raise e

    @staticmethod
    async def get_chat_sessions(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近的会话列表 (聚合)
        """
        try:
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # 确保 chat_sessions 表存在
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        session_id VARCHAR(50) PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        name VARCHAR(255),
                        created_at TIMESTAMP(0) DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                        updated_at TIMESTAMP(0) DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
                    );
                """))
                
                # 关联查询: messages + sessions
                # 获取每个 session 的最后一条消息和更新时间
                # 同时左连接 chat_sessions 获取自定义名称
                # 使用窗口函数或 DISTINCT ON (PostgreSQL特有)
                result = await conn.execute(
                    text("""
                        WITH SessionStats AS (
                            SELECT 
                                session_id,
                                MAX(created_at) as last_update
                            FROM chat_messages
                            WHERE user_id = :user_id AND is_deleted = FALSE
                            GROUP BY session_id
                        ),
                        LastMsg AS (
                            SELECT DISTINCT ON (session_id)
                                session_id,
                                content,
                                model
                            FROM chat_messages
                            WHERE user_id = :user_id AND is_deleted = FALSE
                            ORDER BY session_id, created_at DESC
                        )
                        SELECT 
                            ss.session_id,
                            ss.last_update,
                            lm.content as last_message,
                            lm.model,
                            cs.name as session_name
                        FROM SessionStats ss
                        JOIN LastMsg lm ON ss.session_id = lm.session_id
                        LEFT JOIN chat_sessions cs ON ss.session_id = cs.session_id
                        ORDER BY ss.last_update DESC
                        LIMIT :limit
                    """),
                    {"user_id": user_id, "limit": limit}
                )
                
                sessions = []
                for row in result:
                    # 尝试解析 last_message (可能是 JSON 字符串)
                    content_preview = row.last_message
                    if content_preview and content_preview.startswith("[") and content_preview.endswith("]"):
                         try:
                             content_list = json.loads(content_preview)
                             # 如果是多模态列表，提取第一个文本内容
                             for item in content_list:
                                 if item.get("type") == "text":
                                     content_preview = item.get("text")
                                     break
                                 elif item.get("text"): # 兼容旧格式
                                     content_preview = item.get("text")
                                     break
                         except:
                             pass
                    
                    # 截断预览
                    if len(content_preview) > 50:
                        content_preview = content_preview[:50] + "..."

                    sessions.append({
                        "session_id": row.session_id,
                        "name": row.session_name, # 新增 name 字段
                        "last_message": content_preview,
                        "model": row.model,
                        "updated_at": row.last_update.strftime("%Y-%m-%d %H:%M:%S")
                    })
                return sessions
        except Exception as e:
            logger.error(f"获取会话列表失败: {e}")
            return []

    @staticmethod
    async def delete_chat_session(session_id: str, user_id: str) -> None:
        """
        删除会话 (软删除)
        """
        try:
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # 检查是否存在
                result = await conn.execute(
                    text("SELECT 1 FROM chat_messages WHERE session_id = :session_id AND user_id = :user_id LIMIT 1"),
                    {"session_id": session_id, "user_id": user_id}
                )
                if not result.scalar():
                    raise ValueError("Session not found or permission denied")

                # 软删除
                await conn.execute(
                    text("UPDATE chat_messages SET is_deleted = TRUE WHERE session_id = :session_id AND user_id = :user_id"),
                    {"session_id": session_id, "user_id": user_id}
                )
                logger.info(f"会话已删除: {session_id} (User: {user_id})")
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            raise e

    @staticmethod
    async def delete_chat_message(message_id: str, user_id: str) -> None:
        """
        删除单条消息 (软删除)
        """
        try:
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # 检查
                result = await conn.execute(
                    text("SELECT id FROM chat_messages WHERE id = :id AND user_id = :user_id AND is_deleted = FALSE"),
                    {"id": message_id, "user_id": user_id}
                )
                if not result.scalar():
                    raise ValueError("Message not found or permission denied")

                # 软删除
                await conn.execute(
                    text("UPDATE chat_messages SET is_deleted = TRUE WHERE id = :id"),
                    {"id": message_id}
                )
                logger.info(f"消息已删除: {message_id}")
        except Exception as e:
            logger.error(f"删除消息失败: {e}")
            raise e

