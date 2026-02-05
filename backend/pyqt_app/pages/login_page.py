#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：login_page.py
# 作者：liuhd
# 日期：2026-02-04 10:00:00
# 描述：登录/注册页面

import requests
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox, QFrame, QStackedWidget, QGraphicsDropShadowEffect)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class LoginWorker(QThread):
    finished_signal = pyqtSignal(bool, str, dict)

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        url = "http://192.168.100.119:5777/api_trai/v1/auth/login/json"
        headers = {"Content-Type": "application/json"}
        data = {"username": self.username, "password": self.password}

        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            if response.status_code == 200:
                result = response.json()
                self.finished_signal.emit(True, "登录成功", result)
            else:
                try:
                    error_msg = response.json().get("detail", "登录失败")
                except:
                    error_msg = f"登录失败: {response.status_code}"
                self.finished_signal.emit(False, error_msg, {})
        except requests.exceptions.ConnectionError:
            self.finished_signal.emit(False, "连接服务器失败，请检查网络或服务状态", {})
        except Exception as e:
            self.finished_signal.emit(False, f"发生错误: {str(e)}", {})

class RegisterWorker(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, username, password, full_name, email, phone):
        super().__init__()
        self.username = username
        self.password = password
        self.full_name = full_name
        self.email = email
        self.phone = phone

    def run(self):
        url = "http://192.168.100.119:5777/api_trai/v1/auth/register"
        headers = {"Content-Type": "application/json"}
        data = {
            "username": self.username,
            "password": self.password,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone
        }

        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            if response.status_code == 200:
                result = response.json()
                msg = result.get("msg", "注册成功，请等待管理员审核")
                self.finished_signal.emit(True, msg)
            else:
                try:
                    error_msg = response.json().get("detail", "注册失败")
                except:
                    error_msg = f"注册失败: {response.status_code}"
                self.finished_signal.emit(False, error_msg)
        except requests.exceptions.ConnectionError:
            self.finished_signal.emit(False, "连接服务器失败，请检查网络或服务状态")
        except Exception as e:
            self.finished_signal.emit(False, f"发生错误: {str(e)}")

