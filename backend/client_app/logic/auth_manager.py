#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/logic/auth_manager.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 认证逻辑管理

from utils.api_client import ApiClient

class AuthManager:
    @staticmethod
    def login(username, password):
        client = ApiClient()
        try:
            resp = client.post("/api/v1/auth/login", data={
                "username": username,
                "password": password
            })
            
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token")
                client.set_token(token)
                return True, token, "登录成功"
            else:
                try:
                    detail = resp.json().get("detail", "登录失败")
                except:
                    detail = f"登录失败 (Code: {resp.status_code})"
                return False, None, detail
        except Exception as e:
            return False, None, f"连接错误: {str(e)}"
