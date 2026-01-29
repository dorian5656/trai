#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/ui/service_widget.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 服务管理界面

import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, 
    QTextEdit, QLabel, QGridLayout
)
from PyQt5.QtCore import QProcess, Qt
from logic.service_monitor import ServiceMonitorWorker
from utils.config import Config

class ServiceWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.backend_process = None
        self.frontend_process = None
        
        # 启动监控
        self.monitor = ServiceMonitorWorker()
        self.monitor.status_updated.connect(self.update_status_indicators)
        self.monitor.start()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 状态指示器
        status_group = QGroupBox("服务状态监控")
        status_layout = QGridLayout(status_group)
        
        self.backend_status_lbl = QLabel("⚫ 后端服务")
        self.frontend_status_lbl = QLabel("⚫ 前端服务")
        self.db_status_lbl = QLabel("⚫ 数据库 (PostgreSQL)")
        
        self.set_status_style(self.backend_status_lbl, False)
        self.set_status_style(self.frontend_status_lbl, False)
        self.set_status_style(self.db_status_lbl, False)
        
        status_layout.addWidget(self.backend_status_lbl, 0, 0)
        status_layout.addWidget(self.frontend_status_lbl, 0, 1)
        status_layout.addWidget(self.db_status_lbl, 0, 2)
        
        layout.addWidget(status_group)
        
        # 控制按钮组
        btn_group = QGroupBox("服务控制")
        btn_layout = QHBoxLayout(btn_group)
        
        self.start_backend_btn = QPushButton("启动后端")
        self.start_backend_btn.clicked.connect(self.start_backend)
        btn_layout.addWidget(self.start_backend_btn)
        
        self.stop_backend_btn = QPushButton("停止后端")
        self.stop_backend_btn.clicked.connect(self.stop_backend)
        self.stop_backend_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_backend_btn)
        
        self.start_frontend_btn = QPushButton("启动前端")
        self.start_frontend_btn.clicked.connect(self.start_frontend)
        btn_layout.addWidget(self.start_frontend_btn)

        self.stop_frontend_btn = QPushButton("停止前端")
        self.stop_frontend_btn.clicked.connect(self.stop_frontend)
        self.stop_frontend_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_frontend_btn)
        
        layout.addWidget(btn_group)
        
        # 日志输出
        layout.addWidget(QLabel("运行日志:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas; border-radius: 5px;")
        layout.addWidget(self.log_output)

    def set_status_style(self, label, active):
        if active:
            label.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 14px;")
            label.setText(label.text().replace("⚫", "🟢").replace("🔴", "🟢"))
        else:
            label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
            label.setText(label.text().replace("🟢", "🔴").replace("⚫", "🔴"))
            
    def update_status_indicators(self, status):
        self.set_status_style(self.backend_status_lbl, status["backend"])
        self.set_status_style(self.frontend_status_lbl, status["frontend"])
        self.set_status_style(self.db_status_lbl, status["database"])
        
        # 自动更新按钮状态
        if status["backend"] and not self.backend_process:
            self.start_backend_btn.setEnabled(False)
            self.stop_backend_btn.setEnabled(True)
        elif not status["backend"] and not self.backend_process:
            self.start_backend_btn.setEnabled(True)
            self.stop_backend_btn.setEnabled(False)
            
    def log(self, msg):
        self.log_output.append(msg)
        sb = self.log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    # 复用之前的启动逻辑 (简化版)
    def start_backend(self):
        if self.backend_process and self.backend_process.state() != QProcess.NotRunning:
            return

        self.log("正在启动后端...")
        self.backend_process = QProcess()
        self.backend_process.setProcessChannelMode(QProcess.MergedChannels)
        self.backend_process.readyReadStandardOutput.connect(self.handle_backend_output)
        
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
            root_dir = base_path.parent.parent.parent
        else:
            root_dir = Path(__file__).resolve().parent.parent.parent.parent
        
        script_path = root_dir / "backend" / "run.py"
        python_path = Config.get_python_path()
        
        self.backend_process.setWorkingDirectory(str(root_dir))
        
        # 简单处理，假设 python_path 是可执行的
        cmd = python_path
        args = [str(script_path), "--host", "0.0.0.0", "--port", "5689"] # 默认 5689
        
        if "&&" in cmd or "activate" in cmd:
             full_cmd = f"{cmd} {str(script_path)} --host 0.0.0.0 --port 5689"
             self.backend_process.start("cmd", ["/c", full_cmd])
        else:
             self.backend_process.start(cmd, args)
             
        self.start_backend_btn.setEnabled(False)
        self.stop_backend_btn.setEnabled(True)

    def stop_backend(self):
        if self.backend_process:
            self.backend_process.kill()
            self.log("后端服务已停止")
            self.backend_process = None
            self.start_backend_btn.setEnabled(True)
            self.stop_backend_btn.setEnabled(False)

    def handle_backend_output(self):
        data = self.backend_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
        self.log(f"[Backend] {data.strip()}")

    def start_frontend(self):
        if self.frontend_process and self.frontend_process.state() != QProcess.NotRunning:
            return

        self.log("正在启动前端...")
        self.frontend_process = QProcess()
        self.frontend_process.setProcessChannelMode(QProcess.MergedChannels)
        self.frontend_process.readyReadStandardOutput.connect(self.handle_frontend_output)
        
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
            root_dir = base_path.parent.parent.parent
        else:
            root_dir = Path(__file__).resolve().parent.parent.parent.parent

        frontend_dir = root_dir / "frontend"
        self.frontend_process.setWorkingDirectory(str(frontend_dir))
        self.frontend_process.start("cmd", ["/c", "npm", "run", "dev"])
        
        self.start_frontend_btn.setEnabled(False)
        self.stop_frontend_btn.setEnabled(True)

    def stop_frontend(self):
        if self.frontend_process:
            self.frontend_process.kill()
            self.log("前端服务已停止")
            self.frontend_process = None
            self.start_frontend_btn.setEnabled(True)
            self.stop_frontend_btn.setEnabled(False)

    def handle_frontend_output(self):
        data = self.frontend_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
        self.log(f"[Frontend] {data.strip()}")
        
    def closeEvent(self, event):
        self.monitor.stop()
        super().closeEvent(event)
