#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：video_gen_page.py
# 作者：liuhd
# 日期：2026-02-27 11:04:00
# 描述：AI 文生视频功能页面

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QFrame, QMessageBox, QScrollArea, QTextEdit,
                             QSizePolicy, QFileDialog, QStackedWidget, QStyle)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer, QStandardPaths
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from .config_loader import config
import requests
import os
import subprocess
import tempfile
import hashlib
from datetime import datetime
from loguru import logger

# 尝试导入 cv2，如果失败则标记不可用
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logger.warning("opencv-python not found, video cover extraction disabled.")

class VideoGenWorker(QThread):
    """文生视频工作线程"""
    finished_signal = pyqtSignal(bool, dict, str)

    def __init__(self, api_url, payload, token=None):
        super().__init__()
        self.api_url = api_url
        self.payload = payload
        self.token = token

    def run(self):
        try:
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json"
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            logger.info(f"Start generating video at: {self.api_url}")
            # 设置较长的超时时间，视频生成可能很慢
            response = requests.post(self.api_url, json=self.payload, headers=headers, timeout=600)
            
            if response.status_code == 200:
                data = response.json()
                self.finished_signal.emit(True, data, "生成成功")
            else:
                try:
                    err_data = response.json()
                    err_msg = err_data.get("detail", f"HTTP {response.status_code}")
                except:
                    err_msg = f"HTTP {response.status_code}"
                self.finished_signal.emit(False, {}, err_msg)
                
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            self.finished_signal.emit(False, {}, str(e))

class VideoDownloader(QThread):
    """视频下载线程（用于缓存）"""
    finished_signal = pyqtSignal(bool, str, str) # success, file_path, url

    def __init__(self, url, cache_dir):
        super().__init__()
        self.url = url
        self.cache_dir = cache_dir

    def run(self):
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
            
            # 使用 URL 哈希作为文件名
            file_name = hashlib.md5(self.url.encode()).hexdigest() + ".mp4"
            file_path = os.path.join(self.cache_dir, file_name)
            
            # 如果文件已存在且大小不为0，直接返回
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                self.finished_signal.emit(True, file_path, self.url)
                return

            logger.info(f"Caching video from {self.url} to {file_path}")
            response = requests.get(self.url, stream=True, timeout=60)
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.finished_signal.emit(True, file_path, self.url)
            else:
                self.finished_signal.emit(False, "", self.url)
        except Exception as e:
            logger.error(f"Cache video failed: {e}")
            self.finished_signal.emit(False, "", self.url)

