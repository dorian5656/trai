#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/ui/chat_widget.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 聊天界面 (支持 Markdown 与流式输出)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QTextEdit, 
    QPushButton, QLabel, QComboBox, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import markdown
from utils.api_client import ApiClient
from utils.config import Config

class ChatWorker(QThread):
    chunk_received = pyqtSignal(str) # 流式片段
    finished_signal = pyqtSignal(str) # 完成信号 (完整文本)
    error_signal = pyqtSignal(str)

    def __init__(self, content, model, username):
        super().__init__()
        self.content = content
        self.model = model
        self.username = username
        self.client = ApiClient()

    def run(self):
        try:
            if self.model.startswith("dify"):
                url = "/api/v1/dify/chat"
                app_name = self.model.split("-")[1]
                payload = {
                    "query": self.content,
                    "user": self.username,
                    "app_name": app_name,
                    "stream": True # 开启流式
                }
            else:
                url = "/api/v1/ai/chat/completions"
                payload = {
                    "messages": [{"role": "user", "content": self.content}],
                    "model": self.model,
                    "temperature": 0.7,
                    "stream": True # 开启流式 (假设后端支持)
                }

            # 发起流式请求
            resp = self.client.stream_post(url, json_data=payload)
            
            full_text = ""
            for line in resp.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    # 处理 SSE 格式 (data: ...)
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        # 这里需要根据后端具体返回格式解析
                        # 假设 backend 直接返回 token 或者 json
                        # 如果是 JSON: {"content": "..."}
                        # 如果是纯文本: "..."
                        # 简单起见，假设 data 就是文本片段 (Dify 通常返回 JSON)
                        
                        # Dify SSE 格式: data: {"event": "message", "answer": "..."}
                        import json
                        try:
                            json_data = json.loads(data)
                            if "answer" in json_data:
                                chunk = json_data["answer"]
                            elif "choices" in json_data: # OpenAI 格式
                                chunk = json_data["choices"][0]["delta"].get("content", "")
                            else:
                                chunk = data # Fallback
                        except:
                            chunk = data

                        full_text += chunk
                        self.chunk_received.emit(chunk)
            
            self.finished_signal.emit(full_text)

        except Exception as e:
            self.error_signal.emit(str(e))

class ChatWidget(QWidget):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 顶部配置栏
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("当前模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["deepseek-chat", "Qwen3-VL-4B-Instruct", "dify-guanwang"])
        self.model_combo.setMinimumWidth(200)
        config_layout.addWidget(self.model_combo)
        config_layout.addStretch()
        layout.addLayout(config_layout)
        
        # 聊天记录 (使用 QTextBrowser 支持 HTML/Markdown)
        self.chat_history = QTextBrowser()
        self.chat_history.setOpenExternalLinks(True) # 允许点击链接
        self.chat_history.setStyleSheet("background-color: white; border-radius: 5px; border: 1px solid #dcdcdc; padding: 10px;")
        layout.addWidget(self.chat_history)
        
        # 输入区
        input_layout = QHBoxLayout()
        self.input_box = QTextEdit()
        self.input_box.setMaximumHeight(100)
        self.input_box.setPlaceholderText("在此输入消息 (支持 Markdown)...")
        self.input_box.setStyleSheet("background-color: white; border-radius: 5px; border: 1px solid #dcdcdc;")
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setMinimumHeight(50)
        self.send_btn.setMinimumWidth(100)
        self.send_btn.setStyleSheet("background-color: #3498db; color: white; border-radius: 5px; font-weight: bold;")
        self.send_btn.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.input_box)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)
        
        # 内部状态
        self.history_html = "" # 累积的 HTML 记录
        self.current_ai_response = "" # 当前正在生成的 AI 回复
        
    def send_message(self):
        content = self.input_box.toPlainText().strip()
        if not content:
            return
            
        model = self.model_combo.currentText()
        
        # 显示用户消息
        user_html = self.render_markdown(content)
        self.append_message("User", user_html, model)
        
        self.input_box.clear()
        self.send_btn.setEnabled(False)
        
        # 准备 AI 回复容器
        self.current_ai_response = ""
        self.history_html += f"<div style='margin: 10px 0; color: #2c3e50;'><b>AI:</b><br><span id='current_ai'>...</span></div><hr>"
        self.chat_history.setHtml(self.history_html)
        
        # 启动线程
        self.worker = ChatWorker(content, model, self.username)
        self.worker.chunk_received.connect(self.on_chunk_received)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()
        
    def on_chunk_received(self, chunk):
        self.current_ai_response += chunk
        # 实时渲染 Markdown (可能会有点重，但对于文本量不大还好)
        # 为了性能，可以只渲染当前段落，这里简单全量渲染当前回复
        ai_html = self.render_markdown(self.current_ai_response)
        
        # 更新 HTML (Hack: 替换 id='current_ai' 的内容)
        # PyQt QTextBrowser 不支持动态 DOM 操作，必须重置 HTML
        # 这会导致滚动条跳动，需要处理
        
        # 更好的方式：只追加，不重置。但 Markdown 需要上下文。
        # 简单方案：累积 HTML，重新 setHtml
        
        temp_html = self.history_html.replace("<span id='current_ai'>...</span>", f"<span>{ai_html}</span>")
        
        sb = self.chat_history.verticalScrollBar()
        old_val = sb.value()
        is_at_bottom = old_val == sb.maximum()
        
        self.chat_history.setHtml(temp_html)
        
        if is_at_bottom:
            sb.setValue(sb.maximum())
        else:
            sb.setValue(old_val)
            
    def on_finished(self, full_text):
        # 最终确认
        ai_html = self.render_markdown(full_text)
        # 将占位符永久替换
        self.history_html = self.history_html.replace("<span id='current_ai'>...</span>", f"<span>{ai_html}</span>")
        self.chat_history.setHtml(self.history_html)
        self.send_btn.setEnabled(True)
        
        sb = self.chat_history.verticalScrollBar()
        sb.setValue(sb.maximum())
        
    def on_error(self, err_msg):
        self.history_html += f"<div style='color: red;'>Error: {err_msg}</div>"
        self.chat_history.setHtml(self.history_html)
        self.send_btn.setEnabled(True)
        
    def append_message(self, role, html_content, model=None):
        header = f"{role} ({model})" if model else role
        color = "#2980b9" if role == "User" else "#2c3e50"
        self.history_html += f"<div style='margin: 10px 0; color: {color};'><b>{header}:</b><br>{html_content}</div>"
        self.chat_history.setHtml(self.history_html)
        
        sb = self.chat_history.verticalScrollBar()
        sb.setValue(sb.maximum())

    def render_markdown(self, text):
        try:
            # 扩展: fenced_code (代码块), tables (表格)
            return markdown.markdown(text, extensions=['fenced_code', 'tables'])
        except Exception:
            return text
