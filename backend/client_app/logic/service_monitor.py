#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/logic/service_monitor.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 服务状态监控逻辑

import socket
from PyQt5.QtCore import QObject, pyqtSignal, QThread
import time
from utils.config import Config

class ServiceMonitorWorker(QThread):
    status_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.running = True
        
    def run(self):
        while self.running:
            status = {
                "backend": self.check_port(Config.PORT_BACKEND_PROD) or self.check_port(Config.PORT_BACKEND_DEV),
                "frontend": self.check_port(Config.PORT_FRONTEND),
                "database": self.check_port(Config.PORT_POSTGRES)
            }
            self.status_updated.emit(status)
            time.sleep(5) # 每5秒检查一次
            
    def stop(self):
        self.running = False
        self.wait()
        
    def check_port(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
