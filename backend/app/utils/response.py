#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/response.py
# 描述：统一响应格式封装

from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ResponseModel(BaseModel):
    """
    统一响应模型
    """
    code: int = Field(default=200, description="状态码")
    msg: str = Field(default="OK", description="响应信息")
    data: Optional[Any] = Field(default=None, description="响应数据")
    ts: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'), description="时间戳")

class ResponseHelper:
    """
    响应工具类
    提供统一的成功和失败响应生成方法
    """
    @staticmethod
    def success(data: Any = None, msg: str = "OK") -> ResponseModel:
        """
        成功响应
        :param data: 响应数据
        :param msg: 响应信息
        :return: ResponseModel
        """
        return ResponseModel(
            code=200, 
            msg=msg, 
            data=data,
            ts=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

    @staticmethod
    def error(code: int = 400, msg: str = "Error", data: Any = None) -> ResponseModel:
        """
        错误响应
        :param code: 错误码
        :param msg: 错误信息
        :param data: 错误详情
        :return: ResponseModel
        """
        return ResponseModel(
            code=code, 
            msg=msg, 
            data=data,
            ts=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
