#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：image_parse_page.py
# 作者：liuhd
# 日期：2026-02-05 13:53
# 描述：图片内容解析页面

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTextEdit, QMessageBox, QFileDialog, QApplication, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QKeySequence
import requests
import os
import tempfile
from datetime import datetime
import json
import sys
from .config_loader import config

class ChatLineEdit(QLineEdit):
    """支持图片粘贴的输入框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paste_image_callback = None

    def set_paste_image_callback(self, callback):
        self.paste_image_callback = callback

    def keyPressEvent(self, event):
        # 检查是否是粘贴快捷键 (Ctrl+V)
        if event.matches(QKeySequence.StandardKey.Paste):
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()
            
            # 如果剪贴板中有图片
            if mime_data.hasImage():
                image = clipboard.image()
                if not image.isNull() and self.paste_image_callback:
                    self.paste_image_callback(image)
                    return
        
        # 否则执行默认操作
        super().keyPressEvent(event)

class ImageAnalysisWorker(QThread):
    finished_signal = pyqtSignal(bool, str, str) # 成功, 消息, 结果

    def __init__(self, token, image_url, prompt="Describe this image."):
        super().__init__()
        self.token = token
        self.image_url = image_url
        self.prompt = prompt

    def run(self):
        try:
            url = config["image_parse"]["api_url"]
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}" # 假设需要令牌
            }
            
            payload = {
                "max_tokens": 512,
                "messages": [
                    {
                        "content": [
                            {
                                "image": self.image_url,
                                "type": "image"
                            },
                            {
                                "text": self.prompt,
                                "type": "text"
                            }
                        ],
                        "role": "user"
                    }
                ],
                "model": "Qwen/Qwen3-VL-4B-Instruct",
                "temperature": 0.7
            }
            
            # 注意：用户示例使用了 'http' 而不是 'https'。
            # 鉴于 URL 中包含 "stream"，我们尝试 stream=True 并逐行读取。
            
            response = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
            
            if response.status_code == 200:
                # 检查内容类型
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    # 非流式 JSON 响应
                    result = response.json()
                    # 如果直接返回字符串
                    if isinstance(result, str):
                        self.finished_signal.emit(True, "Success", result)
                    elif isinstance(result, dict) and "choices" in result:
                        content = result["choices"][0]["message"]["content"]
                        self.finished_signal.emit(True, "Success", content)
                    else:
                        self.finished_signal.emit(True, "Success", str(result)) # 兜底
                else:
                    # 流式响应 (SSE)
                    full_content = ""
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                data_str = decoded_line[6:]
                                if data_str.strip() == "[DONE]":
                                    break
                                try:
                                    data_json = json.loads(data_str)
                                    # 假设 OpenAI 流格式
                                    if "choices" in data_json:
                                        delta = data_json["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        full_content += content
                                except:
                                    # 非 JSON 格式，可能是纯文本流
                                    full_content += data_str
                            else:
                                # 可能是原始文本流?
                                full_content += decoded_line
                    self.finished_signal.emit(True, "Success", full_content)
            else:
                self.finished_signal.emit(False, f"HTTP {response.status_code}: {response.text}", "")
                
        except Exception as e:
            self.finished_signal.emit(False, str(e), "")

class ImageParsePage(QWidget):
    def __init__(self):
        super().__init__()
        self.auth_token = ""
        self.current_image_path = ""
        self.init_ui()

    def set_auth_token(self, token: str):
        self.auth_token = token or ""

    def preview_drag_enter_event(self, event):
        """处理拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                # 检查文件扩展名
                file_path = urls[0].toLocalFile()
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']:
                    event.accept()
                    return
        event.ignore()

    def preview_drop_event(self, event):
        """处理拖拽释放事件"""
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            file_path = urls[0].toLocalFile()
            self.load_image_preview(file_path)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. 标题
        title = QLabel("图片内容解析")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # 2. 图片预览区 (支持拖拽)
        self.image_preview = QLabel("请上传或粘贴图片，或将图片拖拽至此")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setFixedHeight(400)
        self.image_preview.setStyleSheet("""
            QLabel {
                border: 2px dashed #ccc;
                border-radius: 10px;
                background-color: #f9f9f9;
                color: #999;
                font-size: 16px;
            }
        """)
        # 启用拖拽
        self.image_preview.setAcceptDrops(True)
        # 绑定事件处理
        self.image_preview.dragEnterEvent = self.preview_drag_enter_event
        self.image_preview.dropEvent = self.preview_drop_event
        
        layout.addWidget(self.image_preview)

        # 3. 操作区 (上传按钮 + 提示词输入)
        ops_layout = QHBoxLayout()
        
        upload_btn = QPushButton("📂 上传图片")
        upload_btn.setFixedSize(120, 40)
        upload_btn.clicked.connect(self.upload_image_dialog)
        upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 5px;
                color: #333;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        ops_layout.addWidget(upload_btn)

        self.prompt_input = ChatLineEdit()
        self.prompt_input.setPlaceholderText("输入提示词 (默认: 描述这张图片.)，支持 Ctrl+V 粘贴图片")
        self.prompt_input.set_paste_image_callback(self.handle_paste_image)
        self.prompt_input.setFixedHeight(40)
        self.prompt_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 0 10px;
                font-size: 14px;
            }
        """)
        ops_layout.addWidget(self.prompt_input)

        self.parse_btn = QPushButton("开始解析")
        self.parse_btn.setFixedSize(120, 40)
        self.parse_btn.clicked.connect(self.start_analysis)
        self.parse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        ops_layout.addWidget(self.parse_btn)

        layout.addLayout(ops_layout)

        # 4. 结果显示区
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setPlaceholderText("解析结果将显示在这里...")
        self.result_area.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e5e5e5;
                border-radius: 10px;
                background-color: #fff;
                padding: 10px;
                font-size: 14px;
                color: #333;
            }
        """)
        layout.addWidget(self.result_area)

    def handle_paste_image(self, image):
        """处理粘贴的图片"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = tempfile.gettempdir()
            filename = f"paste_parse_{timestamp}.png"
            file_path = os.path.join(temp_dir, filename)
            image.save(file_path, "PNG")
            self.load_image_preview(file_path)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"粘贴图片失败: {str(e)}")

    def upload_image_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.load_image_preview(file_path)

    def load_image_preview(self, file_path):
        self.current_image_path = file_path
        pixmap = QPixmap(file_path)
        # 缩放图片以适应预览区域，保持纵横比
        scaled_pixmap = pixmap.scaled(self.image_preview.size(), 
                                    Qt.AspectRatioMode.KeepAspectRatio, 
                                    Qt.TransformationMode.SmoothTransformation)
        self.image_preview.setPixmap(scaled_pixmap)

    def start_analysis(self):
        if not self.current_image_path:
            QMessageBox.warning(self, "提示", "请先上传或粘贴图片")
            return

        prompt = self.prompt_input.text().strip()
        if not prompt:
            prompt = "Describe this image."

        self.parse_btn.setEnabled(False)
        self.result_area.setText("正在上传图片并解析中，请稍候...")
        
        # 先上传图片获取URL
        # 注意：这里需要在线程中执行，避免阻塞UI，或者先在主线程简单处理
        # 为了简单起见，我先在主线程上传（因为requests是阻塞的），如果文件大可能会卡顿
        # 更好的方式是把上传也放到Worker里
        
        # 这里我重新定义一个Worker包含上传和解析两步
        self.worker = FullProcessWorker(self.auth_token, self.current_image_path, prompt)
        self.worker.finished_signal.connect(self.on_analysis_finished)
        self.worker.start()

    def on_analysis_finished(self, success, msg, result):
        self.parse_btn.setEnabled(True)
        if success:
            self.result_area.setText(result)
        else:
            self.result_area.setText(f"解析失败: {msg}")
            QMessageBox.warning(self, "错误", msg)

class FullProcessWorker(QThread):
    finished_signal = pyqtSignal(bool, str, str) # 成功, 消息, 结果

    def __init__(self, token, file_path, prompt):
        super().__init__()
        self.token = token
        self.file_path = file_path
        self.prompt = prompt

    def run(self):
        print(f"Worker started. Token len: {len(self.token) if self.token else 0}")
        print(f"File: {self.file_path}")
        sys.stdout.flush()
        
        # 1. 上传图片
        file_url = ""
        try:
            # 使用 5777 端口上传
            upload_url = config["image_parse"]["upload_url"]
            headers = {"Authorization": f"Bearer {self.token}"}
            data = {"module": "image_parse"}
            
            print(f"Uploading to {upload_url}...")
            sys.stdout.flush()
            with open(self.file_path, "rb") as f:
                files = {"file": (os.path.basename(self.file_path), f, "application/octet-stream")}
                response = requests.post(upload_url, headers=headers, data=data, files=files, timeout=60)
            
            print(f"Upload status: {response.status_code}")
            sys.stdout.flush()
            if response.status_code != 200:
                print(f"Upload failed: {response.text}")
                sys.stdout.flush()
                self.finished_signal.emit(False, f"上传失败 HTTP {response.status_code}", "")
                return
                
            file_url = response.json().get("url", "")
            print(f"Upload successful. URL: {file_url}")
            sys.stdout.flush()
            if not file_url:
                self.finished_signal.emit(False, "上传成功但未返回URL", "")
                return

        except Exception as e:
            print(f"Upload exception: {e}")
            sys.stdout.flush()
            self.finished_signal.emit(False, f"上传异常: {str(e)}", "")
            return

        # 2. 调用解析 API
        try:
            analyze_url = config["image_parse"]["api_url"]
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}"
            }
            
            payload = {
                "max_tokens": 512,
                "messages": [
                    {
                        "content": [
                            {
                                "image": file_url,
                                "type": "image"
                            },
                            {
                                "text": self.prompt,
                                "type": "text"
                            }
                        ],
                        "role": "user"
                    }
                ],
                "model": "Qwen/Qwen3-VL-4B-Instruct",
                "temperature": 0.7
            }
            
            print(f"Analyzing with URL: {analyze_url}")
            print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
            sys.stdout.flush()
            
            response = requests.post(analyze_url, headers=headers, json=payload, stream=True, timeout=120)
            print(f"Analysis status: {response.status_code}")
            sys.stdout.flush()
            
            if response.status_code == 200:
                # 尝试解析响应
                content_type = response.headers.get("Content-Type", "")
                print(f"Content-Type: {content_type}")
                sys.stdout.flush()
                full_content = ""
                
                # 如果是流式
                if "application/json" in content_type:
                    try:
                        res_json = response.json()
                        print(f"JSON Response: {res_json}")
                        sys.stdout.flush()
                        
                        # 尝试多种常见的响应格式
                        if isinstance(res_json, str):
                             full_content = res_json
                        elif isinstance(res_json, dict):
                            # 1. OpenAI 格式
                            if "choices" in res_json and len(res_json["choices"]) > 0:
                                full_content = res_json["choices"][0]["message"]["content"]
                            # 2. Trae/DeepSeek 自定义格式 (data.reply)
                            elif "data" in res_json and isinstance(res_json["data"], dict) and "reply" in res_json["data"]:
                                full_content = res_json["data"]["reply"]
                            # 3. 直接内容字段
                            elif "content" in res_json:
                                full_content = res_json["content"]
                            # 4. 兜底: 转储完整 JSON
                            else:
                                full_content = json.dumps(res_json, ensure_ascii=False, indent=2)
                        else:
                            full_content = str(res_json)
                            
                    except Exception as e:
                        print(f"JSON parse error: {e}")
                        sys.stdout.flush()
                        full_content = response.text
                else:
                    # 默认当做流式文本处理
                    print("Reading stream...")
                    sys.stdout.flush()
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            # print(f"Stream line: {decoded_line}")
                            # 去掉 "data: " 前缀
                            if decoded_line.startswith("data: "):
                                data_str = decoded_line[6:]
                                if data_str.strip() == "[DONE]":
                                    break
                                try:
                                    data_json = json.loads(data_str)
                                    if "choices" in data_json and len(data_json["choices"]) > 0:
                                        delta = data_json["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        full_content += content
                                    elif "content" in data_json: # 另一种常见格式
                                        full_content += data_json["content"]
                                except:
                                    # 非 JSON 格式，可能是纯文本流
                                    full_content += data_str
                            else:
                                full_content += decoded_line + "\n"
                
                print(f"Final content length: {len(full_content)}")
                sys.stdout.flush()
                
                if not full_content:
                    full_content = "(服务器返回了空白内容)"
                    # 尝试读取原始文本作为调试
                    try:
                        # 如果是流式响应，iter_lines可能已经消耗了内容，无法再次读取 response.text
                        # 但如果是json模式，response.text 应该还在
                         if "application/json" in content_type:
                             full_content += f"\n\nRaw Response: {response.text}"
                    except:
                        pass

                self.finished_signal.emit(True, "Success", full_content)
            else:
                print(f"Analysis failed: {response.text}")
                sys.stdout.flush()
                self.finished_signal.emit(False, f"解析请求失败 HTTP {response.status_code}: {response.text}", "")

        except Exception as e:
            print(f"Analysis exception: {e}")
            sys.stdout.flush()
            self.finished_signal.emit(False, f"解析异常: {str(e)}", "")
