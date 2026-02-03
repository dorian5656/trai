#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/security.py
# 作者：whf
# 日期：2026-01-27
# 描述：安全工具类 (密码哈希/JWT)

from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
import bcrypt
from backend.app.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否匹配
    :param plain_password: 明文密码
    :param hashed_password: 哈希密码
    :return: 是否匹配
    """
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    
    # 限制密码长度，避免 bcrypt 报错 (password too long)
    if len(plain_password) > 71:
        plain_password = plain_password[:71]
        
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
        
    try:
        return bcrypt.checkpw(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """
    获取密码哈希值
    :param password: 明文密码
    :return: 哈希密码
    """
    if isinstance(password, str):
        password = password.encode('utf-8')
        
    if len(password) > 71:
        password = password[:71]
            
    # 生成 salt 并哈希
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password, salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    """
    创建 JWT 访问令牌
    :param data: 包含的数据 (sub 等)
    :param expires_delta: 过期时间差
    :return: JWT Token 字符串
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt