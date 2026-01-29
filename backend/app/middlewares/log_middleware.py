#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/middlewares/log_middleware.py
# 作者：whf
# 日期：2026-01-26
# 描述：请求日志中间件，用于记录 API 请求详情到数据库

import time
import uuid
import json
from datetime import datetime, timedelta, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.concurrency import iterate_in_threadpool
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.logger import logger
import asyncio

class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # 1. 获取请求体
        request_body = ""
        try:
            content_type = request.headers.get("content-type", "")
            # 仅记录 JSON 请求体，避免大文件上传
            if "application/json" in content_type:
                # 读取 Body 会消耗 Stream，必须重新设置回去
                body_bytes = await request.body()
                request._body = body_bytes  # Hack: 将读取的 bytes 放回，供后续使用
                try:
                    request_body = body_bytes.decode("utf-8")
                except:
                    request_body = "<binary/invalid utf-8>"
        except Exception as e:
            logger.warning(f"读取 Request Body 失败: {e}")

        # 2. 执行请求
        try:
            response = await call_next(request)
            
            # 3. 处理流式响应 (StreamingResponse)
            # 注意: BaseHTTPMiddleware 会将响应包装为 _StreamingResponse
            if isinstance(response, StreamingResponse) or response.__class__.__name__ in ['StreamingResponse', '_StreamingResponse']:
                async def stream_wrapper(original_iterator):
                    content_buffer = b""
                    try:
                        async for chunk in original_iterator:
                            if isinstance(chunk, bytes):
                                content_buffer += chunk
                            elif isinstance(chunk, str):
                                content_buffer += chunk.encode("utf-8")
                            yield chunk
                    except Exception as e:
                        logger.error(f"流式响应遍历异常: {e}")
                        raise e
                    finally:
                        # 流结束后记录日志
                        process_time = (time.perf_counter() - start_time) * 1000
                        response_body_str = ""
                        try:
                            raw_body = content_buffer.decode("utf-8")
                            
                            # 解析 SSE 格式并合并内容
                            # 格式: data: <content>\n\n
                            merged_content = ""
                            for line in raw_body.split('\n\n'):
                                if line.startswith("data: "):
                                    content = line[6:]
                                    if content != "[DONE]":
                                        merged_content += content
                            
                            # 构造类似于非流式响应的 JSON 格式，以便前端或日志统一展示
                            log_payload = {
                                "reply": merged_content,
                                "stream_merged": True
                            }
                            response_body_str = json.dumps(log_payload, ensure_ascii=False)
                            
                        except:
                            response_body_str = "<binary/invalid utf-8>"
                        
                        # logger.info(f"流式响应结束，耗时: {process_time:.2f}ms，内容长度: {len(response_body_str)}")
                            
                        asyncio.create_task(self._log_request(
                            request=request,
                            request_id=request_id,
                            request_body=request_body,
                            response_body=response_body_str,
                            status_code=response.status_code,
                            duration_ms=process_time,
                            error_detail=None
                        ))

                # 替换 body_iterator
                response.body_iterator = stream_wrapper(response.body_iterator)
                return response

            # 4. 处理普通响应
            response_body = ""
            try:
                # 检查 content-type (application/json)
                resp_content_type = response.headers.get("content-type", "")
                
                if "application/json" in resp_content_type:
                    # 读取响应内容
                    resp_body_bytes = b""
                    async for chunk in response.body_iterator:
                        resp_body_bytes += chunk
                    
                    try:
                        response_body = resp_body_bytes.decode("utf-8")
                    except:
                        response_body = "<binary/invalid utf-8>"

                    # 重建响应对象 (因为 iterator 已被消耗)
                    response = Response(
                        content=resp_body_bytes,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type
                    )
            except Exception as e:
                logger.warning(f"读取 Response Body 失败: {e}")
            
            process_time = (time.perf_counter() - start_time) * 1000
            
            # 5. 异步写入日志 (普通响应)
            asyncio.create_task(self._log_request(
                request=request,
                request_id=request_id,
                request_body=request_body,
                response_body=response_body,
                status_code=response.status_code,
                duration_ms=process_time,
                error_detail=None
            ))
            
            return response
            
        except Exception as e:
            process_time = (time.perf_counter() - start_time) * 1000
            # 记录异常日志
            asyncio.create_task(self._log_request(
                request=request,
                request_id=request_id,
                request_body=request_body,
                response_body="",
                status_code=500,
                duration_ms=process_time,
                error_detail=str(e)
            ))
            raise e

    async def _log_request(
        self,
        request: Request,
        request_id: str,
        request_body: str,
        response_body: str,
        status_code: int,
        duration_ms: float,
        error_detail: str = None
    ):
        """
        异步写入日志到数据库
        """
        try:
            # --- 错误详情提取逻辑优化 ---
            # 1. 尝试解析 Response Body (如果是 JSON)
            body_json = None
            if response_body:
                try:
                    body_json = json.loads(response_body)
                except:
                    pass

            # 2. 判断是否为"失败"请求
            # 如果 error_detail 已有值 (如代码抛出异常捕获)，则直接认定为失败
            is_error = error_detail is not None
            
            # 检查 HTTP 状态码
            if status_code != 200:
                is_error = True
            
            # 检查业务状态码 (仅当响应是 JSON 且包含 code 字段)
            # 假设: code=200 表示成功，其他表示失败
            if body_json and isinstance(body_json, dict):
                if "code" in body_json and body_json["code"] != 200:
                    is_error = True

            # 3. 如果判定为失败且当前没有 error_detail，则从响应中提取
            if is_error and not error_detail:
                if body_json and isinstance(body_json, dict):
                    # 优先提取 msg 字段
                    if "msg" in body_json:
                        error_detail = str(body_json["msg"])
                    # 其次提取 detail 字段 (FastAPI 默认错误格式)
                    elif "detail" in body_json:
                        error_detail = str(body_json["detail"])
                    # 否则使用整个 JSON 字符串
                    else:
                        error_detail = response_body
                else:
                    # 非 JSON 响应，直接使用响应体 (截断)
                    error_detail = response_body[:1000] if response_body else "Unknown Error"

            sql = """
            INSERT INTO request_logs (
                request_id, 
                method, 
                path, 
                client_ip, 
                request_body, 
                response_body, 
                status_code, 
                duration_ms,
                error_detail,
                created_at
            ) VALUES (:request_id, :method, :path, :client_ip, :request_body, :response_body, :status_code, :duration_ms, :error_detail, :created_at)
            """
            
            client_host = request.client.host if request.client else "unknown"
            
            # 使用系统当前时间 (北京时间)
            created_at = datetime.now()
            
            params = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_host,
                "request_body": request_body[:2000],
                "response_body": response_body[:2000],
                "status_code": status_code,
                "duration_ms": duration_ms,
                "error_detail": error_detail,
                "created_at": created_at
            }
            
            # 使用 PGUtils 插入日志
            await PGUtils.execute_update(sql, params)
            
        except Exception as e:
            # 日志写入失败不能影响主流程，仅打印本地日志
            logger.error(f"写入请求日志失败: {e}")