class VideoGenPage(QWidget):
    def __init__(self):
        super().__init__()
        self.auth_token = ""
        self.generated_video_url = ""
        self.local_video_path = "" # 本地缓存路径
        
        # 获取系统临时目录作为缓存目录
        self.cache_dir = os.path.join(tempfile.gettempdir(), "trai_video_cache")
        
        self.init_ui()
        self.init_media_player()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 标题
        title_label = QLabel("AI 文生视频")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        main_layout.addWidget(title_label)

        # 顶部控制区 (输入框 + 按钮)
        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("请输入视频画面描述 (Prompt)...")
        self.prompt_input.setFixedHeight(80)
        self.prompt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                background-color: #fff;
            }
            QTextEdit:focus {
                border: 1px solid #2196f3;
            }
        """)
        
        # 按钮容器
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)
        
        self.generate_btn = QPushButton("生成视频")
        self.generate_btn.setFixedHeight(30)
        self.generate_btn.setFixedWidth(100)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.generate_btn.clicked.connect(self.generate_video)

        self.download_btn = QPushButton("下载视频")
        self.download_btn.setFixedHeight(30)
        self.download_btn.setFixedWidth(100)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.download_btn.clicked.connect(self.download_video)
        
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.download_btn)

        control_layout.addWidget(self.prompt_input)
        control_layout.addLayout(btn_layout)
        
        main_layout.addLayout(control_layout)

        # 视频展示区域
        self.video_stack = QStackedWidget()
        
        # Page 0: 占位符/封面图
        self.placeholder_label = QLabel("此处显示生成的视频")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 10px;
                color: #999;
                font-size: 16px;
            }
        """)
        self.placeholder_label.setScaledContents(True) # 允许内容缩放
        self.video_stack.addWidget(self.placeholder_label)
        
        # Page 1: 视频播放器
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black; border-radius: 10px;")
        self.video_stack.addWidget(self.video_widget)
        
        # 视频容器
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(5)
        
        self.video_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_stack.setMinimumHeight(360)
        
        video_layout.addWidget(self.video_stack)
        
        # 播放控制条
        self.control_layout = QHBoxLayout()
        self.play_btn = QPushButton()
        self.play_btn.setEnabled(False)
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self.toggle_video)
        
        self.control_layout.addWidget(self.play_btn)
        self.control_layout.addStretch()
        
        video_layout.addLayout(self.control_layout)
        
        main_layout.addWidget(video_container, 1)

    def init_media_player(self):
        """初始化媒体播放器"""
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        
        self.media_player.playbackStateChanged.connect(self.media_state_changed)
        self.media_player.errorOccurred.connect(self.handle_media_error)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status)

    def set_auth_token(self, token: str):
        self.auth_token = token or ""

    def generate_video(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入画面描述")
            return
        
        if not self.auth_token:
            QMessageBox.warning(self, "提示", "请先登录")
            return

        api_url = config.get("video_gen", {}).get("api_url", "")
        if not api_url:
            QMessageBox.warning(self, "错误", "未找到视频生成接口配置")
            return

        # 重置状态
        self.media_player.stop()
        self.video_stack.setCurrentIndex(0)
        self.play_btn.setEnabled(False)
        self.placeholder_label.setPixmap(QPixmap())
        self.placeholder_label.setText("正在生成视频，请稍候...\n(可能需要几分钟)")
        self.generated_video_url = ""
        self.local_video_path = ""

        # 禁用按钮
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("生成中...")
        self.download_btn.setEnabled(False)
        
        payload = {
            "prompt": prompt,
            "model": "Wan2.1-T2V-1.3B",
            "ratio": "16:9",
            "duration": 5,
            "sampling_steps": 20,
            "guide_scale": 5,
            "seed": -1
        }
        
        self.worker = VideoGenWorker(api_url, payload, self.auth_token)
        self.worker.finished_signal.connect(self._on_generation_finished)
        self.worker.start()

    def _on_generation_finished(self, success: bool, data: dict, msg: str):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("生成视频")
        
        if success:
            video_data = data.get("data", {})
            video_url = video_data.get("video_url", "")
            cover_url = video_data.get("cover_url") or video_data.get("cover") or video_data.get("image_url")
            
            if video_url:
                self.generated_video_url = video_url
                self.download_btn.setEnabled(True)
                logger.success(f"Video generated: {video_url}")
                
                # 无论是否有封面，都先下载视频到本地缓存，以便播放
                self.placeholder_label.setText("视频生成成功，正在缓存...")
                self.cache_worker = VideoDownloader(video_url, self.cache_dir)
                self.cache_worker.finished_signal.connect(lambda s, p, u: self._on_video_cached(s, p, u, cover_url))
                self.cache_worker.start()
            else:
                self.placeholder_label.setText("生成成功，但未返回视频地址。")
        else:
            self.placeholder_label.setText(f"生成失败: {msg}")
            QMessageBox.critical(self, "生成失败", f"错误信息: {msg}")

    def _on_video_cached(self, success, file_path, url, cover_url):
        if success:
            self.local_video_path = file_path
            logger.info(f"Video cached at: {file_path}")
            
            # 设置播放源为本地文件
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            self.play_btn.setEnabled(True)
            
            # 尝试显示封面
            if cover_url:
                self.load_cover(cover_url)
                self.video_stack.setCurrentIndex(0) # 显示封面
            else:
                # 尝试从本地视频提取第一帧
                if HAS_CV2:
                    self.extract_frame_as_cover(file_path)
                else:
                    # 如果没有 CV2，则直接显示视频控件并暂停在第一帧
                    # 注意：这依赖于播放器能否正确加载并显示首帧
                    self.video_stack.setCurrentIndex(1)
                    self.media_player.setPosition(0)
                    self.media_player.pause() 
                    # 有些平台需要 play() 然后 pause() 才能显示
                    QTimer.singleShot(100, self.media_player.play)
                    QTimer.singleShot(300, self.media_player.pause)
        else:
            self.placeholder_label.setText("视频缓存失败，请尝试直接下载。")
            # 仍然允许播放远程 URL
            self.media_player.setSource(QUrl(url))
            self.play_btn.setEnabled(True)

    def extract_frame_as_cover(self, file_path):
        try:
            cap = cv2.VideoCapture(file_path)
            ret, frame = cap.read()
            if ret:
                # CV2 BGR -> RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                
                # 缩放并显示
                if not pixmap.isNull():
                    self.placeholder_label.setPixmap(pixmap.scaled(
                        self.placeholder_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    ))
                    self.placeholder_label.setText("")
                    self.video_stack.setCurrentIndex(0) # 确保显示封面页
            cap.release()
        except Exception as e:
            logger.error(f"Extract frame failed: {e}")
            self.video_stack.setCurrentIndex(1) # 失败则显示播放器

    def load_cover(self, cover_url):
        try:
            response = requests.get(cover_url, timeout=10)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                if not pixmap.isNull():
                    self.placeholder_label.setPixmap(pixmap.scaled(
                        self.placeholder_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    ))
                    self.placeholder_label.setText("")
        except Exception as e:
            logger.error(f"Failed to load cover: {e}")

    def download_video(self):
        if not self.generated_video_url:
            return
            
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"generated_video_{timestamp}.mp4"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存视频", default_filename, "Video Files (*.mp4);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            # 如果已有本地缓存，直接复制
            if self.local_video_path and os.path.exists(self.local_video_path):
                import shutil
                shutil.copy2(self.local_video_path, file_path)
                self.show_download_success_dialog(file_path)
            else:
                # 否则重新下载
                logger.info(f"Downloading video from {self.generated_video_url}")
                response = requests.get(self.generated_video_url, stream=True)
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    self.show_download_success_dialog(file_path)
                else:
                    QMessageBox.warning(self, "错误", f"下载失败: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Download failed: {e}")
            QMessageBox.critical(self, "错误", f"下载出错: {str(e)}")

    def show_download_success_dialog(self, file_path):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("下载成功")
        msg_box.setText(f"视频已保存至：\n{file_path}")
        msg_box.setIcon(QMessageBox.Icon.Information)
        
        open_video_btn = msg_box.addButton("打开视频", QMessageBox.ButtonRole.ActionRole)
        open_folder_btn = msg_box.addButton("打开文件夹", QMessageBox.ButtonRole.ActionRole)
        close_btn = msg_box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        clicked_button = msg_box.clickedButton()
        if clicked_button == open_video_btn:
            self.open_file(file_path)
        elif clicked_button == open_folder_btn:
            self.open_folder(file_path)

    def open_file(self, file_path):
        try:
            if os.name == 'nt':
                os.startfile(file_path)
            else:
                subprocess.call(['xdg-open', file_path])
        except Exception as e:
            logger.error(f"Failed to open file: {e}")

    def open_folder(self, file_path):
        try:
            if os.name == 'nt':
                file_path = os.path.normpath(file_path)
                subprocess.Popen(f'explorer /select,"{file_path}"')
            else:
                folder_path = os.path.dirname(file_path)
                subprocess.call(['xdg-open', folder_path])
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")

    def toggle_video(self):
        # 封面 -> 播放器
        if self.video_stack.currentIndex() == 0:
            if self.local_video_path or self.generated_video_url:
                self.video_stack.setCurrentIndex(1)
                self.media_player.play()
            return
            
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def media_state_changed(self, state):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def handle_media_error(self):
        self.play_btn.setEnabled(False)
        err_msg = self.media_player.errorString()
        logger.error(f"Media Player Error: {err_msg}")
        # 显示错误提示
        if self.isVisible():
            QMessageBox.warning(self, "播放错误", f"无法播放视频: {err_msg}")

    def handle_media_status(self, status):
        # 可以在这里处理缓冲状态等
        pass
