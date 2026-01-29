#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/ui/login_dialog.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 登录对话框

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QFormLayout, QLineEdit, 
    QDialogButtonBox, QMessageBox
)
from logic.auth_manager import AuthManager
from utils.config import Config

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录 - Trae AI Assistant")
        self.setFixedSize(400, 250)
        self.token = None
        self.username = None
        
        layout = QVBoxLayout(self)
        
        # 表单
        form_group = QGroupBox("用户登录")
        form_layout = QFormLayout(form_group)
        
        self.username_edit = QLineEdit(Config.DEFAULT_USERNAME)
        self.username_edit.setPlaceholderText("用户名")
        form_layout.addRow("用户名:", self.username_edit)
        
        self.password_edit = QLineEdit(Config.DEFAULT_PASSWORD)
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("密码")
        form_layout.addRow("密码:", self.password_edit)
        
        layout.addWidget(form_group)
        
        # 按钮
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.handle_login)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
    def handle_login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "错误", "用户名和密码不能为空")
            return
            
        success, token, msg = AuthManager.login(username, password)
        
        if success:
            self.token = token
            self.username = username
            
            # 保存自动登录信息
            settings = Config.get_settings()
            settings.setValue("auth_token", token)
            settings.setValue("auth_username", username)
            
            QMessageBox.information(self, "成功", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "登录失败", msg)
