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
                             QApplication, QLineEdit, QFormLayout)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QFont
from .config_loader import ConfigLoader
import re
import json
import copy

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
        config_group = QGroupBox("服务器配置")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(20, 20, 20, 20)

        desc_label = QLabel("提示: 修改服务器地址后，系统将自动更新相关接口配置。配置修改保存后即时生效，无需重启。")
        desc_label.setStyleSheet("color: #e6a23c; margin-bottom: 15px;")
        config_layout.addWidget(desc_label)

        # 表单布局
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # IP 输入框
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("例如: 192.168.1.100")
        self.ip_input.setStyleSheet("padding: 8px; border: 1px solid #dcdfe6; border-radius: 4px;")
        
        # 端口输入框
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("例如: 5777")
        self.port_input.setStyleSheet("padding: 8px; border: 1px solid #dcdfe6; border-radius: 4px;")

        ip_label = QLabel("服务器 IP:")
        ip_label.setStyleSheet("font-weight: normal; font-size: 13px;")
        port_label = QLabel("端口号:")
        port_label.setStyleSheet("font-weight: normal; font-size: 13px;")

        form_layout.addRow(ip_label, self.ip_input)
        form_layout.addRow(port_label, self.port_input)
        
        config_layout.addLayout(form_layout)
        config_layout.addStretch() # 顶上去

        # 按钮栏
        btn_layout = QHBoxLayout()
        
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
        self.load_config_to_ui()

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

    def load_config_to_ui(self):
        """加载配置到UI"""
        # 重新从文件加载
        self.config_loader.reload()
        config = self.config_loader.get_config()
        
        # 提取 IP 和 端口
        try:
            # 优先尝试从 login.api_url 获取
            api_url = config.get("login", {}).get("api_url", "")
            if not api_url:
                # 尝试从 deepseek.upload_url 获取
                api_url = config.get("deepseek", {}).get("upload_url", "")
            
            if api_url:
                # 使用正则解析 http://IP:PORT/...
                match = re.search(r'https?://([^/]+)', api_url)
                if match:
                    authority = match.group(1) # 192.168.100.119:5777
                    if ':' in authority:
                        ip, port = authority.split(':')
                        self.ip_input.setText(ip)
                        self.port_input.setText(port)
                    else:
                        self.ip_input.setText(authority)
                        self.port_input.setText("80") # 默认端口
                else:
                    self.ip_input.setText("")
                    self.port_input.setText("")
            else:
                self.ip_input.setText("")
                self.port_input.setText("")
        except Exception as e:
            print(f"Error parsing config: {e}")
            self.ip_input.setText("")
            self.port_input.setText("")
            
        self.update_last_modified_time()
        
    def save_config(self):
        """保存配置"""
        new_ip = self.ip_input.text().strip()
        new_port = self.port_input.text().strip()
        
        if not new_ip or not new_port:
             QMessageBox.warning(self, "警告", "IP 和端口不能为空！")
             return

        # 获取当前配置的深拷贝
        config = copy.deepcopy(self.config_loader.get_config())
        
        # 获取旧的 authority (用于查找替换)
        old_authority = ""
        try:
            # 同样逻辑获取旧地址
            api_url = config.get("login", {}).get("api_url", "")
            if not api_url:
                api_url = config.get("deepseek", {}).get("upload_url", "")
                
            match = re.search(r'https?://([^/]+)', api_url)
            if match:
                old_authority = match.group(1)
        except:
            pass
            
        if not old_authority:
             QMessageBox.warning(self, "警告", "无法从当前配置中解析旧的服务器地址，无法进行替换。")
             return
             
        new_authority = f"{new_ip}:{new_port}"
        
        # 如果地址没变，无需保存
        if old_authority == new_authority:
             QMessageBox.information(self, "提示", "配置未发生变化。")
             return

        # 递归替换所有 URL 中的 host
        self._recursive_replace(config, old_authority, new_authority)
        
        # 序列化并保存
        try:
            config_str = json.dumps(config, indent=4, ensure_ascii=False)
            success, msg = self.config_loader.save_config(config_str)
            
            if success:
                self.update_last_modified_time()
                QMessageBox.information(self, "成功", f"服务器地址已更新\n从 {old_authority} 变更为 {new_authority}")
                # 重新加载以确保一致性
                self.load_config_to_ui()
            else:
                QMessageBox.critical(self, "错误", f"保存失败: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"配置处理异常: {e}")

    def _recursive_replace(self, obj, old_str, new_str):
        """递归替换 JSON 对象中的 URL Host"""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    # 仅替换 http/https 开头的 URL 中的 host 部分
                    if old_str in v and ("http://" in v or "https://" in v):
                         obj[k] = v.replace(old_str, new_str)
                elif isinstance(v, (dict, list)):
                    self._recursive_replace(v, old_str, new_str)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, str):
                     if old_str in v and ("http://" in v or "https://" in v):
                         obj[i] = v.replace(old_str, new_str)
                elif isinstance(v, (dict, list)):
                    self._recursive_replace(v, old_str, new_str)


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
