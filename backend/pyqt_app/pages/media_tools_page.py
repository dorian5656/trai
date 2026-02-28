#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：media_tools_page.py
# 作者：liuhd
# 日期：2026-02-28 11:13:00
# 描述：媒体工具箱页面，提供视频转GIF等媒体处理功能

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QGridLayout,
    QLineEdit,
    QFileDialog,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QMessageBox,
    QTabWidget,
    QTimeEdit,
    QSizePolicy,
    QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTime
from PyQt6.QtGui import QDesktopServices, QIcon, QMovie
import os
import requests
import tempfile
import shutil
from datetime import datetime
from loguru import logger
from .config_loader import config

class VideoToGifWorker(QThread):
    """视频转GIF工作线程"""
    finished_signal = pyqtSignal(bool, str, str) # success, msg/path, type(error/success)

    def __init__(self, api_url, video_path, fps, width, token=None):
        super().__init__()
        self.api_url = api_url
        self.video_path = video_path
        self.fps = fps
        self.width = width
        self.token = token

    def run(self):
        file_handle = None
        try:
            # 1. 上传并转换
            file_handle = open(self.video_path, 'rb')
            files = {
                'file': (os.path.basename(self.video_path), file_handle, 'video/mp4')
            }
            params = {
                'fps': self.fps,
                'width': self.width
            }
            headers = {}
            if self.token:
                headers['Authorization'] = f"Bearer {self.token}"

            logger.info(f"Start converting video to GIF: {self.video_path}, params={params}")
            response = requests.post(self.api_url, files=files, params=params, headers=headers, timeout=300)
            
            if response.status_code != 200:
                logger.error(f"Conversion failed: {response.text}")
                self.finished_signal.emit(False, f"转换失败: {response.status_code} - {response.text}", "error")
                return

            # 2. 获取下载链接
            resp_json = response.json()
            download_url = ""
            
            # 优先尝试从标准结构解析: data -> url
            if isinstance(resp_json, dict):
                data = resp_json.get("data")
                if isinstance(data, dict):
                    download_url = data.get("url", "")
                elif isinstance(data, str):
                    download_url = data
                
                # 如果没找到，尝试直接从根节点找 url (兼容性)
                if not download_url:
                    download_url = resp_json.get("url", "")
            elif isinstance(resp_json, str):
                download_url = resp_json
            
            if not download_url or not isinstance(download_url, str) or not download_url.startswith("http"):
                 # 如果返回不是URL，可能是直接返回了文件内容？或者错误信息？
                 # 根据API描述，返回下载链接。如果是直接返回文件流，header会有Content-Type: image/gif
                 content_type = response.headers.get("Content-Type", "")
                 if "image/gif" in content_type:
                     # 直接返回了文件流
                     try:
                         temp_file = tempfile.NamedTemporaryFile(suffix=".gif", delete=False)
                         temp_file.write(response.content)
                         temp_file.close()
                         self.finished_signal.emit(True, temp_file.name, "success")
                         return
                     except Exception as e:
                         self.finished_signal.emit(False, f"保存临时文件失败: {str(e)}", "error")
                         return
                 else:
                    self.finished_signal.emit(False, f"无法解析返回结果: {response.text[:100]}", "error")
                    return

            logger.info(f"Download URL: {download_url}")
            
            # 3. 下载文件到临时目录
            logger.info("Downloading to temp file...")
            download_res = requests.get(download_url, stream=True, timeout=120)
            if download_res.status_code == 200:
                try:
                    temp_file = tempfile.NamedTemporaryFile(suffix=".gif", delete=False)
                    for chunk in download_res.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                    temp_file.close()
                    self.finished_signal.emit(True, temp_file.name, "success")
                except Exception as e:
                    self.finished_signal.emit(False, f"保存临时文件失败: {str(e)}", "error")
            else:
                self.finished_signal.emit(False, f"下载失败: {download_res.status_code}", "error")

        except Exception as e:
            logger.exception("Video to GIF error")
            self.finished_signal.emit(False, str(e), "error")
        finally:
            if file_handle:
                try:
                    file_handle.close()
                except Exception as e:
                    logger.warning(f"Failed to close file handle: {e}")


class MediaToolsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.token = None
        self.worker = None
        self.temp_gif_path = None
        self.movie = None
        self.init_ui()

    def set_auth_token(self, token: str):
        self.token = token or ""

    def init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 标题
        title_label = QLabel("🎞️ 媒体工具箱")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        main_layout.addWidget(title_label)

        # 选项卡
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                background: white;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #f5f5f5;
                border: 1px solid #e0e0e0;
                padding: 8px 20px;
                margin-right: 4px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white;
                font-weight: bold;
            }
        """)
        
        # 添加 "视频转GIF" 标签页
        self.video_to_gif_tab = self.create_video_to_gif_tab()
        self.tabs.addTab(self.video_to_gif_tab, "视频转GIF")
        
        main_layout.addWidget(self.tabs)

    def create_video_to_gif_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. 视频选择区域
        file_group = QFrame()
        file_group.setStyleSheet(".QFrame { background-color: #f9f9f9; border-radius: 8px; border: 1px solid #e0e0e0; }")
        file_layout = QVBoxLayout(file_group)
        
        file_label = QLabel("选择视频文件:")
        file_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        file_input_layout = QHBoxLayout()
        self.video_path_input = QLineEdit()
        self.video_path_input.setPlaceholderText("请选择要转换的视频文件...")
        self.video_path_input.setReadOnly(True)
        self.video_path_input.setFixedHeight(30)
        
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.setFixedHeight(30)
        self.browse_btn.clicked.connect(self.browse_video_file)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 0 15px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        
        file_input_layout.addWidget(self.video_path_input)
        file_input_layout.addWidget(self.browse_btn)
        
        file_layout.addWidget(file_label)
        file_layout.addLayout(file_input_layout)
        
        layout.addWidget(file_group)

        # 2. 参数设置区域
        params_group = QFrame()
        params_group.setStyleSheet(".QFrame { background-color: #f9f9f9; border-radius: 8px; border: 1px solid #e0e0e0; }")
        params_layout = QGridLayout(params_group)
        params_layout.setSpacing(15)
        
        params_title = QLabel("转换参数设置:")
        params_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        params_layout.addWidget(params_title, 0, 0, 1, 4)

        # 帧率 FPS
        params_layout.addWidget(QLabel("帧率 (FPS):"), 1, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(10)
        self.fps_spin.setSuffix(" fps")
        self.fps_spin.setToolTip("建议 5-20，数值越大文件越大")
        params_layout.addWidget(self.fps_spin, 1, 1)

        # 宽度 Width
        params_layout.addWidget(QLabel("宽度 (px):"), 1, 2)
        self.width_combo = QComboBox()
        self.width_combo.addItems(["320", "480", "640", "800", "Original"])
        self.width_combo.setCurrentIndex(0) # 默认 320
        self.width_combo.setToolTip("建议 320-640，数值越大文件越大")
        params_layout.addWidget(self.width_combo, 1, 3)
        
        layout.addWidget(params_group)

        # 3. 操作按钮区域
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        
        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.convert_btn.setFixedHeight(30)
        self.convert_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.convert_btn.clicked.connect(self.start_conversion)
        
        action_layout.addWidget(self.convert_btn)
        
        layout.addLayout(action_layout)

        # 4. 预览区域
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.preview_scroll.setStyleSheet("background: transparent;")
        self.preview_scroll.setMinimumHeight(360)
        self.preview_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        
        self.preview_label = QLabel("GIF 预览区域")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumWidth(720)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #ccc;
                border-radius: 8px;
                color: #999;
                padding: 20px;
                min-height: 360px;
            }
        """)
        preview_layout.addWidget(self.preview_label)
        
        self.preview_scroll.setWidget(preview_container)
        layout.addWidget(self.preview_scroll)

        # 5. 下载按钮和状态
        status_layout = QHBoxLayout()
        status_layout.addStretch()
        
        self.download_btn = QPushButton("下载 GIF")
        self.download_btn.setIcon(QIcon.fromTheme("document-save"))
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setFixedHeight(30)
        self.download_btn.setFixedWidth(120)
        self.download_btn.setVisible(False) # 默认隐藏
        self.download_btn.clicked.connect(self.download_gif)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                font-size: 14px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        status_layout.addWidget(self.download_btn)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        self.status_label = QLabel("准备就绪")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666; margin-top: 10px;")
        layout.addWidget(self.status_label)
        
        return tab

    def browse_video_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择视频文件", 
            "", 
            "Video Files (*.mp4 *.avi *.mov *.mkv *.flv);;All Files (*)"
        )
        if file_path:
            self.video_path_input.setText(file_path)
            self.status_label.setText(f"已选择: {os.path.basename(file_path)}")

    def start_conversion(self):
        video_path = self.video_path_input.text().strip()
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "提示", "请先选择有效的视频文件！")
            return

        if not self.token:
             QMessageBox.warning(self, "提示", "请先登录！")
             return

        # 获取参数
        fps = self.fps_spin.value()
        width_text = self.width_combo.currentText()
        
        width = 320 # 默认
        if width_text != "Original":
            try:
                width = int(width_text)
            except:
                width = 320
        else:
            width = 0 
        
        self.convert_btn.setEnabled(False)
        self.convert_btn.setText("转换中...")
        self.status_label.setText("正在上传并转换...")
        self.preview_label.setText("正在生成预览...")
        self.preview_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #2196F3;
                border-radius: 8px;
                color: #2196F3;
                padding: 20px;
                min-height: 150px;
            }
        """)
        self.download_btn.setVisible(False)
        
        # 清理旧的 movie
        if self.movie:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
            self.preview_label.clear()
        
        api_url = config.get("media_tools", {}).get("video2gif_url", "")
        if not api_url:
            QMessageBox.critical(self, "错误", "未配置 video2gif_url")
            self.reset_ui()
            return

        self.worker = VideoToGifWorker(api_url, video_path, fps, width if width_text != "Original" else None, self.token)
        self.worker.finished_signal.connect(self.on_conversion_finished)
        self.worker.start()

    def on_conversion_finished(self, success, result, type_):
        self.reset_ui()
        if success:
            self.status_label.setText("转换成功")
            self.temp_gif_path = result
            
            # 显示预览
            try:
                self.movie = QMovie(self.temp_gif_path)
                # 设置缓存模式以优化播放
                self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
                self.preview_label.setMovie(self.movie)
                self.preview_label.setStyleSheet("border: none;") # 去除边框
                self.movie.start()
                self.download_btn.setVisible(True)
            except Exception as e:
                self.status_label.setText(f"预览失败: {str(e)}")
                self.preview_label.setText("预览加载失败")
                
        else:
            self.status_label.setText(f"转换失败: {result}")
            self.preview_label.setText("转换失败")
            self.preview_label.setStyleSheet("""
                QLabel {
                    border: 2px dashed #F44336;
                    border-radius: 8px;
                    color: #F44336;
                    padding: 20px;
                    min-height: 150px;
                }
            """)
            QMessageBox.critical(self, "错误", f"转换失败: {result}")

    def download_gif(self):
        if not self.temp_gif_path or not os.path.exists(self.temp_gif_path):
            QMessageBox.warning(self, "提示", "预览文件已失效，请重新转换")
            return

        # 默认文件名加上时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(self.video_path_input.text()))[0]
        default_name = f"{base_name}_{timestamp}.gif"
        default_path = os.path.join(os.path.dirname(self.video_path_input.text()), default_name)

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 GIF",
            default_path,
            "GIF Files (*.gif);;All Files (*)"
        )

        if save_path:
            try:
                shutil.copy(self.temp_gif_path, save_path)
                
                # 自定义成功弹窗
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("下载成功")
                msg_box.setText(f"GIF 已保存至:\n{save_path}")
                msg_box.setIcon(QMessageBox.Icon.Information)
                
                open_file_btn = msg_box.addButton("打开图片", QMessageBox.ButtonRole.ActionRole)
                open_folder_btn = msg_box.addButton("打开目录", QMessageBox.ButtonRole.ActionRole)
                close_btn = msg_box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
                
                msg_box.exec()
                
                clicked_button = msg_box.clickedButton()
                if clicked_button == open_file_btn:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(save_path))
                elif clicked_button == open_folder_btn:
                    folder = os.path.dirname(save_path)
                    QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
                    
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存文件失败: {str(e)}")

    def set_auth_token(self, token: str):
        self.token = token or ""

    def reset_ui(self):
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText("开始转换")

    def closeEvent(self, event):
        if self.temp_gif_path and os.path.exists(self.temp_gif_path):
            try:
                os.remove(self.temp_gif_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {self.temp_gif_path}: {e}")
        super().closeEvent(event)
