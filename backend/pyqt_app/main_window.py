#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：main_window.py
# 作者：liuhd
# 日期：2026-02-04 10:00:00
# 描述：主窗口逻辑 (侧边栏与页面切换)

import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QStackedWidget, QListWidgetItem, QFrame, QPushButton, QStyle)
from PyQt6.QtCore import QSize, Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PyQt6.QtGui import QIcon

from pages import LoginPage, ModelScopePage, DeepSeekPage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TRAI")
        self.user_token = ""
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), "icon", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.resize(1200, 900)
        
        # 主容器
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局 (水平)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. 侧边栏容器 (用于包含按钮和列表，并进行动画缩放)
        self.sidebar_container = QWidget()
        self.sidebar_container.setObjectName("sidebarContainer")
        self.sidebar_container.setMaximumWidth(200) # 初始宽度
        self.sidebar_container.setMinimumWidth(200)
        
        self.sidebar_layout = QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(0)
        
        # 侧边栏顶部 Header (容器)
        self.top_header = QWidget()
        self.top_header.setObjectName("topHeader")
        self.top_header.setFixedHeight(50)
        
        header_layout = QHBoxLayout(self.top_header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        
        # 切换按钮
        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setObjectName("toggleBtn")
        self.toggle_btn.setFixedSize(50, 50) # 固定大小
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        
        header_layout.addStretch() # 弹簧挤到右边
        header_layout.addWidget(self.toggle_btn)

        # 侧边栏列表
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar") # 用于QSS
        self.sidebar.setFrameShape(QFrame.Shape.NoFrame) # 无边框
        self.sidebar.setFocusPolicy(Qt.FocusPolicy.NoFocus) # 去除选中虚线框
        self.sidebar.currentRowChanged.connect(self.display_page)
        
        # 添加侧边栏选项
        self.add_sidebar_item("登录/注册")
        self.add_sidebar_item("ModelScope 工具")
        self.add_sidebar_item("DeepSeek 对话")
        
        # 将组件加入侧边栏容器
        self.sidebar_layout.addWidget(self.top_header)
        self.sidebar_layout.addWidget(self.sidebar)

        # 2. 内容区域 (堆叠窗口)
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("contentArea")
        
        # 初始化页面
        self.login_page = LoginPage()
        self.login_page.login_success.connect(self.on_login_success) # 连接登录成功信号
        self.modelscope_page = ModelScopePage()
        self.deepseek_page = DeepSeekPage()
        
        # 添加页面到堆叠窗口
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.modelscope_page)
        self.stacked_widget.addWidget(self.deepseek_page)
        
        # 添加到主布局
        main_layout.addWidget(self.sidebar_container)
        main_layout.addWidget(self.stacked_widget)
        
        # 默认选中第一项
        self.sidebar.setCurrentRow(0)
        
        # 初始化权限控制
        self.update_sidebar_access(is_logged_in=False)

    def add_sidebar_item(self, name):
        item = QListWidgetItem(name)
        item.setSizeHint(QSize(0, 50)) # 设置高度
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar.addItem(item)
        
    def update_sidebar_access(self, is_logged_in):
        """更新侧边栏访问权限"""
        count = self.sidebar.count()
        for i in range(count):
            item = self.sidebar.item(i)
            # 第0项是登录/注册，始终可用
            # 其他项仅登录后可用
            if i == 0:
                item.setHidden(False)
                # 如果已登录，可以修改显示文本，例如 "用户中心"
                # if is_logged_in:
                #     item.setText("用户中心")
            else:
                # 方法1: 隐藏不可用的项
                # item.setHidden(not is_logged_in)
                
                # 方法2: 禁用不可用的项 (变灰且不可点击)
                if not is_logged_in:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                else:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                    
    def on_login_success(self, user_info):
        """处理登录成功"""
        self.update_sidebar_access(is_logged_in=True)
        if isinstance(user_info, dict):
            self.user_token = user_info.get("access_token", "") or user_info.get("data", {}).get("access_token", "")
        else:
            self.user_token = ""
        try:
            self.deepseek_page.set_auth_token(self.user_token)
        except Exception:
            pass
        # 登录成功后，可以自动跳转到 ModelScope 工具页（索引1）
        if self.sidebar.count() > 1:
            self.sidebar.setCurrentRow(1)

    def display_page(self, index):
        self.stacked_widget.setCurrentIndex(index)

    def toggle_sidebar(self):
        width = self.sidebar_container.width()
        # 目标宽度: 如果当前是200则变60，否则变200
        target_width = 60 if width == 200 else 200
        
        # 并行简单动画：同时改变最小和最大宽度，确保平滑
        self.anim_group = QParallelAnimationGroup()
        
        anim_min = QPropertyAnimation(self.sidebar_container, b"minimumWidth")
        anim_min.setDuration(300)
        anim_min.setStartValue(width)
        anim_min.setEndValue(target_width)
        anim_min.setEasingCurve(QEasingCurve.Type.InOutQuart)
        
        anim_max = QPropertyAnimation(self.sidebar_container, b"maximumWidth")
        anim_max.setDuration(300)
        anim_max.setStartValue(width)
        anim_max.setEndValue(target_width)
        anim_max.setEasingCurve(QEasingCurve.Type.InOutQuart)

        self.anim_group.addAnimation(anim_min)
        self.anim_group.addAnimation(anim_max)
        self.anim_group.start()
        
        # 切换文本显示状态 (折叠时隐藏文本，展开时显示)
        # 注意：动画开始时或结束时处理文本可能更好，这里简化处理，直接设置
        # 但 QListWidget 默认是 IconMode 还是 ListMode? 默认 ListMode 图标在左文本在右。
        # 宽度变窄时文本会自动截断。为了美观，可以在折叠后隐藏文本。
        # 这里为了简单，暂不动态隐藏文本，依赖宽度遮挡。

