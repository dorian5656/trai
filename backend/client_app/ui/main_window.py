#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/client_app/ui/main_window.py
# 作者: whf
# 日期: 2026-01-29
# 描述: 主窗口 (模块化)

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget, QStackedWidget,
    QMessageBox, QLineEdit, QFormLayout, QGroupBox, QPushButton, 
    QVBoxLayout, QComboBox, QLabel, QSystemTrayIcon, QMenu, QAction, QApplication
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon
from .chat_widget import ChatWidget
from .service_widget import ServiceWidget
from .image_widget import ImageWidget
from utils.config import Config

class ConfigWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        form_group = QGroupBox("系统设置")
        form_layout = QFormLayout(form_group)
        
        self.settings = Config.get_settings()
        
        self.env_combo = QComboBox()
        self.env_combo.addItems(["Prod (正式环境)", "Dev (开发环境)"])
        self.env_combo.currentIndexChanged.connect(self.on_env_change)
        form_layout.addRow("环境选择:", self.env_combo)
        
        self.backend_url_edit = QLineEdit(Config.get_backend_url())
        form_layout.addRow("后端地址 (Backend URL):", self.backend_url_edit)
        
        self.python_path_edit = QLineEdit(Config.get_python_path())
        self.python_path_edit.setPlaceholderText("例如: conda activate xxx && python 或 绝对路径")
        form_layout.addRow("Python 解释器路径:", self.python_path_edit)
        
        current_env = int(self.settings.value("env_index", 0))
        self.env_combo.setCurrentIndex(current_env)
        
        layout.addWidget(form_group)
        
        save_btn = QPushButton("保存配置")
        save_btn.setFixedWidth(120)
        save_btn.setStyleSheet("background-color: #2ecc71; color: white; border-radius: 5px; padding: 8px;")
        save_btn.clicked.connect(self.save_config)
        layout.addWidget(save_btn, alignment=Qt.AlignRight)
        
        layout.addStretch()
        
    def on_env_change(self, index):
        if index == 0:
            self.backend_url_edit.setText(f"http://localhost:{Config.PORT_BACKEND_PROD}")
        else:
            self.backend_url_edit.setText(f"http://localhost:{Config.PORT_BACKEND_DEV}")

    def save_config(self):
        new_url = self.backend_url_edit.text().strip()
        new_python = self.python_path_edit.text().strip()
        env_index = self.env_combo.currentIndex()
        
        if not new_url:
            QMessageBox.warning(self, "错误", "后端地址不能为空")
            return
            
        self.settings.setValue("backend_url", new_url)
        self.settings.setValue("python_path", new_python)
        self.settings.setValue("env_index", env_index)
        
        QMessageBox.information(self, "成功", "配置已保存 (重启生效)")

class MainWindow(QMainWindow):
    def __init__(self, token, username):
        super().__init__()
        self.token = token
        self.username = username
        self.setWindowTitle(f"{Config.APP_NAME} - {username}")
        self.resize(1100, 750)
        
        # 初始化系统托盘
        self.init_tray()
        
        self.init_ui()

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = Config.get_resource_path("pppg.ico")
        self.tray_icon.setIcon(QIcon(icon_path)) # 尝试加载图标
        
        # 托盘菜单
        tray_menu = QMenu()
        
        show_action = QAction("显示主界面", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("退出程序", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # 双击恢复
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.activateWindow()

    def quit_app(self):
        # 真正退出
        self.service_page.close()
        QApplication.quit()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 左侧菜单区域 ===
        left_widget = QWidget()
        left_widget.setFixedWidth(200)
        left_widget.setStyleSheet("background-color: #2c3e50;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.menu_list = QListWidget()
        self.menu_list.setStyleSheet("""
            QListWidget {
                background-color: #2c3e50;
                color: white;
                border: none;
                font-size: 14px;
            }
            QListWidget::item {
                height: 50px;
                padding-left: 15px;
            }
            QListWidget::item:selected {
                background-color: #34495e;
                border-left: 4px solid #3498db;
            }
            QListWidget::item:hover {
                background-color: #34495e;
            }
        """)
        self.menu_list.addItem("🤖 AI 对话")
        self.menu_list.addItem("📷 图像识别")
        self.menu_list.addItem("🛠️ 服务管理")
        self.menu_list.addItem("⚙️ 系统配置")
        
        self.menu_list.currentRowChanged.connect(self.on_menu_change)
        
        left_layout.addWidget(self.menu_list)
        
        # 底部退出按钮
        exit_btn = QPushButton("🚪 退出登录 / 关闭")
        exit_btn.setFixedHeight(50)
        exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: white;
                border: none;
                font-size: 14px;
                text-align: left;
                padding-left: 15px;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
        """)
        exit_btn.clicked.connect(self.logout_or_quit)
        left_layout.addWidget(exit_btn)

        # === 右侧内容区 ===
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background-color: #f5f6fa;")
        
        # 1. AI 对话
        self.chat_page = ChatWidget(self.username)
        self.content_stack.addWidget(self.chat_page)
        
        # 2. 图像识别
        self.image_page = ImageWidget()
        self.content_stack.addWidget(self.image_page)
        
        # 3. 服务管理
        self.service_page = ServiceWidget()
        self.content_stack.addWidget(self.service_page)
        
        # 4. 系统配置
        self.config_page = ConfigWidget()
        self.content_stack.addWidget(self.config_page)

        # 布局组合
        main_layout.addWidget(left_widget)
        main_layout.addWidget(self.content_stack)
        
        self.menu_list.setCurrentRow(0)

    def logout_or_quit(self):
        # 询问是退出还是注销
        msg = QMessageBox()
        msg.setWindowTitle("退出")
        msg.setText("请选择操作:")
        msg.setIcon(QMessageBox.Question)
        logout_btn = msg.addButton("注销登录", QMessageBox.ActionRole)
        quit_btn = msg.addButton("彻底退出", QMessageBox.ActionRole)
        cancel_btn = msg.addButton("取消", QMessageBox.RejectRole)
        
        msg.exec_()
        
        if msg.clickedButton() == quit_btn:
            self.quit_app()
        elif msg.clickedButton() == logout_btn:
            # 清除自动登录
            settings = Config.get_settings()
            settings.remove("auth_token")
            settings.remove("auth_username")
            # 重启应用或退出 (简单起见，提示重启)
            QMessageBox.information(self, "提示", "已清除登录信息，请重启程序重新登录。")
            self.quit_app()

    def on_menu_change(self, index):
        self.content_stack.setCurrentIndex(index)
        
    def closeEvent(self, event):
        if self.tray_icon.isVisible():
            # 最小化到托盘
            self.hide()
            self.tray_icon.showMessage(
                Config.APP_NAME,
                "程序已最小化到系统托盘",
                QSystemTrayIcon.Information,
                2000
            )
            event.ignore()
        else:
            self.quit_app()
