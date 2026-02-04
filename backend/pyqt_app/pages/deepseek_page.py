#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：deepseek_page.py
# 作者：liuhd
# 日期：2026-02-04 16:29:00
# 描述：DeepSeek对话功能页面

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QListWidget, QListWidgetItem, 
                             QFrame, QScrollArea, QSizePolicy, QGridLayout, QTextEdit, QMessageBox)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QFont
import requests

class DeepSeekPage(QWidget):
    def __init__(self):
        super().__init__()
        self.auth_token = ""
        self.init_ui()

    def init_ui(self):
        # 主布局：水平布局，左侧历史记录，右侧对话区域
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 左侧侧边栏 (历史记录)
        self.left_sidebar = QWidget()
        self.left_sidebar.setObjectName("chatSidebar")
        self.left_sidebar.setFixedWidth(260)
        self.left_sidebar.setStyleSheet("""
            QWidget#chatSidebar {
                background-color: #f7f7f8;
                border-right: 1px solid #e5e5e5;
            }
        """)
        
        left_layout = QVBoxLayout(self.left_sidebar)
        left_layout.setContentsMargins(15, 20, 15, 20)
        left_layout.setSpacing(15)

        # 新对话按钮
        self.new_chat_btn = QPushButton("  +  新对话")
        self.new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_btn.setFixedHeight(45)
        self.new_chat_btn.setStyleSheet("""
            QPushButton {
                background-color: #e3f2fd;
                color: #2196f3;
                border: 1px solid #bbdefb;
                border-radius: 8px;
                font-weight: bold;
                text-align: left;
                padding-left: 20px;
            }
            QPushButton:hover {
                background-color: #bbdefb;
            }
        """)
        left_layout.addWidget(self.new_chat_btn)

        # 最近对话标签
        recent_label = QLabel("最近对话")
        recent_label.setStyleSheet("color: #999; font-size: 12px; margin-top: 10px;")
        left_layout.addWidget(recent_label)

        # 历史记录列表
        self.history_list = QListWidget()
        self.history_list.setFrameShape(QFrame.Shape.NoFrame)
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 6px;
                color: #333;
                margin-bottom: 5px;
            }
            QListWidget::item:hover {
                background-color: #eaeaea;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #2196f3;
            }
        """)
        
        # 模拟数据
        # for i in range(5):
        #     item = QListWidgetItem(f"新对话 {i+1}")
        #     self.history_list.addItem(item)
            
        left_layout.addWidget(self.history_list)
        
        # 底部用户信息区域 (占位)
        # user_area = QLabel("用户设置")
        # left_layout.addWidget(user_area)

        main_layout.addWidget(self.left_sidebar)

        # 2. 右侧对话主区域
        self.right_content = QWidget()
        self.right_content.setStyleSheet("background-color: #ffffff;")
        right_layout = QVBoxLayout(self.right_content)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 顶部工具栏 (用于折叠侧边栏)
        header = QWidget()
        header.setFixedHeight(50)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        self.toggle_btn = QPushButton("◀")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setToolTip("折叠/展开侧边栏")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                color: #666;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #2196f3;
                background-color: #f0f0f0;
                border-radius: 5px;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_left_sidebar)
        
        header_layout.addWidget(self.toggle_btn)
        header_layout.addStretch()
        
        right_layout.addWidget(header)

        # 中间内容区域 (使用弹性布局居中显示欢迎页)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setSpacing(30)
        
        # 欢迎标题
        welcome_label = QLabel("你好，我是驼人GPT")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #333;")
        center_layout.addWidget(welcome_label)
        
        # 输入框容器
        input_container = QFrame()
        input_container.setFixedWidth(700)
        input_container.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e5e5e5;
                border-radius: 12px;
            }
            QFrame:hover {
                border: 1px solid #ccc;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
        """)
        # 添加阴影效果
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 20))
        input_container.setGraphicsEffect(shadow)
        
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(15, 15, 15, 10)
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("发送消息 or 输入“/”选择技能")
        self.chat_input.setFrame(False)
        self.chat_input.setFixedHeight(40)
        self.chat_input.setStyleSheet("font-size: 16px; border: none; background: transparent;")
        input_layout.addWidget(self.chat_input)
        
        # 输入框底部工具栏
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(15)
        
        # 左侧图标 (附件、网络)
        icon_btn_style = """
            QPushButton {
                border: none;
                background: transparent;
                color: #999;
                font-size: 18px;
                font-family: "Segoe UI Emoji","Segoe UI Symbol","Microsoft YaHei",sans-serif;
            }
            QPushButton:hover {
                color: #666;
            }
        """
        attach_btn = QPushButton("📎")
        attach_btn.setToolTip("上传附件")
        attach_btn.setStyleSheet(icon_btn_style)
        
        web_btn = QPushButton("🌐") # 占位图标
        web_btn.setToolTip("联网搜索")
        web_btn.setStyleSheet(icon_btn_style)
        
        tools_layout.addWidget(attach_btn)
        tools_layout.addWidget(web_btn)
        tools_layout.addStretch()
        
        # 右侧图标 (语音、发送)
        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setStyleSheet(icon_btn_style)
        
        self.send_btn = QPushButton("↑")
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setEnabled(False)
        self.send_btn.setStyleSheet("QPushButton { background-color: #e5e5e5; color: #ffffff; border-radius: 16px; font-weight: bold; font-size: 16px; padding-bottom: 3px; }")
        
        tools_layout.addWidget(self.voice_btn)
        tools_layout.addWidget(self.send_btn)
        self.send_btn.clicked.connect(self.send_message)
        self.chat_input.textChanged.connect(self.update_send_btn_state)
        self.update_send_btn_state(self.chat_input.text())
        
        input_layout.addLayout(tools_layout)
        center_layout.addWidget(input_container)
        
        self.reply_view = QTextEdit()
        self.reply_view.setReadOnly(True)
        self.reply_view.setFixedWidth(700)
        self.reply_view.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 10px; font-size: 14px; color: #333;")
        self.reply_view.hide()
        center_layout.addWidget(self.reply_view)
        
        # 快捷功能按钮区
        features_widget = QWidget()
        features_layout = QHBoxLayout(features_widget)
        features_layout.setSpacing(15)
        features_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        features = [
            ("🖼️ 图像生成", "image_gen"),
            ("📝 会议记录", "meeting_note"),
            ("✍️ 帮你写作", "writing"),
            ("🌐 翻译", "translation"),
            ("📊 数据分析", "data_analysis"),
            ("🧰 更多", "more")
        ]
        
        for text, _ in features:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f7f7f8;
                    border: 1px solid #e5e5e5;
                    border-radius: 15px;
                    padding: 8px 16px;
                    color: #666;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #ffffff;
                    border-color: #d0d0d0;
                }
            """)
            features_layout.addWidget(btn)
            
        center_layout.addWidget(features_widget)
        
        # 版权/关于信息
        # footer_label = QLabel("关于驼人GPT")
        # footer_label.setStyleSheet("color: #ccc; font-size: 12px;")
        # center_layout.addWidget(footer_label, 0, Qt.AlignmentFlag.AlignCenter)

        right_layout.addWidget(center_widget)
        main_layout.addWidget(self.right_content)

    def toggle_left_sidebar(self):
        width = self.left_sidebar.width()
        # 目标宽度: 如果当前是260则变0，否则变260
        if width > 0:
            target_width = 0
            self.toggle_btn.setText("▶")
        else:
            target_width = 260
            self.toggle_btn.setText("◀")
            
        self.anim = QPropertyAnimation(self.left_sidebar, b"minimumWidth")
        self.anim.setDuration(300)
        self.anim.setStartValue(width)
        self.anim.setEndValue(target_width)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
        
        # 同时还需要设置maximumWidth，否则布局可能不会如预期收缩
        self.anim_max = QPropertyAnimation(self.left_sidebar, b"maximumWidth")
        self.anim_max.setDuration(300)
        self.anim_max.setStartValue(width)
        self.anim_max.setEndValue(target_width)
        self.anim_max.setEasingCurve(QEasingCurve.Type.InOutQuart)
        
        self.anim.start()
        self.anim_max.start()

    def set_auth_token(self, token: str):
        self.auth_token = token or ""
    
    def _on_chat_finished(self, ok: bool, msg: str, reply: str):
        if not ok:
            QMessageBox.warning(self, "失败", msg)
            return
        self.reply_view.setText(reply)
        self.reply_view.show()
    
    def send_message(self):
        content = self.chat_input.text().strip()
        if not content:
            QMessageBox.warning(self, "提示", "请输入内容")
            return
        if not self.auth_token:
            QMessageBox.warning(self, "提示", "请先登录")
            return
        self.chat_input.setEnabled(False)
        self.toggle_btn.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.worker = ChatWorker(self.auth_token, content)
        self.worker.finished_signal.connect(self._on_chat_finished)
        self.worker.finished_signal.connect(self._on_chat_done)
        self.worker.start()
    
    def update_send_btn_state(self, text: str):
        t = (text or "").strip()
        if t:
            self.send_btn.setEnabled(True)
            self.send_btn.setStyleSheet("QPushButton { background-color: #2196f3; color: #ffffff; border-radius: 16px; font-weight: bold; font-size: 16px; padding-bottom: 3px; } QPushButton:hover { background-color: #1976D2; }")
        else:
            self.send_btn.setEnabled(False)
            self.send_btn.setStyleSheet("QPushButton { background-color: #e5e5e5; color: #ffffff; border-radius: 16px; font-weight: bold; font-size: 16px; padding-bottom: 3px; }")
    
    def _on_chat_done(self, *args):
        self.chat_input.setEnabled(True)
        self.toggle_btn.setEnabled(True)
        self.update_send_btn_state(self.chat_input.text())
        self.send_btn.setEnabled(True)

class ChatWorker(QThread):
    finished_signal = pyqtSignal(bool, str, str)
    def __init__(self, token: str, content: str):
        super().__init__()
        self.token = token
        self.content = content
    def run(self):
        url = "http://192.168.100.119:5778/api_trai/v1/ai/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": self.content}
            ],
            "temperature": 0.7
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=100)
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("data", {}).get("reply", "")
                self.finished_signal.emit(True, "OK", reply)
            else:
                try:
                    err = resp.json().get("detail", f"HTTP {resp.status_code}")
                except:
                    err = f"HTTP {resp.status_code}"
                self.finished_signal.emit(False, err, "")
        except requests.exceptions.ConnectionError:
            self.finished_signal.emit(False, "连接服务器失败，请检查网络或服务状态", "")
        except Exception as e:
            self.finished_signal.emit(False, str(e), "")
