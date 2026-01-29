#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/main.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 客户端入口

import sys
from PyQt5.QtWidgets import QApplication, QDialog
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from utils.config import Config
from utils.api_client import ApiClient

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(Config.APP_NAME)
    
    # 初始化配置
    backend_url = Config.get_backend_url()
    ApiClient().set_base_url(backend_url)
    
    # 自动登录检查
    settings = Config.get_settings()
    token = settings.value("auth_token")
    username = settings.value("auth_username")
    
    logged_in = False
    
    if token and username:
        # TODO: 可以在这里添加 Token 有效性验证 (调用 /users/me)
        ApiClient().set_token(token)
        logged_in = True
    
    if not logged_in:
        # 显示登录窗口
        login = LoginDialog()
        if login.exec_() == QDialog.Accepted:
            # 设置全局 Token
            ApiClient().set_token(login.token)
            token = login.token
            username = login.username
            logged_in = True
        else:
            sys.exit(0)
            
    if logged_in:
        # 显示主窗口
        window = MainWindow(token, username)
        window.show()
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()
