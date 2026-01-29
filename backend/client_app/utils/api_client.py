#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/utils/api_client.py
# 作者: whf
# 日期: 2026-01-29
# 描述: API 客户端封装

import requests
from .config import Config

class ApiClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ApiClient, cls).__new__(cls)
            cls._instance.token = None
            cls._instance.base_url = Config.get_backend_url()
        return cls._instance
        
    def set_token(self, token):
        self.token = token
        
    def set_base_url(self, url):
        self.base_url = url.rstrip("/")
        
    def _get_headers(self):
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
        
    def post(self, endpoint, json_data=None, data=None, timeout=30):
        url = f"{self.base_url}{endpoint}"
        return requests.post(url, json=json_data, data=data, headers=self._get_headers(), timeout=timeout)
        
    def get(self, endpoint, params=None, timeout=30):
        url = f"{self.base_url}{endpoint}"
        return requests.get(url, params=params, headers=self._get_headers(), timeout=timeout)
        
    def stream_post(self, endpoint, json_data=None, timeout=120):
        url = f"{self.base_url}{endpoint}"
        return requests.post(url, json=json_data, headers=self._get_headers(), stream=True, timeout=timeout)
