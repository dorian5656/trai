#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/response.py
# 描述：统一响应格式封装

from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ResponseCode:
    """
    统一状态码定义
    参考: HTTP Status Codes
    """
    # -------------------------------------------------------------------------
    # 2xx Success (成功)
    # -------------------------------------------------------------------------
    OK = 200                    # 请求成功 (GET, POST, PUT, DELETE)
    CREATED = 201               # 资源创建成功 (POST)
    ACCEPTED = 202              # 请求已接受，处理中 (Async)
    NO_CONTENT = 204            # 请求成功，无内容返回 (DELETE)
    PARTIAL_CONTENT = 206       # 部分内容 (Range Requests)
    
    # -------------------------------------------------------------------------
    # 3xx Redirection (重定向)
    # -------------------------------------------------------------------------
    MOVED_PERMANENTLY = 301     # 永久重定向
    FOUND = 302                 # 临时重定向
    SEE_OTHER = 303             # 参见其他
    NOT_MODIFIED = 304          # 资源未修改 (Cache)
    TEMPORARY_REDIRECT = 307    # 临时重定向 (保留方法)
    PERMANENT_REDIRECT = 308    # 永久重定向 (保留方法)

    # -------------------------------------------------------------------------
    # 4xx Client Error (客户端错误)
    # -------------------------------------------------------------------------
    BAD_REQUEST = 400           # 请求错误 (参数/语法)
    UNAUTHORIZED = 401          # 未认证 (Token缺失/无效)
    FORBIDDEN = 403             # 禁止访问 (权限不足)
    NOT_FOUND = 404             # 资源不存在
    METHOD_NOT_ALLOWED = 405    # 方法不允许
    NOT_ACCEPTABLE = 406        # 无法响应请求的格式
    TIMEOUT = 408               # 请求超时
    CONFLICT = 409              # 资源冲突 (如重复创建)
    GONE = 410                  # 资源已永久删除
    PRECONDITION_FAILED = 412   # 前置条件失败
    PAYLOAD_TOO_LARGE = 413     # 请求体过大
    URI_TOO_LONG = 414          # URI过长
    UNSUPPORTED_MEDIA_TYPE = 415 # 不支持的媒体类型
    RANGE_NOT_SATISFIABLE = 416 # 范围请求无法满足
    TEAPOT = 418                # 我是茶壶 (彩蛋)
    VALIDATION_ERROR = 422      # 参数校验失败 (语义错误)
    LOCKED = 423                # 资源被锁定
    TOO_MANY_REQUESTS = 429     # 请求过多 (限流)
    
    # -------------------------------------------------------------------------
    # 5xx Server Error (服务端错误)
    # -------------------------------------------------------------------------
    INTERNAL_SERVER_ERROR = 500 # 服务器内部错误
    NOT_IMPLEMENTED = 501       # 功能未实现
    BAD_GATEWAY = 502           # 网关错误
    SERVICE_UNAVAILABLE = 503   # 服务不可用 (维护/过载)
    GATEWAY_TIMEOUT = 504       # 网关超时
    HTTP_VERSION_NOT_SUPPORTED = 505 # HTTP版本不支持
    INSUFFICIENT_STORAGE = 507  # 存储空间不足

class ResponseModel(BaseModel):
    """
    统一响应模型
    """
    code: int = Field(default=ResponseCode.OK, description="状态码")
    msg: str = Field(default="OK", description="响应信息")
    data: Optional[Any] = Field(default=None, description="响应数据")
    ts: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'), description="时间戳")

class ResponseHelper:
    """
    响应工具类
    提供统一的成功和失败响应生成方法
    """
    @staticmethod
    def success(data: Any = None, msg: str = "OK", code: int = ResponseCode.OK) -> ResponseModel:
        """
        成功响应
        :param data: 响应数据
        :param msg: 响应信息
        :param code: 状态码 (默认 200)
        :return: ResponseModel
        """
        return ResponseModel(
            code=code, 
            msg=msg, 
            data=data,
            ts=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

    @staticmethod
    def error(code: int = ResponseCode.BAD_REQUEST, msg: str = "Error", data: Any = None) -> ResponseModel:
        """
        错误响应
        :param code: 错误码 (默认 400)
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
