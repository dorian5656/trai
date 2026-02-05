#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：image_gen_page.py
# 作者：liuhd
# 日期：2026-02-05
# 描述：AI 文生图功能页面

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QFrame, QMessageBox, QScrollArea, QFileDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QByteArray
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor
import requests
import json
import os
from datetime import datetime

class ImageGenWorker(QThread):
    finished_signal = pyqtSignal(bool, str, dict) # success, message, data

    def __init__(self, token, prompt):
        super().__init__()
        self.token = token
        self.prompt = prompt

    def run(self):
        url = "http://192.168.100.119:5777/api_trai/v1/ai/image/generations"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }
        data = {
            "model": "Z-Image-Turbo",
            "n": 1,
            "prompt": self.prompt,
            "size": "1024x1024"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120) # 生成图片可能较慢
            if response.status_code == 200:
                self.finished_signal.emit(True, "生成成功", response.json())
            else:
                try:
                    err_msg = response.json().get("detail", response.text)
                except:
                    err_msg = f"HTTP {response.status_code}"
                self.finished_signal.emit(False, f"生成失败: {err_msg}", {})
        except Exception as e:
            self.finished_signal.emit(False, f"请求异常: {str(e)}", {})

class ImageDownloadWorker(QThread):
    finished_signal = pyqtSignal(bool, bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, timeout=60)
            if response.status_code == 200:
                self.finished_signal.emit(True, response.content)
            else:
                self.finished_signal.emit(False, b"")
        except:
            self.finished_signal.emit(False, b"")

class ImageGenPage(QWidget):
    def __init__(self):
        super().__init__()
        self.auth_token = ""
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 标题
        title_label = QLabel("AI 文生图")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        main_layout.addWidget(title_label)

        # 顶部控制区 (输入框 + 按钮)
        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("请输入画面描述 (Prompt)...")
        self.prompt_input.setFixedHeight(45)
        self.prompt_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 0 15px;
                font-size: 14px;
                background-color: #fff;
            }
            QLineEdit:focus {
                border: 1px solid #2196f3;
            }
        """)
        self.prompt_input.returnPressed.connect(self.generate_image)
        
        self.generate_btn = QPushButton("生成图片")
        self.generate_btn.setFixedHeight(45)
        self.generate_btn.setFixedWidth(120)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.generate_btn.clicked.connect(self.generate_image)

        self.save_btn = QPushButton("下载图片")
        self.save_btn.setFixedHeight(45)
        self.save_btn.setFixedWidth(120)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setEnabled(False) # 初始不可用
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.save_btn.clicked.connect(self.save_image)

        control_layout.addWidget(self.prompt_input)
        control_layout.addWidget(self.generate_btn)
        control_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(control_layout)

        # 图片展示区域 (下方)
        self.image_area = QLabel("此处显示生成的图片")
        self.image_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_area.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 10px;
                color: #999;
                font-size: 16px;
            }
        """)
        self.image_area.setMinimumSize(400, 400)
        self.image_area.setSizePolicy(
            self.image_area.sizePolicy().horizontalPolicy(),
            self.image_area.sizePolicy().verticalPolicy()
        )
        
        # 使用 ScrollArea 包裹图片
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.image_area)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        main_layout.addWidget(scroll_area, 1) # 1 表示占用剩余空间

    def set_auth_token(self, token: str):
        self.auth_token = token or ""

    def generate_image(self):
        prompt = self.prompt_input.text().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入画面描述")
            return
        
        if not self.auth_token:
            QMessageBox.warning(self, "提示", "请先登录")
            return

        # UI 状态更新
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("生成中...")
        self.save_btn.setEnabled(False) # 禁用保存
        self.prompt_input.setEnabled(False)
        self.image_area.setText("正在请求 AI 绘图，请稍候...")
        self.image_area.clear() # 清除之前的图片
        self.image_area.setText("正在生成中...")

        # 启动生成线程
        self.worker = ImageGenWorker(self.auth_token, prompt)
        self.worker.finished_signal.connect(self.on_generation_finished)
        self.worker.start()

    def on_generation_finished(self, success, msg, data):
        if not success:
            self.reset_ui_state()
            self.image_area.setText("生成失败")
            QMessageBox.warning(self, "错误", msg)
            return

        # 解析返回结果
        # 假设返回格式: {"data": [{"url": "..."}]}
        try:
            # 解析嵌套的响应结构
            # 格式: {"code": 200, "data": {"created": ..., "data": [{"url": "..."}]}}
            payload = data.get("data", {})
            if isinstance(payload, dict):
                items = payload.get("data", [])
            else:
                items = [] # 容错
                
            if not items or not isinstance(items, list):
                # 尝试直接解析（兼容非标准结构）
                if isinstance(payload, list):
                    items = payload
                else:
                     raise ValueError(f"响应格式不符合预期: {str(data)[:100]}...")

            image_url = items[0].get("url", "")
            if not image_url:
                raise ValueError("未找到图片URL")
            
            # 下载图片
            self.image_area.setText("正在下载图片...")
            self.dl_worker = ImageDownloadWorker(image_url)
            self.dl_worker.finished_signal.connect(self.on_download_finished)
            self.dl_worker.start()
            
        except Exception as e:
            self.reset_ui_state()
            self.image_area.setText("解析结果失败")
            QMessageBox.warning(self, "错误", f"解析响应失败: {str(e)}")

    def on_download_finished(self, success, content):
        self.reset_ui_state()
        if success and content:
            pixmap = QPixmap()
            pixmap.loadFromData(content)
            
            # 缩放图片以适应显示区域 (保持比例)
            # 实际上 QLabel 在 ScrollArea 中可以显示原图，或者我们手动缩放
            # 这里先直接显示原图，ScrollArea 会处理滚动
            self.image_area.setPixmap(pixmap)
            self.image_area.setScaledContents(False) # 不强制拉伸，保持原比例
            self.image_area.resize(pixmap.size()) # 调整 label 大小以适应图片
            self.save_btn.setEnabled(True) # 启用保存按钮
        else:
            self.image_area.setText("图片加载失败")
            QMessageBox.warning(self, "错误", "无法下载生成的图片")

    def reset_ui_state(self):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("生成图片")
        self.prompt_input.setEnabled(True)
        self.prompt_input.setFocus()

    def save_image(self):
        pixmap = self.image_area.pixmap()
        if not pixmap or pixmap.isNull():
            QMessageBox.warning(self, "提示", "没有可保存的图片")
            return

        # 生成默认文件名
        default_name = f"ai_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存图片", 
            os.path.join(os.path.expanduser("~"), "Pictures", default_name),
            "Images (*.png *.jpg *.bmp)"
        )

        if file_path:
            try:
                if not pixmap.save(file_path):
                     QMessageBox.warning(self, "错误", "保存图片失败")
                else:
                     QMessageBox.information(self, "成功", f"图片已保存至: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"保存图片出错: {str(e)}")
