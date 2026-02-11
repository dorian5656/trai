#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：settings_page.py
# 作者：liuhd
# 日期：2026-02-10 17:30:00
# 描述：系统设置页面，提供配置修改、版本信息和更新检测

import os
import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QMessageBox, QGroupBox,
                             QApplication)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from .config_loader import ConfigLoader

# 当前版本号
CURRENT_VERSION = "1.0.0"

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.config_loader = ConfigLoader.get_instance()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 1. 标题
        title = QLabel("⚙️ 系统设置")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # 2. 版本信息区域
        info_group = QGroupBox("关于软件")
        info_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        info_layout = QHBoxLayout(info_group)
        info_layout.setContentsMargins(20, 20, 20, 20)
        
        version_label = QLabel(f"当前版本: v{CURRENT_VERSION}")
        version_label.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(version_label)
        info_layout.addStretch()
        
        layout.addWidget(info_group)

        # 3. 配置文件编辑区域
        config_group = QGroupBox("高级配置")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(20, 20, 20, 20)

        desc_label = QLabel("警告: 修改配置文件可能导致程序运行异常，请谨慎操作。")
        desc_label.setStyleSheet("color: #e6a23c; margin-bottom: 5px;")
        config_layout.addWidget(desc_label)

        # 配置文件编辑器
        self.config_editor = QTextEdit()
        self.config_editor.setFont(QFont("Consolas", 10)) # 等宽字体
        self.config_editor.setMinimumHeight(350)
        self.config_editor.setStyleSheet("background-color: #f8f8f8; border: 1px solid #dcdfe6; border-radius: 4px;")
        config_layout.addWidget(self.config_editor)

        # 按钮栏
        btn_layout = QHBoxLayout()
        
        self.reload_btn = QPushButton("重置配置")
        self.reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_btn.clicked.connect(self.load_config_to_editor)
        self.reload_btn.setStyleSheet("""
            QPushButton {
                background-color: #f4f4f5; 
                color: #909399; 
                border: 1px solid #dcdfe6; 
                padding: 5px 10px; 
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e9e9eb; }
        """)
        
        self.last_updated_label = QLabel("")
        self.last_updated_label.setStyleSheet("color: #909399; font-size: 12px; margin-right: 10px;")
        
        self.save_btn = QPushButton("保存配置")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self.save_config)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #409eff; 
                color: white; 
                border: none; 
                padding: 5px 10px; 
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #66b1ff; }
        """)

        btn_layout.addWidget(self.reload_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.last_updated_label)
        btn_layout.addWidget(self.save_btn)
        
        config_layout.addLayout(btn_layout)
        layout.addWidget(config_group)

        # 4. 更新检测区域 (预留)
        update_group = QGroupBox("软件更新")
        update_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        update_layout = QHBoxLayout(update_group)
        update_layout.setContentsMargins(20, 20, 20, 20)

        self.check_update_btn = QPushButton("检查更新")
        self.check_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_update_btn.clicked.connect(self.check_update)
        self.check_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #67c23a; 
                color: white; 
                border: none; 
                padding: 5px 10px; 
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #85ce61; }
        """)
        
        self.update_status_label = QLabel("当前已是最新版本")
        self.update_status_label.setStyleSheet("color: #606266; margin-left: 10px;")
        
        update_layout.addWidget(self.check_update_btn)
        update_layout.addWidget(self.update_status_label)
        update_layout.addStretch()
        
        layout.addWidget(update_group)
        
        # 初始化加载配置（需在UI组件创建完成后调用）
        self.load_config_to_editor()

        layout.addStretch() # 底部弹簧

    def update_last_modified_time(self):
        """更新最后修改时间显示"""
        path = self.config_loader.config_path
        if path and os.path.exists(path):
            try:
                ts = os.path.getmtime(path)
                dt = datetime.datetime.fromtimestamp(ts)
                self.last_updated_label.setText(f"最后更新: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception:
                self.last_updated_label.setText("")
        else:
            self.last_updated_label.setText("")

    def load_config_to_editor(self):
        """加载配置到编辑器"""
        # 重新从文件加载
        self.config_loader.reload()
        text = self.config_loader.get_config_text()
        self.config_editor.setPlainText(text)
        self.update_last_modified_time()

    def save_config(self):
        """保存配置"""
        text = self.config_editor.toPlainText()
        success, msg = self.config_loader.save_config(text)
        
        if success:
            self.update_last_modified_time()
            QMessageBox.information(self, "成功", "配置已保存。")
        else:
            QMessageBox.critical(self, "错误", f"保存失败: {msg}")

    def check_update(self):
        """检查更新 (模拟)"""
        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText("正在检查...")
        self.update_status_label.setText("正在连接服务器...")
        
        # 模拟延时
        QTimer.singleShot(2000, self.finish_check_update)

    def finish_check_update(self):
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText("检查更新")
        self.update_status_label.setText(f"当前版本 v{CURRENT_VERSION} 已是最新")
        QMessageBox.information(self, "检查更新", "当前已是最新版本！")
