#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：main_window.py
# 作者：liuhd
# 日期：2026-02-04 10:00:00
# 描述：主窗口逻辑 (侧边栏与页面切换)

import os
import sys
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QStackedWidget, QListWidgetItem, QFrame, QPushButton, QStyle,
                             QSystemTrayIcon, QMenu, QApplication, QMessageBox)
from PyQt6.QtCore import QSize, Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction

from pages import (LoginPage, ModelScopePage, DeepSeekPage, ImageGenPage, ImageParsePage, 
                    RrdsppgPage, SystemMonitorPage, DocToolsPage, ImageToolsPage, VoiceToolsPage, VideoGenPage, MusicGenPage, MediaToolsPage, SettingsPage)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TRAI")
        self.user_token = ""
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), "icon", "tr_mascot_local.ico")
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
        self.sidebar.setIconSize(QSize(24, 24)) # 设置图标大小
        self.sidebar.currentRowChanged.connect(self.display_page)
        
        # 添加侧边栏选项
        self.add_sidebar_item("登录/注册", "👤")
        self.add_sidebar_item("ModelScope 工具", "🛠️")
        self.add_sidebar_item("文档工具箱", "📚")
        self.add_sidebar_item("图像工具箱", "🖼️")
        self.add_sidebar_item("媒体工具箱", "🎞️")
        self.add_sidebar_item("语音服务", "🎙️")
        self.add_sidebar_item("DeepSeek 对话", "💬")
        self.add_sidebar_item("AI 文生图", "🎨")
        self.add_sidebar_item("AI 文生视频", "🎬")
        self.add_sidebar_item("AI 文生音乐", "🎵")
        self.add_sidebar_item("图片内容解析", "👁️")
        self.add_sidebar_item("人人都是品牌官", "📝")
        self.add_sidebar_item("系统监控", "📊")
        
        # 将组件加入侧边栏容器
        self.sidebar_layout.addWidget(self.top_header)
        self.sidebar_layout.addWidget(self.sidebar)
        
        # 底部设置按钮
        self.settings_btn = QPushButton("      设置")
        self.settings_btn.setIcon(self.create_emoji_icon("⚙️"))
        self.settings_btn.setIconSize(QSize(24, 24))
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setFixedHeight(50)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 10px;
                border: none;
                background-color: transparent;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
            }
        """)
        self.settings_btn.clicked.connect(self.show_settings_page)
        self.sidebar_layout.addWidget(self.settings_btn)

        # 2. 内容区域 (堆叠窗口)
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("contentArea")
        
        # 初始化页面
        self.login_page = LoginPage()
        self.login_page.login_success.connect(self.on_login_success) # 连接登录成功信号
        self.modelscope_page = ModelScopePage()
        self.doc_tools_page = DocToolsPage()
        self.image_tools_page = ImageToolsPage()
        self.media_tools_page = MediaToolsPage()
        self.voice_tools_page = VoiceToolsPage()
        self.deepseek_page = DeepSeekPage()
        self.image_gen_page = ImageGenPage()
        self.video_gen_page = VideoGenPage()
        self.music_gen_page = MusicGenPage()
        self.image_parse_page = ImageParsePage()
        self.rrdsppg_page = RrdsppgPage()
        self.system_monitor_page = SystemMonitorPage()
        self.settings_page = SettingsPage()
        
        # 添加页面到堆叠窗口
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.modelscope_page)
        self.stacked_widget.addWidget(self.doc_tools_page)
        self.stacked_widget.addWidget(self.image_tools_page)
        self.stacked_widget.addWidget(self.media_tools_page)
        self.stacked_widget.addWidget(self.voice_tools_page)
        self.stacked_widget.addWidget(self.deepseek_page)
        self.stacked_widget.addWidget(self.image_gen_page)
        self.stacked_widget.addWidget(self.video_gen_page)
        self.stacked_widget.addWidget(self.music_gen_page)
        self.stacked_widget.addWidget(self.image_parse_page)
        self.stacked_widget.addWidget(self.rrdsppg_page)
        self.stacked_widget.addWidget(self.system_monitor_page)
        self.stacked_widget.addWidget(self.settings_page)
        
        # 添加到主布局
        main_layout.addWidget(self.sidebar_container)
        main_layout.addWidget(self.stacked_widget)
        
        # 默认选中第一项
        self.sidebar.setCurrentRow(0)
        
        # 初始化权限控制
        self.update_sidebar_access(is_logged_in=False)

        # 初始化系统托盘
        self.tray_icon = None
        self.init_system_tray()

    def init_system_tray(self):
        """初始化系统托盘"""
        # 检查系统是否支持托盘
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self)
        
        # 设置图标 (使用窗口图标)
        icon = self.windowIcon()
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("TRAI")
        
        # 创建上下文菜单
        tray_menu = QMenu()
        
        # 显示主界面动作
        show_action = QAction("显示主界面", self)
        show_action.triggered.connect(self.show_normal_window)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        # 退出动作
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # 连接激活信号 (如点击托盘图标)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def on_tray_icon_activated(self, reason):
        """处理托盘图标点击事件"""
        # Trigger 通常是单击 (Windows/Linux)
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_normal_window()
        # DoubleClick 双击
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_normal_window()

    def show_normal_window(self):
        """显示并激活主窗口"""
        self.show()
        self.setWindowState(Qt.WindowState.WindowNoState)
        self.activateWindow()

    def quit_app(self):
        """完全退出应用"""
        # 隐藏托盘图标，避免退出后残留
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        """重写关闭事件: 询问是最小化到托盘还是直接退出"""
        # 只有在托盘图标可用且显示时，才询问
        if self.tray_icon and self.tray_icon.isVisible():
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("退出确认")
            msg_box.setText("您点击了关闭按钮，请选择：")
            msg_box.setIcon(QMessageBox.Icon.Question)
            
            # 设置样式表，调整字体大小
            msg_box.setStyleSheet("""
                QLabel { font-size: 13px; }
                QPushButton { font-size: 12px; padding: 4px 12px; }
            """)
            
            # 自定义按钮
            minimize_btn = msg_box.addButton("最小化至托盘", QMessageBox.ButtonRole.ActionRole)
            quit_btn = msg_box.addButton("直接退出", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = msg_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            
            # 默认选中最小化
            msg_box.setDefaultButton(minimize_btn)
            
            msg_box.exec()
            
            clicked_button = msg_box.clickedButton()
            
            if clicked_button == minimize_btn:
                event.ignore()
                self.hide()
            elif clicked_button == quit_btn:
                self.quit_app() # 调用清理逻辑
                event.accept()
            else:
                event.ignore() # 取消关闭
        else:
            event.accept()

    def create_emoji_icon(self, emoji, size=64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 优先使用 Segoe UI Emoji 字体 (Windows) 或 Apple Color Emoji (Mac)
        font = QFont("Segoe UI Emoji", int(size * 0.6))
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        painter.setFont(font)
        # 居中绘制
        rect = pixmap.rect()
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, emoji)
        painter.end()
        return QIcon(pixmap)

    def add_sidebar_item(self, name, icon_emoji=""):
        item = QListWidgetItem(name)
        item.setSizeHint(QSize(0, 50)) # 设置高度
        
        if icon_emoji:
            item.setIcon(self.create_emoji_icon(icon_emoji))
            
        # 左对齐，保证折叠后图标可见
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
            self.modelscope_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.doc_tools_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.image_tools_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.media_tools_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.voice_tools_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.deepseek_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.image_gen_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.video_gen_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.music_gen_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.image_parse_page.set_auth_token(self.user_token)
        except Exception:
            pass
        try:
            self.rrdsppg_page.set_auth_token(self.user_token)
        except Exception:
            pass
        # 登录成功后，可以自动跳转到 ModelScope 工具页（索引1）
        if self.sidebar.count() > 1:
            self.sidebar.setCurrentRow(1)

    def display_page(self, index):
        """切换页面"""
        if index == -1:
            return
            
        # 恢复设置按钮样式
        self.settings_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 10px;
                border: none;
                background-color: transparent;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
            }
        """)
        self.stacked_widget.setCurrentIndex(index)

    def show_settings_page(self):
        """显示设置页面"""
        # 取消侧边栏选中状态
        self.sidebar.setCurrentRow(-1)
        
        # 切换到设置页 (最后一页)
        self.stacked_widget.setCurrentWidget(self.settings_page)
        
        # 高亮设置按钮
        self.settings_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 10px;
                border: none;
                background-color: #d1d1d1;
                font-size: 14px;
            }
        """)

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

