#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：rrdsppg_page.py
# 作者：liuhd
# 日期：2026-02-06 11:55:00
# 描述：RRDSPPG 测试工具 (PyQt6 GUI版)

import os
import requests
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QFileDialog, QComboBox, QTextEdit,
    QProgressBar, QFrame, QDialog, QScrollArea,
    QMessageBox, QCheckBox, QApplication
)
from PyQt6.QtGui import (
    QPixmap, QRegularExpressionValidator, 
    QCursor
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QRegularExpression
)
import threading
from .config_loader import config

class OCRWorker(QThread):
    """OCR处理线程"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, params, token="", api_url=None):
        super().__init__()
        self.params = params
        self.token = token
        self.api_url = api_url or config["rrdsppg"]["api_url"]
    
    def run(self):
        try:
            self.progress.emit(20)
            # 发送请求到API
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            # 使用 multipart/form-data
            # 注意：requests 会自动设置 Content-Type 为 multipart/form-data; boundary=...
            files = {'file': ('', b'')} 
            response = requests.post(self.api_url, data=self.params, files=files, headers=headers, timeout=30)
            self.progress.emit(80)
            
            if response.status_code == 200:
                result = response.json()
                self.finished.emit(result)
            else:
                self.error.emit(f"API请求失败，状态码: {response.status_code}")
        except Exception as e:
            self.error.emit(f"请求异常: {str(e)}")
        finally:
            self.progress.emit(100)

class ImageViewerDialog(QDialog):
    """图片查看器弹窗"""
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片预览")
        self.resize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        
        layout = QVBoxLayout(self)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setPixmap(pixmap)
        self.scroll_area.setWidget(self.image_label)
        
        layout.addWidget(self.scroll_area)

class ImagePreview(QWidget):
    """图片预览组件"""
    preview_signal = pyqtSignal(QPixmap)
    error_signal = pyqtSignal(str)

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout()
        self.title_label = QLabel(title)
        self.image_label = QLabel("支持拖拽图片到此处\n或点击选择图片") 
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(300, 200)
        self.image_label.setStyleSheet("border: 2px dashed #CCCCCC; font-size: 14px; color: #999999;")
        
        # 将 image_label 设置为可点击
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.path_label = QLabel("无图片")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("font-size: 10px; color: #666666;")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        # 添加URL输入框
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("输入图片URL")
        self.url_button = QPushButton("使用URL")
        
        # 连接 URL 输入框的变化信号
        self.url_edit.textChanged.connect(self.on_url_changed)
        self.url_button.clicked.connect(self.on_url_button_clicked)
        
        url_layout = QHBoxLayout()
        url_layout.addWidget(self.url_edit)
        url_layout.addWidget(self.url_button)
        
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.path_label)
        self.layout.addLayout(url_layout)
        self.setLayout(self.layout)
        
        # 启用拖拽
        self.setAcceptDrops(True)
        
        # 信号连接
        self.preview_signal.connect(self.update_preview_pixmap)
        self.error_signal.connect(self.show_preview_error)
        
        self.is_url_mode = False # 标记当前是否为 URL 模式

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def mousePressEvent(self, event):
        # 只有点击图片区域且不是 URL 模式时才触发文件选择
        if event.button() == Qt.MouseButton.LeftButton and self.image_label.geometry().contains(event.pos()) and not self.is_url_mode:
            self.select_local_image()
        super().mousePressEvent(event)

    def select_local_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Image Files (*.png *.jpg *.jpeg)"
        )
        if file_path:
            self.set_image(file_path)

    def on_url_changed(self, text):
        # 当输入 URL 时，如果内容不为空，则进入 URL 模式
        if text.strip():
            self.is_url_mode = True
            self.image_label.setText("URL预览模式\n点击'使用URL'加载")
            self.image_label.setStyleSheet("border: 2px solid #CCCCCC; font-size: 14px; color: #999999; background-color: #F0F0F0;") 
            self.path_label.setText("使用 URL")
        else:
            self.is_url_mode = False
            self.image_label.setText("支持拖拽图片到此处\n或点击选择图片")
            self.image_label.setStyleSheet("border: 2px dashed #CCCCCC; font-size: 14px; color: #999999;")
            self.path_label.setText("无图片")
            self.image_label.clear()
            self.image_label.setText("支持拖拽图片到此处\n或点击选择图片") # clear后重置文字

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path) and file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                self.set_image(file_path)
                break

    def update_preview_pixmap(self, pixmap):
        self.current_pixmap = pixmap # 保存原始图片
        scaled_pixmap = pixmap.scaled(
            self.image_label.width(), self.image_label.height(), 
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def show_preview_error(self, error_msg):
        self.image_label.setText(error_msg)

    def on_url_button_clicked(self):
        url = self.url_edit.text().strip()
        if url:
            self.set_image(url)

    def set_image(self, image_path):
        """设置图片"""
        # 检查是否是HTTP URL
        if image_path.startswith('http://') or image_path.startswith('https://'):
            self.is_url_mode = True
            self.path_label.setText(image_path)
            self.image_label.setText("正在加载预览...")
            threading.Thread(target=self.download_and_preview, args=(image_path,), daemon=True).start()
            return image_path
        
        # 对于本地文件，尝试加载并显示
        if os.path.exists(image_path):
            self.is_url_mode = False
            pixmap = QPixmap(image_path)
            self.update_preview_pixmap(pixmap)
            self.path_label.setText(image_path)
            
            self.url_edit.clear()
            self.url_edit.setEnabled(False) 
            self.url_edit.setPlaceholderText("已选择本地图片 (拖拽替换)")
            self.url_button.setEnabled(False)
            
            return image_path
        return None
    
    def reset_state(self):
        """重置状态"""
        self.current_pixmap = None
        self.image_label.clear()
        self.image_label.setText("支持拖拽图片到此处\n或点击选择图片")
        self.image_label.setStyleSheet("border: 2px dashed #CCCCCC; font-size: 14px; color: #999999;")
        self.path_label.setText("无图片")
        self.url_edit.clear()
        self.url_edit.setEnabled(True)
        self.url_button.setEnabled(True)
        self.url_edit.setPlaceholderText("输入图片URL")
        self.is_url_mode = False

    def download_and_preview(self, url):
        """下载并预览图片"""
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                image_data = resp.content
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                self.preview_signal.emit(pixmap)
            else:
                self.error_signal.emit(f"预览失败: {resp.status_code}")
        except Exception as e:
            self.error_signal.emit(f"预览出错: {str(e)}")
    
    def get_image_path(self):
        """获取当前设置的图片路径或URL"""
        if self.url_edit.text().strip():
            return self.url_edit.text().strip()
        path = self.path_label.text()
        if path != "无图片" and path != "URL图片预览":
            return path
        return None

class RrdsppgPage(QWidget):
    """人人都是品牌官-OCR工具页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.token = ""
        # 初始化UI
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("人人都是品牌官-测试工具")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title_label)
        
        # 图片上传区域
        image_section = QFrame()
        image_section.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        image_layout = QHBoxLayout(image_section)
        
        # 模板图片预览
        self.template_preview = ImagePreview("模板图片")
        
        # 目标图片预览
        self.target_preview = ImagePreview("目标图片")
        
        # 设置默认URL
        template_url = config["rrdsppg"].get("template_url", "")
        target_url = config["rrdsppg"].get("target_url", "")
        if template_url:
            self.template_preview.url_edit.setText(template_url)
        if target_url:
            self.target_preview.url_edit.setText(target_url)
        
        # 添加到布局
        template_layout = QVBoxLayout()
        template_layout.addWidget(self.template_preview)
        
        target_layout = QVBoxLayout()
        target_layout.addWidget(self.target_preview)
        
        image_layout.addLayout(template_layout)
        image_layout.addLayout(target_layout)
        main_layout.addWidget(image_section)
        
        # 参数设置区域
        params_section = QFrame()
        params_section.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        params_layout = QVBoxLayout(params_section)
        
        params_title = QLabel("参数设置")
        params_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        params_layout.addWidget(params_title)
        
        # 表单布局
        form_layout = QVBoxLayout()
        
        # Task ID
        task_layout = QHBoxLayout()
        task_label = QLabel("Task ID:")
        self.task_id_edit = QLineEdit()
        self.task_id_edit.setText(config["rrdsppg"].get("task_id", ""))
        id_validator = QRegularExpressionValidator(QRegularExpression("^[0-9]{1,25}$"))
        self.task_id_edit.setValidator(id_validator)
        
        task_layout.addWidget(task_label)
        task_layout.addWidget(self.task_id_edit)
        form_layout.addLayout(task_layout)
        
        # User ID
        user_layout = QHBoxLayout()
        user_label = QLabel("User ID:")
        self.user_id_edit = QLineEdit()
        self.user_id_edit.setText(config["rrdsppg"].get("user_id", ""))
        self.user_id_edit.setValidator(id_validator)
        
        user_layout.addWidget(user_label)
        user_layout.addWidget(self.user_id_edit)
        form_layout.addLayout(user_layout)
        
        # Type选择
        type_layout = QHBoxLayout()
        type_label = QLabel("Type:")
        
        type_hint = QLabel("(请先选择任务类型)")
        type_hint.setStyleSheet("color: red; font-size: 12px; font-weight: bold; margin-right: 10px;")
        
        self.type_combo = QComboBox()
        self.type_combo.setMinimumHeight(35)
        self.type_combo.setStyleSheet("""
            QComboBox { font-size: 14px; padding: 5px; }
            QComboBox QAbstractItemView::item { min-height: 35px; }
        """)
        self.type_combo.addItem("视频号", config["rrdsppg"].get("type_video", ""))
        self.type_combo.addItem("公众号转发", config["rrdsppg"].get("type_public", ""))
        
        type_layout.addWidget(type_label)
        type_layout.addWidget(type_hint)
        type_layout.addWidget(self.type_combo)
        
        form_layout.addLayout(type_layout)

        # itzx复选框
        itzx_layout = QHBoxLayout()
        self.itzx_checkbox = QCheckBox("启用 itzx (返回多个值)")
        self.itzx_checkbox.setChecked(False)
        itzx_layout.addWidget(self.itzx_checkbox)
        form_layout.addLayout(itzx_layout)
        
        params_layout.addLayout(form_layout)
        main_layout.addWidget(params_section)
        
        # API地址显示
        api_layout = QHBoxLayout()
        api_label = QLabel("API地址:")
        self.api_edit = QLineEdit()
        self.api_edit.setText(config["rrdsppg"]["api_url"])
        # self.api_edit.setReadOnly(True)
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_edit)
        main_layout.addLayout(api_layout)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        self.run_button = QPushButton("开始识别")
        self.run_button.setMinimumHeight(40)
        self.run_button.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.run_button.clicked.connect(self.run_ocr)
        
        self.clear_button = QPushButton("清空")
        self.clear_button.setMinimumHeight(40)
        self.clear_button.setStyleSheet("background-color: #FF4444; color: white; font-weight: bold; font-size: 14px;")
        self.clear_button.clicked.connect(self.clear_all)
        
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.clear_button)
        main_layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 结果显示区域
        result_section = QFrame()
        result_section.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        result_layout = QVBoxLayout(result_section)
        
        result_header_layout = QHBoxLayout()
        result_title = QLabel("识别结果")
        result_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        copy_result_btn = QPushButton("复制结果")
        copy_result_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        copy_result_btn.clicked.connect(self.copy_result)
        
        result_header_layout.addWidget(result_title)
        result_header_layout.addStretch()
        result_header_layout.addWidget(copy_result_btn)
        
        result_layout.addLayout(result_header_layout)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("""
            QScrollBar:vertical {
                width: 30px;
            }
        """)
        result_layout.addWidget(self.result_text)
        
        main_layout.addWidget(result_section)
        
        # 状态显示 (替代 StatusBar)
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: gray; font-size: 12px; margin-top: 5px;")
        main_layout.addWidget(self.status_label)

    def copy_result(self):
        """复制识别结果"""
        text = self.result_text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.show_message("结果已复制到剪贴板")
    
    def run_ocr(self):
        """运行OCR识别"""
        template_path = self.template_preview.get_image_path()
        target_path = self.target_preview.get_image_path()
        
        if not template_path:
            self.show_message("请选择模板图片或输入URL")
            return
        if not target_path:
            self.show_message("请选择目标图片或输入URL")
            return
        
        # 确保 temp/web_upload 目录存在
        upload_dir = os.path.join(os.getcwd(), "temp", "web_upload")
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        params = {
            "templatePath": template_path,
            "targetPath": target_path,
            "taskId": self.task_id_edit.text(),
            "userId": self.user_id_edit.text(),
            "type": self.type_combo.currentData(),
            "itzx": 1 if self.itzx_checkbox.isChecked() else 0
        }
        
        print(f"使用模板图片: {params['templatePath']}")
        print(f"使用目标图片: {params['targetPath']}")
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.run_button.setEnabled(False)
        
        current_api_url = self.api_edit.text().strip()
        self.worker = OCRWorker(params, self.token, api_url=current_api_url)
        self.worker.finished.connect(self.on_ocr_finished)
        self.worker.error.connect(self.on_ocr_error)
        self.worker.progress.connect(self.update_progress)
        self.worker.start()
    
    def on_ocr_finished(self, result):
        self.progress_bar.setValue(100)
        self.run_button.setEnabled(True)
        self.result_text.setText(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("code") == 200:
            self.show_message("识别成功！")
        else:
            self.show_message(f"识别失败: {result.get('msg', '未知错误')}")
    
    def on_ocr_error(self, error_msg):
        self.progress_bar.setValue(100)
        self.run_button.setEnabled(True)
        self.show_message(f"错误: {error_msg}")
        self.result_text.setText(f"错误: {error_msg}")
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def clear_all(self):
        self.template_preview.reset_state()
        self.target_preview.reset_state()
        self.result_text.clear()
        self.progress_bar.setVisible(False)
    
    def show_message(self, message):
        self.status_label.setText(message)
        print(message)
    
    def set_auth_token(self, token):
        """设置认证Token"""
        self.token = token
