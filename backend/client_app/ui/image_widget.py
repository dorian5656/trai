#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/ui/image_widget.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 图像识别界面 (支持拖拽上传)

import sys
import base64
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
    QPushButton, QFrame, QFileDialog, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QMimeData, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from utils.api_client import ApiClient

class ImageWorker(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, messages):
        super().__init__()
        self.messages = messages
        self.client = ApiClient()

    def run(self):
        try:
            payload = {
                "messages": self.messages,
                "model": "Qwen3-VL-4B-Instruct",
                "temperature": 0.7,
                "max_tokens": 512
            }
            # 调用 /api/v1/ai/image/chat/image
            resp = self.client.post("/api/v1/ai/image/chat/image", json_data=payload, timeout=60)
            
            if resp.status_code == 200:
                result = resp.json()
                reply = result.get("reply", "")
                self.finished_signal.emit(reply)
            else:
                self.error_signal.emit(f"Error {resp.status_code}: {resp.text}")
        except Exception as e:
            self.error_signal.emit(str(e))

class DropLabel(QLabel):
    image_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("\n\n拖拽图片到此处\n或点击上传\n\n")
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f9f9f9;
                color: #555;
                font-size: 16px;
            }
            QLabel:hover {
                border-color: #3498db;
                background-color: #eaf6ff;
            }
        """)
        self.setAcceptDrops(True)
        self.setMinimumHeight(200)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                self.image_dropped.emit(path)
            else:
                QMessageBox.warning(self, "格式错误", "仅支持图片文件 (png, jpg, jpeg, bmp, gif)")

    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            self.image_dropped.emit(path)

class ImageWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.current_image_path = None
        self.current_base64 = None
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 顶部提示
        layout.addWidget(QLabel("<h2>📷 图像识别 (Qwen-VL)</h2>"))
        
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧: 图片上传与预览
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        self.drop_area = DropLabel()
        self.drop_area.image_dropped.connect(self.on_image_selected)
        left_layout.addWidget(self.drop_area)
        
        self.preview_lbl = QLabel()
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        self.preview_lbl.setMinimumHeight(200)
        self.preview_lbl.setStyleSheet("border: 1px solid #ddd; background-color: #fff;")
        self.preview_lbl.hide()
        left_layout.addWidget(self.preview_lbl)
        
        self.reupload_btn = QPushButton("重新上传")
        self.reupload_btn.clicked.connect(self.reset_image)
        self.reupload_btn.hide()
        left_layout.addWidget(self.reupload_btn)
        
        left_layout.addStretch()
        splitter.addWidget(left_widget)
        
        # 右侧: 对话与结果
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setPlaceholderText("识别结果将显示在这里...")
        self.result_area.setStyleSheet("background-color: white; border: 1px solid #ddd;")
        right_layout.addWidget(self.result_area)
        
        input_layout = QHBoxLayout()
        self.input_box = QTextEdit()
        self.input_box.setMaximumHeight(80)
        self.input_box.setPlaceholderText("输入提示词 (例如: 描述这张图片)")
        self.input_box.setText("描述这张图片")
        input_layout.addWidget(self.input_box)
        
        self.send_btn = QPushButton("识别/对话")
        self.send_btn.setMinimumHeight(80)
        self.send_btn.clicked.connect(self.start_recognition)
        self.send_btn.setEnabled(False)
        input_layout.addWidget(self.send_btn)
        
        right_layout.addLayout(input_layout)
        splitter.addWidget(right_widget)
        
        # 设置分割比例 4:6
        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        
    def on_image_selected(self, path):
        self.current_image_path = path
        
        # 显示预览
        pixmap = QPixmap(path)
        self.preview_lbl.setPixmap(pixmap.scaled(self.preview_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.preview_lbl.show()
        self.drop_area.hide()
        self.reupload_btn.show()
        
        # 转换为 Base64
        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            # 简单判断 mime type
            ext = path.split('.')[-1].lower()
            mime = "jpeg" if ext == "jpg" else ext
            self.current_base64 = f"data:image/{mime};base64,{encoded_string}"
            
        self.send_btn.setEnabled(True)
        self.result_area.append(f"图片已加载: {path}")
        
    def reset_image(self):
        self.current_image_path = None
        self.current_base64 = None
        self.preview_lbl.hide()
        self.reupload_btn.hide()
        self.drop_area.show()
        self.send_btn.setEnabled(False)
        self.result_area.clear()
        
    def start_recognition(self):
        prompt = self.input_box.toPlainText().strip()
        if not prompt:
            prompt = "描述这张图片"
            
        if not self.current_base64:
            return
            
        self.send_btn.setEnabled(False)
        self.result_area.append(f"\n<b>User:</b> {prompt}")
        self.result_area.append("正在分析中...")
        
        # 构造多模态消息
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": self.current_base64},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
        
        self.worker = ImageWorker(messages)
        self.worker.finished_signal.connect(self.on_success)
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()
        
    def on_success(self, reply):
        self.result_area.append(f"<b>AI:</b> {reply}")
        self.send_btn.setEnabled(True)
        
    def on_error(self, err):
        self.result_area.append(f"<span style='color:red'>Error: {err}</span>")
        self.send_btn.setEnabled(True)
