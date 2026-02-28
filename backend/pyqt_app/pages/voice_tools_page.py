#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：voice_tools_page.py
# 作者：liuhd
# 日期：2026-02-26 13:59:00
# 描述：语音服务页面，提供语音识别、语音服务检查等功能。

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QFileDialog, QLineEdit,
                             QTextEdit, QScrollArea, QMessageBox, QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
import requests
import os
import mimetypes
from .config_loader import config
from loguru import logger

class SpeechHealthWorker(QThread):
    """语音服务健康检查线程"""
    finished_signal = pyqtSignal(bool, dict, str)

    def __init__(self, api_url):
        super().__init__()
        self.api_url = api_url

    def run(self):
        try:
            logger.info(f"Checking speech health at: {self.api_url}")
            response = requests.get(self.api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.finished_signal.emit(True, data, "检查成功")
            else:
                self.finished_signal.emit(False, {}, f"HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Speech health check failed: {e}")
            self.finished_signal.emit(False, {}, str(e))

class SpeechASRWorker(QThread):
    """语音转文字工作线程"""
    finished_signal = pyqtSignal(bool, dict, str)

    def __init__(self, api_url, file_path, token=None):
        super().__init__()
        self.api_url = api_url
        self.file_path = file_path
        self.token = token

    def run(self):
        try:
            if not os.path.exists(self.file_path):
                self.finished_signal.emit(False, {}, "文件不存在")
                return

            logger.info(f"Starting ASR for file: {self.file_path} at {self.api_url}")
            
            # 猜测 MIME 类型
            mime_type, _ = mimetypes.guess_type(self.file_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            
            file_name = os.path.basename(self.file_path)
            
            # 构造 headers
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            # 构造 multipart/form-data 请求
            # curl示例: -F 'file=@女生.wav;type=audio/wav'
            files = {
                'file': (file_name, open(self.file_path, 'rb'), mime_type)
            }
            
            # 发送请求
            # 注意：requests 自动设置 boundary，不要手动设置 Content-Type
            response = requests.post(self.api_url, files=files, headers=headers, timeout=300) # ASR 可能耗时较长
            
            if response.status_code == 200:
                data = response.json()
                self.finished_signal.emit(True, data, "转换成功")
            else:
                try:
                    err_data = response.json()
                    err_msg = err_data.get("detail", f"HTTP {response.status_code}")
                except:
                    err_msg = f"HTTP {response.status_code}"
                self.finished_signal.emit(False, {}, err_msg)
                
        except Exception as e:
            logger.error(f"ASR failed: {e}")
            self.finished_signal.emit(False, {}, str(e))
        finally:
            # 确保文件句柄被关闭 (requests 的 files 参数如果传入文件对象，requests 不会负责关闭它，但上下文退出时会清理)
            # 显式关闭更好，但这里 open 是在 files 字典里直接调用的，引用计数可能导致无法立即关闭
            # 更严谨的做法是使用 with open... 但在 requests files 参数中比较麻烦
            pass


class VoiceToolsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.token = ""
        self.init_ui()

    def set_auth_token(self, token: str) -> None:
        self.token = token or ""

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e0e0e0;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 0, 30, 0)
        
        title_label = QLabel("🎙️ 语音服务")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333333;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        main_layout.addWidget(header)

        # Content Widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(30, 30, 30, 30)

        # 1. 语音服务健康检查
        health_group = self.create_card("语音服务健康检查")
        health_layout = health_group.layout()
        
        check_btn = QPushButton("检查服务状态")
        check_btn.setFixedWidth(120)
        check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        check_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 6px;
                padding: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        check_btn.clicked.connect(self._check_health)
        health_layout.addWidget(check_btn)
        
        self.check_btn = check_btn # 保存引用以便禁用/启用
        
        self.health_status_label = QLabel("等待检查...")
        self.health_status_label.setStyleSheet("color: #666; margin-top: 10px; font-size: 13px; line-height: 1.5; background-color: transparent;")
        self.health_status_label.setWordWrap(True)
        health_layout.addWidget(self.health_status_label)
        
        content_layout.addWidget(health_group)

        # 2. 音频转文字
        asr_group = self.create_card("音频转文字")
        asr_layout = asr_group.layout()
        
        # 文件选择
        file_label = QLabel("选择音频文件:")
        file_label.setStyleSheet("color: #555; font-weight: bold; margin-bottom: 5px; background-color: transparent;")
        asr_layout.addWidget(file_label)

        file_row = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("支持 mp3, wav, m4a, flac 等格式")
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 8px;
                background-color: #f9f9f9;
                color: #333;
            }
        """)
        file_row.addWidget(self.file_path_edit)
        
        select_file_btn = QPushButton("浏览...")
        select_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_file_btn.clicked.connect(self.select_audio_file)
        select_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f2f5;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 8px 15px;
                color: #333;
            }
            QPushButton:hover { background-color: #e6e8eb; }
        """)
        file_row.addWidget(select_file_btn)
        asr_layout.addLayout(file_row)
        
        # 转换按钮
        convert_btn = QPushButton("开始转换")
        convert_btn.setFixedWidth(120)
        convert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #67c23a;
                color: white;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
                font-size: 13px;
                margin-top: 10px;
            }
            QPushButton:hover { background-color: #85ce61; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        convert_btn.clicked.connect(self.start_asr_conversion)
        asr_layout.addWidget(convert_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        self.convert_btn = convert_btn
        
        # 结果输出
        result_layout = QHBoxLayout()
        result_label = QLabel("转换结果:")
        result_label.setStyleSheet("color: #555; font-weight: bold; margin-top: 15px; margin-bottom: 5px; background-color: transparent;")
        result_layout.addWidget(result_label)
        result_layout.addStretch()
        
        # 复制成功提示
        self.copy_tip_label = QLabel("复制成功")
        self.copy_tip_label.setStyleSheet("color: #67c23a; font-size: 12px; margin-right: 10px; font-weight: bold;")
        self.copy_tip_label.hide() # 默认隐藏
        result_layout.addWidget(self.copy_tip_label)
        
        # 复制按钮
        copy_btn = QPushButton("复制")
        copy_btn.setFixedWidth(60)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #606266;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                margin-top: 15px;
            }
            QPushButton:hover {
                color: #409eff;
                border-color: #c6e2ff;
                background-color: #ecf5ff;
            }
        """)
        copy_btn.clicked.connect(self.copy_result_to_clipboard)
        result_layout.addWidget(copy_btn)
        
        asr_layout.addLayout(result_layout)
        
        self.asr_result_area = QTextEdit()
        self.asr_result_area.setPlaceholderText("识别到的文字内容将显示在这里...")
        # 移除固定高度限制，让其填充剩余空间
        # self.asr_result_area.setMinimumHeight(400)
        # self.asr_result_area.setMaximumHeight(600)
        self.asr_result_area.setStyleSheet("""
            QTextEdit {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 10px;
                background-color: #ffffff;
                color: #333;
                font-size: 14px;
                line-height: 1.5;
            }
        """)
        asr_layout.addWidget(self.asr_result_area)
        
        # 设置布局伸缩因子，让结果区域占据剩余空间
        # asr_group 是 VBox，asr_result_area 是最后一个 widget
        # 我们希望 asr_group 本身也能伸展
        content_layout.addWidget(asr_group, 1) # stretch=1
        
        # 移除原来的 addStretch
        # content_layout.addStretch()

        main_layout.addWidget(content_widget)

    def create_card(self, title):
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            #card {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #eaeaea;
            }
        """)
        # 添加阴影效果 (虽然QSS支持有限，但配合背景色可以营造层次感)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(10)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333; border: none; margin-bottom: 10px; background-color: transparent;")
        layout.addWidget(title_label)
        
        return card

    def select_audio_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择音频文件",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg *.aac);;All Files (*)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    def _get_api_url(self, key: str) -> str:
        """获取 API 地址"""
        # 尝试从配置中获取
        url = config.get("voice_tools", {}).get(key, "")
        if url:
            return url
            
        return ""

    def _check_health(self):
        api_url = self._get_api_url("health_url")
        if not api_url:
            QMessageBox.warning(self, "错误", "未找到语音服务接口地址")
            return
            
        self.check_btn.setEnabled(False)
        self.check_btn.setText("检查中...")
        self.health_status_label.setText("正在连接服务器...")
        
        self.health_worker = SpeechHealthWorker(api_url)
        self.health_worker.finished_signal.connect(self._on_health_check_finished)
        self.health_worker.start()

    def _on_health_check_finished(self, success: bool, data: dict, msg: str):
        self.check_btn.setEnabled(True)
        self.check_btn.setText("检查服务状态")
        
        if success:
            status = data.get("status", "unknown")
            device = data.get("device", "unknown")
            model_loaded = data.get("model_loaded", False)
            model_path = data.get("model_path", "")
            
            color = "#67c23a" if status == "ok" and model_loaded else "#e6a23c"
            status_text = (
                f"状态: <span style='color:{color}; font-weight:bold;'>{status}</span><br>"
                f"设备: {device}<br>"
                f"模型加载: {'✅ 已加载' if model_loaded else '❌ 未加载'}<br>"
                f"模型路径: {model_path}"
            )
            self.health_status_label.setText(status_text)
        else:
            self.health_status_label.setText(f"<span style='color:#f56c6c;'>检查失败: {msg}</span>")

    def start_asr_conversion(self):
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "提示", "请先选择音频文件")
            return
            
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "错误", "文件不存在")
            return
            
        api_url = self._get_api_url("asr_url")
        if not api_url:
            QMessageBox.warning(self, "错误", "未找到音频转文字接口地址")
            return
            
        self.convert_btn.setEnabled(False)
        self.convert_btn.setText("转换中...")
        self.asr_result_area.setText("正在上传并转换，请稍候...")
        
        self.asr_worker = SpeechASRWorker(api_url, file_path, self.token)
        self.asr_worker.finished_signal.connect(self._on_asr_finished)
        self.asr_worker.start()

    def _on_asr_finished(self, success: bool, data: dict, msg: str):
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText("开始转换")
        
        if success:
            # 根据截图返回结构: {'code': 200, 'msg': 'success', 'data': {'text': '...', 'url': '...'}}
            # data 参数已经是 response.json() 的结果
            
            # 优先尝试从 data['data']['text'] 获取
            inner_data = data.get("data", {})
            if isinstance(inner_data, dict):
                text = inner_data.get("text", "")
            else:
                text = ""
                
            # 如果没找到，尝试直接从 data['text'] 获取 (兼容其他可能的格式)
            if not text:
                text = data.get("text", "")
                
            # 如果还是没有，显示原始数据以便调试
            if not text:
                 text = str(data)
                 
            self.asr_result_area.setText(text)
            logger.info(f"ASR Success: {text[:50]}...")
        else:
            self.asr_result_area.setText(f"转换失败: {msg}")
            QMessageBox.critical(self, "转换失败", f"错误信息: {msg}")

    def copy_result_to_clipboard(self):
        text = self.asr_result_area.toPlainText().strip()
        if not text:
            return
            
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        
        # 显示提示并设置定时隐藏
        self.copy_tip_label.show()
        QTimer.singleShot(2000, self.copy_tip_label.hide)
        
        # 可选：显示一个小提示或改变按钮文字
        # 这里使用消息框简单处理，或者不做提示保持静默
        # logger.info("Result copied to clipboard")
        # QMessageBox.information(self, "提示", "内容已复制到剪贴板")

