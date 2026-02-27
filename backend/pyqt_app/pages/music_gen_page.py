#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：music_gen_page.py
# 作者：liuhd
# 日期：2026-02-27 15:29:00
# 描述：AI 文生音乐功能页面

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QMessageBox, QTextEdit, QSpinBox,
                             QSizePolicy, QFileDialog, QStackedWidget, QStyle, QProgressBar, QSlider)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from .config_loader import config
import requests
import os
import subprocess
from datetime import datetime
from loguru import logger

class MusicGenWorker(QThread):
    """文生音乐工作线程"""
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
            
            logger.info(f"Start generating music at: {self.api_url}")
            # 设置较长的超时时间，生成音乐可能较慢
            response = requests.post(self.api_url, json=self.payload, headers=headers, timeout=300)
            
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
            logger.error(f"Music generation failed: {e}")
            self.finished_signal.emit(False, {}, str(e))

class MusicGenPage(QWidget):
    def __init__(self):
        super().__init__()
        self.auth_token = ""
        self.generated_audio_url = ""
        self.init_ui()
        self.init_audio_player()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 标题
        title_label = QLabel("AI 文生音乐")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        main_layout.addWidget(title_label)

        # 顶部控制区 (参数输入)
        input_layout = QVBoxLayout()
        input_layout.setSpacing(10)

        # 1. Prompt
        prompt_label = QLabel("音乐风格描述 (Prompt):")
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("例如：女性 流行音乐，清亮女声，现代流行编曲...")
        self.prompt_input.setFixedHeight(60)
        self.prompt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                background-color: #fff;
            }
            QTextEdit:focus {
                border: 1px solid #2196F3;
            }
        """)
        input_layout.addWidget(prompt_label)
        input_layout.addWidget(self.prompt_input)
        
        # 2. Lyrics
        lyrics_label = QLabel("自定义歌词 (可选):")
        self.lyrics_input = QTextEdit()
        self.lyrics_input.setPlaceholderText("请输入歌词...\n如果不输入，将生成纯音乐或随机歌词。")
        self.lyrics_input.setFixedHeight(80)
        self.lyrics_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                background-color: #fff;
            }
            QTextEdit:focus {
                border: 1px solid #2196F3;
            }
        """)
        input_layout.addWidget(lyrics_label)
        input_layout.addWidget(self.lyrics_input)

        # 3. Duration & Buttons
        bottom_control_layout = QHBoxLayout()
        bottom_control_layout.setSpacing(15)
        
        # 时长设置
        duration_layout = QHBoxLayout()
        duration_label = QLabel("时长(秒):")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(5, 300) # 5秒到300秒
        self.duration_spin.setValue(30)
        self.duration_spin.setFixedWidth(80)
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.duration_spin)
        
        bottom_control_layout.addLayout(duration_layout)
        bottom_control_layout.addStretch() # 弹簧
        
        # 按钮
        self.generate_btn = QPushButton("生成音乐")
        self.generate_btn.setFixedHeight(30)
        self.generate_btn.setFixedWidth(120)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.generate_btn.clicked.connect(self.generate_music)

        self.download_btn = QPushButton("下载音乐")
        self.download_btn.setFixedHeight(30)
        self.download_btn.setFixedWidth(120)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.download_btn.clicked.connect(self.download_music)
        
        bottom_control_layout.addWidget(self.generate_btn)
        bottom_control_layout.addWidget(self.download_btn)

        input_layout.addLayout(bottom_control_layout)
        main_layout.addLayout(input_layout)

        # 音乐展示区域 (下方)
        self.audio_stack = QStackedWidget()
        
        # Page 0: 占位符
        self.placeholder_label = QLabel("此处显示生成的音乐")
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
        self.audio_stack.addWidget(self.placeholder_label)
        
        # Page 1: 音乐播放器界面
        self.player_widget = QWidget()
        self.player_widget.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 10px;
            }
        """)
        player_layout = QVBoxLayout(self.player_widget)
        
        # 音乐图标或可视化占位
        self.music_icon_label = QLabel("🎵")
        self.music_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.music_icon_label.setStyleSheet("font-size: 64px; color: #2196F3; border: none;")
        player_layout.addWidget(self.music_icon_label)
        
        # 进度条
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        player_layout.addWidget(self.position_slider)
        
        # 控制按钮行
        controls_layout = QHBoxLayout()
        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self.toggle_play)
        self.play_btn.setStyleSheet("border: none; background: transparent;")
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("border: none; color: #666;")
        
        controls_layout.addStretch()
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.time_label)
        controls_layout.addStretch()
        
        player_layout.addLayout(controls_layout)
        
        self.audio_stack.addWidget(self.player_widget)
        
        # 容器设置
        self.audio_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # self.audio_stack.setMinimumHeight(200) # 音乐播放器不需要太高
        
        main_layout.addWidget(self.audio_stack, 1) # 1 表示占用剩余空间

    def init_audio_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playbackStateChanged.connect(self.media_state_changed)
        self.player.errorOccurred.connect(self.handle_error)

    def set_auth_token(self, token: str):
        self.auth_token = token or ""

    def generate_music(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入音乐风格描述")
            return
        
        if not self.auth_token:
            QMessageBox.warning(self, "提示", "请先登录")
            return

        api_url = config.get("music_gen", {}).get("api_url", "")
        if not api_url:
            QMessageBox.warning(self, "错误", "未找到音乐生成接口配置")
            return

        # 界面状态更新
        self.player.stop()
        self.audio_stack.setCurrentIndex(0)
        self.placeholder_label.setText("正在生成音乐，请稍候...")
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("生成中...")
        self.download_btn.setEnabled(False)
        
        # 构造请求参数
        lyrics = self.lyrics_input.toPlainText().strip()
        duration = self.duration_spin.value()
        
        payload = {
            "prompt": prompt,
            "model_id": "ACE-Step/Ace-Step1.5",
            "user_id": "system", # 暂时写死，后续可以从登录信息获取
            "duration": duration
        }
        
        if lyrics:
            payload["lyrics"] = lyrics
        
        self.worker = MusicGenWorker(api_url, payload, self.auth_token)
        self.worker.finished_signal.connect(self._on_generation_finished)
        self.worker.start()

    def _on_generation_finished(self, success: bool, data: dict, msg: str):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("生成音乐")
        
        if success:
            # 假设返回结构: {"data": {"audio_url": "..."}} 或直接 {"audio_url": "..."}
            # 根据 API 示例返回体: ResponseModel(data=MusicGenResponse)
            # 假设 MusicGenResponse 包含 audio_url
            
            resp_data = data.get("data", {})
            music_url = resp_data.get("audio_url", "") or resp_data.get("url", "")
            
            if music_url:
                self.generated_audio_url = music_url
                self.download_btn.setEnabled(True)
                
                # 切换到播放器
                self.audio_stack.setCurrentIndex(1)
                self.player.setSource(QUrl(music_url))
                self.player.play()
                
                logger.success(f"Music generated: {music_url}")
            else:
                self.placeholder_label.setText("生成成功，但未返回音频地址。")
                self.audio_stack.setCurrentIndex(0)
        else:
            self.placeholder_label.setText(f"生成失败: {msg}")
            self.audio_stack.setCurrentIndex(0)
            QMessageBox.critical(self, "生成失败", f"错误信息: {msg}")

    def download_music(self):
        if not self.generated_audio_url:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"generated_music_{timestamp}.wav"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存音乐", default_filename, "Audio Files (*.wav *.mp3);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            # 简单的下载逻辑
            response = requests.get(self.generated_audio_url, stream=True)
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

    def show_download_success_dialog(self, file_path: str):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("下载成功")
        msg_box.setText(f"音乐已保存至：\n{file_path}")
        msg_box.setIcon(QMessageBox.Icon.Information)

        play_btn = msg_box.addButton("直接播放", QMessageBox.ButtonRole.ActionRole)
        open_folder_btn = msg_box.addButton("打开文件目录", QMessageBox.ButtonRole.ActionRole)
        close_btn = msg_box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        clicked_button = msg_box.clickedButton()
        if clicked_button == play_btn:
            self.play_local_file(file_path)
        elif clicked_button == open_folder_btn:
            self.open_folder(file_path)

    def play_local_file(self, file_path: str):
        try:
            if not os.path.exists(file_path):
                QMessageBox.warning(self, "错误", "文件不存在，无法播放。")
                return
            self.audio_stack.setCurrentIndex(1)
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.play()
        except Exception as e:
            logger.error(f"Play local file failed: {e}")
            QMessageBox.warning(self, "错误", f"无法播放该文件: {e}")

    def open_folder(self, file_path: str):
        try:
            if os.name == 'nt':
                normalized_path = os.path.normpath(file_path)
                subprocess.Popen(f'explorer /select,"{normalized_path}"')
            else:
                folder_path = os.path.dirname(file_path)
                subprocess.call(['xdg-open', folder_path])
        except Exception as e:
            logger.error(f"Open folder failed: {e}")
            QMessageBox.warning(self, "错误", f"无法打开文件目录: {e}")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def media_state_changed(self, state):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def position_changed(self, position):
        # 只有当用户没有在拖动滑块时才更新滑块位置
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        self.update_time_label()

    def duration_changed(self, duration):
        self.position_slider.setRange(0, duration)
        self.update_time_label()

    def set_position(self, position):
        self.player.setPosition(position)

    def update_time_label(self):
        position = self.player.position()
        duration = self.player.duration()
        
        def format_time(ms):
            seconds = (ms // 1000) % 60
            minutes = (ms // 60000)
            return f"{minutes:02d}:{seconds:02d}"
            
        self.time_label.setText(f"{format_time(position)} / {format_time(duration)}")

    def handle_error(self):
        self.play_btn.setEnabled(False)
        logger.error(f"Music Player Error: {self.player.errorString()}")