class LoginPage(QWidget):
    login_success = pyqtSignal(dict)  # 登录成功信号，传递用户信息

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 添加顶部弹簧
        main_layout.addStretch()

        # 堆叠窗口，用于切换登录和注册
        self.stacked_widget = QStackedWidget()
        # 由于注册页面变宽了，需要增加宽度，但登录页面不需要那么宽
        # 不过为了切换平滑，可以统一宽度或者根据内容调整
        # 这里设置为自适应，给一个最小宽度
        self.stacked_widget.setMinimumWidth(400)
        # self.stacked_widget.setFixedWidth(400) # 取消固定宽度
        
        # 初始化登录和注册界面
        self.login_widget = self.create_login_widget()
        self.register_widget = self.create_register_widget()
        
        self.stacked_widget.addWidget(self.login_widget)
        self.stacked_widget.addWidget(self.register_widget)
        
        # 居中添加堆叠窗口
        # 为了防止注册页面过宽，可以包裹在一个固定宽度的容器中，或者直接设置stacked_widget最大宽度
        self.stacked_widget.setMaximumWidth(600)

        main_layout.addWidget(self.stacked_widget, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 添加底部弹簧
        main_layout.addStretch()

    def create_container_style(self):
        return """
            QFrame {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #f0f0f0;
            }
        """

    def create_input_style(self):
        return """
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 0 10px;
                background-color: #fafafa;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #2196F3;
                background-color: #ffffff;
            }
        """

    def create_btn_style(self, color="#2196F3", hover_color="#1976D2"):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """

    def add_shadow(self, widget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 30))
        widget.setGraphicsEffect(shadow)

    def create_login_widget(self):
        container = QFrame()
        container.setStyleSheet(self.create_container_style())
        self.add_shadow(container)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(25)
        layout.setContentsMargins(50, 50, 50, 50)

        # 标题
        title = QLabel("用户登录")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #333; border: none; margin-bottom: 10px;")
        layout.addWidget(title)

        # 输入框
        self.login_user_input = QLineEdit()
        self.login_user_input.setPlaceholderText("用户名")
        self.login_user_input.setFixedHeight(40)
        self.login_user_input.setStyleSheet(self.create_input_style())
        layout.addWidget(self.login_user_input)

        self.login_pass_input = QLineEdit()
        self.login_pass_input.setPlaceholderText("密码")
        self.login_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_pass_input.setFixedHeight(40)
        self.login_pass_input.setStyleSheet(self.create_input_style())
        layout.addWidget(self.login_pass_input)

        # 预填充默认账号密码 (调试用)
        self.login_user_input.setText("A6666")
        self.login_pass_input.setText("123456")

        # 按钮
        btn_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("登录")
        self.login_btn.setFixedHeight(40)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setStyleSheet(self.create_btn_style())
        self.login_btn.clicked.connect(self.handle_login)
        
        self.to_register_btn = QPushButton("去注册")
        self.to_register_btn.setFixedHeight(40)
        self.to_register_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.to_register_btn.setStyleSheet(self.create_btn_style(color="#4CAF50", hover_color="#388E3C"))
        self.to_register_btn.clicked.connect(self.show_register)

        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.to_register_btn)
        layout.addLayout(btn_layout)

        return container

    def create_register_widget(self):
        container = QFrame()
        container.setStyleSheet(self.create_container_style())
        self.add_shadow(container)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        # 标题
        title = QLabel("用户注册")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #333; border: none; margin-bottom: 10px;")
        layout.addWidget(title)

        # 表单区域 - 使用水平布局分为两列
        form_layout = QHBoxLayout()
        form_layout.setSpacing(20)

        # 左列：账号信息
        left_col = QVBoxLayout()
        left_col.setSpacing(15)

        self.reg_user_input = QLineEdit()
        self.reg_user_input.setPlaceholderText("用户名")
        self.reg_user_input.setFixedHeight(40)
        self.reg_user_input.setStyleSheet(self.create_input_style())
        left_col.addWidget(self.reg_user_input)

        self.reg_pass_input = QLineEdit()
        self.reg_pass_input.setPlaceholderText("密码")
        self.reg_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.reg_pass_input.setFixedHeight(40)
        self.reg_pass_input.setStyleSheet(self.create_input_style())
        left_col.addWidget(self.reg_pass_input)
        
        self.reg_confirm_input = QLineEdit()
        self.reg_confirm_input.setPlaceholderText("确认密码")
        self.reg_confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.reg_confirm_input.setFixedHeight(40)
        self.reg_confirm_input.setStyleSheet(self.create_input_style())
        left_col.addWidget(self.reg_confirm_input)

        form_layout.addLayout(left_col)

        # 右列：个人信息
        right_col = QVBoxLayout()
        right_col.setSpacing(15)

        self.reg_fullname_input = QLineEdit()
        self.reg_fullname_input.setPlaceholderText("姓名")
        self.reg_fullname_input.setFixedHeight(40)
        self.reg_fullname_input.setStyleSheet(self.create_input_style())
        right_col.addWidget(self.reg_fullname_input)

        self.reg_email_input = QLineEdit()
        self.reg_email_input.setPlaceholderText("邮箱")
        self.reg_email_input.setFixedHeight(40)
        self.reg_email_input.setStyleSheet(self.create_input_style())
        right_col.addWidget(self.reg_email_input)

        self.reg_phone_input = QLineEdit()
        self.reg_phone_input.setPlaceholderText("电话")
        self.reg_phone_input.setFixedHeight(40)
        self.reg_phone_input.setStyleSheet(self.create_input_style())
        right_col.addWidget(self.reg_phone_input)

        form_layout.addLayout(right_col)
        
        layout.addLayout(form_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 10, 0, 0)
        
        self.register_btn = QPushButton("注册")
        self.register_btn.setFixedHeight(45)
        self.register_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.register_btn.setStyleSheet(self.create_btn_style(color="#4CAF50", hover_color="#388E3C"))
        self.register_btn.clicked.connect(self.handle_register)
        
        self.back_login_btn = QPushButton("返回登录")
        self.back_login_btn.setFixedHeight(45)
        self.back_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_login_btn.setStyleSheet(self.create_btn_style(color="#9E9E9E", hover_color="#757575"))
        self.back_login_btn.clicked.connect(self.show_login)

        btn_layout.addWidget(self.register_btn)
        btn_layout.addWidget(self.back_login_btn)
        layout.addLayout(btn_layout)

        return container

    def show_register(self):
        self.stacked_widget.setCurrentWidget(self.register_widget)

    def show_login(self):
        self.stacked_widget.setCurrentWidget(self.login_widget)

    def handle_login(self):
        username = self.login_user_input.text().strip()
        password = self.login_pass_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return
            
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中...")
        
        self.login_worker = LoginWorker(username, password)
        self.login_worker.finished_signal.connect(self.on_login_finished)
        self.login_worker.start()

    def on_login_finished(self, success, message, data):
        self.login_btn.setEnabled(True)
        self.login_btn.setText("登录")
        
        if success:
            token = data.get("access_token", "") or data.get("data", {}).get("access_token", "")
            QMessageBox.information(self, "成功", "登录成功！")
            self.login_success.emit({"access_token": token})
        else:
            QMessageBox.warning(self, "失败", message)

    def handle_register(self):
        username = self.reg_user_input.text().strip()
        password = self.reg_pass_input.text().strip()
        confirm = self.reg_confirm_input.text().strip()
        full_name = self.reg_fullname_input.text().strip()
        email = self.reg_email_input.text().strip()
        phone = self.reg_phone_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return
            
        if password != confirm:
            QMessageBox.warning(self, "提示", "两次输入的密码不一致")
            return

        self.register_btn.setEnabled(False)
        self.register_btn.setText("注册中...")
        
        self.reg_worker = RegisterWorker(username, password, full_name, email, phone)
        self.reg_worker.finished_signal.connect(self.on_register_finished)
        self.reg_worker.start()

    def on_register_finished(self, success, message):
        self.register_btn.setEnabled(True)
        self.register_btn.setText("注册")
        
        if success:
            QMessageBox.information(self, "成功", message)
            self.show_login()
        else:
            QMessageBox.warning(self, "失败", message)
