#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：modelscope_page.py
# 作者：liuhd
# 日期：2026-02-03 09:38:00
# 描述：ModelScope 模型上传工具 (PyQt6 GUI版)

import sys
import os
import shutil
import re
import logging  # Added for stdlib logging manipulation
from pathlib import Path

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QFileDialog, QMessageBox, QGroupBox,
                             QFormLayout, QTabWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtGui import QFont, QTextCursor

# 添加项目根目录到 sys.path
sys.path.append(str(Path(__file__).resolve().parents[3]))

from loguru import logger
from modelscope.hub.api import HubApi
from modelscope.hub.snapshot_download import snapshot_download
from .config_loader import config

# 默认配置
DEFAULT_MODEL_ID = config["modelscope"]["default_model_id"]
DEFAULT_UPLOAD_DIR = config["modelscope"]["default_upload_dir"]
DEFAULT_DOWNLOAD_DIR = config["modelscope"]["default_download_dir"]
DEFAULT_ACCESS_TOKEN = config["modelscope"]["api_key"]
DEFAULT_COMMIT_MSG = "输入提交模型的说明"

class StreamLogger:
    """
    一个辅助类，作为文件对象替换 sys.stdout/stderr
    """
    def __init__(self, signal):
        self.signal = signal

    def write(self, text):
        self.signal.emit(str(text))

    def flush(self):
        pass

    def isatty(self):
        # 返回 False 告知 tqdm 这是一个文件流，不要使用 ANSI 控制符
        return False

class LogSignal(QObject):
    """
    用于将日志发送到 GUI 的信号类
    """
    log_signal = pyqtSignal(str)

    def write(self, message):
        self.log_signal.emit(str(message))

    def flush(self):
        pass

class UploadWorker(QThread):
    """
    上传任务工作线程
    """
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, model_id, local_dir, access_token, commit_message):
        super().__init__()
        self.model_id = model_id
        self.local_dir = local_dir
        self.access_token = access_token
        self.commit_message = commit_message

    def cleanup_temp_dir(self, model_dir):
        """清理 SDK 可能残留的临时 Git 目录"""
        temp_dirs = [
            os.path.join(model_dir, '._____temp'),
            os.path.join(model_dir, '.git')
        ]
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"已清理残留目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理 {temp_dir} 时出错: {e}")

    def run(self):
        try:
            # 1. 验证目录和文件
            if not os.path.isdir(self.local_dir):
                logger.error(f"错误: 模型目录不存在 → {self.local_dir}")
                self.finished_signal.emit(False, "模型目录不存在")
                return

            if not os.listdir(self.local_dir):
                logger.error(f"错误: 模型目录为空 → {self.local_dir}")
                self.finished_signal.emit(False, "模型目录为空")
                return
            
            # 2. 清理残留临时目录
            self.cleanup_temp_dir(self.local_dir)
            
            # 3. 初始化 API 并登录
            api = HubApi()
            try:
                api.login(self.access_token)
                logger.success("ModelScope 账号登录成功")
            except Exception as e:
                logger.error(f"登录失败: {e}")
                logger.info("请访问: https://modelscope.cn/my/access/token 获取有效Token")
                self.finished_signal.emit(False, f"登录失败: {e}")
                return
            
            # 4. 上传
            logger.info(f"开始上传模型至 ModelScope: {self.model_id}")
            logger.info(f"本地目录: {self.local_dir}")
            
            api.upload_folder(
                folder_path=self.local_dir,
                repo_id=self.model_id,
                repo_type='model',
                commit_message=self.commit_message
            )
            
            logger.success("上传成功！")
            logger.info(f"模型主页: https://www.modelscope.cn/models/{self.model_id}")
            logger.info(f"文件列表: https://www.modelscope.cn/models/{self.model_id}/files")
            self.finished_signal.emit(True, "上传成功")

        except Exception as e:
            logger.error(f"上传失败: {type(e).__name__}: {e}")
            logger.info("排查建议:")
            logger.info("1. 确认 ACCESS_TOKEN 有效")
            logger.info("2. 确认 MODEL_ID 中的用户名与你的账号完全一致（区分大小写）")
            logger.info("3. 检查网络是否可访问 ModelScope")
            self.finished_signal.emit(False, str(e))

class DownloadWorker(QThread):
    """
    下载任务工作线程
    """
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, model_id, local_dir):
        super().__init__()
        self.model_id = model_id
        self.local_dir = local_dir

    def run(self):
        try:
            logger.info(f"模型: {self.model_id}")
            logger.info(f"目标路径: {self.local_dir}")
            os.makedirs(self.local_dir, exist_ok=True)

            logger.info("开始下载（自动断点续传）...")
            final_path = snapshot_download(
                model_id=self.model_id,
                revision="master",
                local_dir=self.local_dir,    # 关键：直接指定完整路径
            )
            logger.info(f"下载成功！路径: {os.path.abspath(final_path)}")
            self.finished_signal.emit(True, "下载成功")
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self.finished_signal.emit(False, str(e))

class UploadTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 配置区域
        config_group = QGroupBox("配置参数")
        form_layout = QFormLayout()

        # 模型 ID
        self.model_id_input = QLineEdit(DEFAULT_MODEL_ID)
        form_layout.addRow("Model ID:", self.model_id_input)

        # 本地目录
        dir_layout = QHBoxLayout()
        self.local_dir_input = QLineEdit(DEFAULT_UPLOAD_DIR)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(self.local_dir_input)
        dir_layout.addWidget(browse_btn)
        form_layout.addRow("本地模型目录:", dir_layout)

        # 访问令牌
        token_layout = QHBoxLayout()
        self.token_input = QLineEdit(DEFAULT_ACCESS_TOKEN)
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password) # 默认隐藏
        
        self.toggle_token_btn = QPushButton("显示")
        self.toggle_token_btn.setFixedWidth(50)
        self.toggle_token_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_token_btn.clicked.connect(self.toggle_token_visibility)
        
        token_layout.addWidget(self.token_input)
        token_layout.addWidget(self.toggle_token_btn)
        form_layout.addRow("Access Token:", token_layout)

        # 提交说明
        self.commit_msg_input = QLineEdit(DEFAULT_COMMIT_MSG)
        form_layout.addRow("提交说明:", self.commit_msg_input)

        config_group.setLayout(form_layout)
        layout.addWidget(config_group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始上传")
        self.start_btn.setFixedHeight(40)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_btn.clicked.connect(self.start_upload)
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)

    def toggle_token_visibility(self):
        if self.token_input.echoMode() == QLineEdit.EchoMode.Password:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_token_btn.setText("隐藏")
        else:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_token_btn.setText("显示")

    def browse_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择模型目录", self.local_dir_input.text())
        if directory:
            self.local_dir_input.setText(directory)

    def start_upload(self):
        model_id = self.model_id_input.text().strip()
        local_dir = self.local_dir_input.text().strip()
        token = self.token_input.text().strip()
        commit_msg = self.commit_msg_input.text().strip()

        if not all([model_id, local_dir, token]):
            QMessageBox.warning(self, "参数错误", "请填写完整的配置信息！")
            return

        self.start_btn.setEnabled(False)
        self.start_btn.setText("正在上传...")
        
        # 通知主窗口清空日志（如果需要）
        # 这里为了简单，我们假设主窗口会处理日志显示
        self.worker = UploadWorker(model_id, local_dir, token, commit_msg)
        self.worker.finished_signal.connect(self.on_upload_finished)
        self.worker.start()

    @pyqtSlot(bool, str)
    def on_upload_finished(self, success, message):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("开始上传")
        
        if success:
            QMessageBox.information(self, "成功", "模型上传成功！")
        else:
            QMessageBox.critical(self, "失败", f"上传失败: {message}")

class DownloadTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 配置区域
        config_group = QGroupBox("配置参数")
        form_layout = QFormLayout()

        # 模型 ID
        self.model_id_input = QLineEdit(DEFAULT_MODEL_ID)
        form_layout.addRow("Model ID:", self.model_id_input)

        # 本地目录
        dir_layout = QHBoxLayout()
        self.local_dir_input = QLineEdit(DEFAULT_DOWNLOAD_DIR)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(self.local_dir_input)
        dir_layout.addWidget(browse_btn)
        form_layout.addRow("本地存放路径:", dir_layout)

        config_group.setLayout(form_layout)
        layout.addWidget(config_group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始下载")
        self.start_btn.setFixedHeight(40)
        self.start_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.start_btn.clicked.connect(self.start_download)
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)

    def browse_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择存放目录", self.local_dir_input.text())
        if directory:
            norm_dir = os.path.normpath(directory)
            model_id = self.model_id_input.text().strip()
            if model_id:
                parts = [p for p in model_id.split('/') if p]
                if len(parts) >= 2:
                    suffix = os.path.normpath(os.path.join(*parts))
                    lower_norm = norm_dir.lower()
                    if lower_norm.endswith(suffix.lower()):
                        self.local_dir_input.setText(norm_dir)
                    else:
                        base_name = os.path.basename(norm_dir)
                        if base_name.lower() == parts[-1].lower():
                            parent = os.path.basename(os.path.dirname(norm_dir))
                            if parent.lower() != parts[-2].lower():
                                full_path = os.path.normpath(os.path.join(os.path.dirname(norm_dir), parts[-2], parts[-1]))
                                self.local_dir_input.setText(full_path)
                            else:
                                self.local_dir_input.setText(norm_dir)
                        elif base_name.lower() == parts[-2].lower():
                            full_path = os.path.normpath(os.path.join(norm_dir, parts[-1]))
                            self.local_dir_input.setText(full_path)
                        else:
                            full_path = os.path.normpath(os.path.join(norm_dir, *parts))
                            self.local_dir_input.setText(full_path)
                else:
                    model_name = parts[-1] if parts else model_id
                    if os.path.basename(norm_dir).lower() != model_name.lower():
                        full_path = os.path.normpath(os.path.join(norm_dir, model_name))
                        self.local_dir_input.setText(full_path)
                    else:
                        self.local_dir_input.setText(norm_dir)
            else:
                self.local_dir_input.setText(norm_dir)

    def start_download(self):
        model_id = self.model_id_input.text().strip()
        local_dir = self.local_dir_input.text().strip()

        if not all([model_id, local_dir]):
            QMessageBox.warning(self, "参数错误", "请填写完整的配置信息！")
            return

        self.start_btn.setEnabled(False)
        self.start_btn.setText("正在下载...")
        
        self.worker = DownloadWorker(model_id, local_dir)
        self.worker.finished_signal.connect(self.on_download_finished)
        self.worker.start()

    @pyqtSlot(bool, str)
    def on_download_finished(self, success, message):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("开始下载")
        
        if success:
            QMessageBox.information(self, "成功", "模型下载成功！")
        else:
            QMessageBox.critical(self, "失败", f"下载失败: {message}")

class ModelScopePage(QWidget):
    def __init__(self):
        super().__init__()
        
        # 初始化 UI
        self.init_ui()
        
        # 配置日志
        self.setup_logging()

    def init_ui(self):
        main_layout = QVBoxLayout(self) # 直接使用 self 作为布局父对象

        # 选项卡
        self.tabs = QTabWidget()
        self.upload_tab = UploadTab()
        self.download_tab = DownloadTab()
        
        self.tabs.addTab(self.upload_tab, "上传模型")
        self.tabs.addTab(self.download_tab, "下载模型")
        
        # 版本号显示 (右上角)
        version_label = QLabel("v.2026.03  ")
        version_label.setStyleSheet("color: #888888; font-size: 10px;")
        self.tabs.setCornerWidget(version_label, Qt.Corner.TopRightCorner)

        main_layout.addWidget(self.tabs, 0)

        # 日志输出区域 (全局共享)
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group, 1)

    def setup_logging(self):
        # 移除 loguru 默认 handler
        logger.remove()
        
        # 定义日志格式 (添加换行符以适配 insertText)
        log_format = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>\n"
        
        # 添加自定义 sink
        self.log_signal_emitter = LogSignal()
        self.log_signal_emitter.log_signal.connect(self.append_log)
        
        # loguru 输出到 sink
        logger.add(self.log_signal_emitter.write, format=log_format, level="INFO")

        # 创建流式日志捕获器
        self.stream_logger = StreamLogger(self.log_signal_emitter.log_signal)

        # 保存原始 stderr 以便发生错误时恢复或打印
        self.original_stderr = sys.__stderr__ if sys.__stderr__ else sys.stderr

        # 重定向 stderr 到 sink (捕获 tqdm 进度条)
        # 注意：不再重定向 stdout，避免捕获其他模块的 print 输出
        # sys.stdout = self.stream_logger
        sys.stderr = self.stream_logger
        
        # 尝试覆盖原始流，防止某些库直接使用 sys.__stderr__
        try:
            # sys.__stdout__ = self.stream_logger
            sys.__stderr__ = self.stream_logger
        except AttributeError:
            pass # 某些环境可能不允许修改 __stderr__

        # 配置 modelscope 的 stdlib 日志，使其输出到 GUI
        def setup_stdlib_logger(logger_name):
            target_logger = logging.getLogger(logger_name)
            target_logger.setLevel(logging.INFO)
            
            # 检查是否已存在 GUI handler
            has_gui_handler = False
            for handler in target_logger.handlers:
                if getattr(handler, 'stream', None) == self.stream_logger:
                    has_gui_handler = True
                    break
            
            if not has_gui_handler:
                # 添加一个新的 StreamHandler 指向我们的流
                handler = logging.StreamHandler(self.stream_logger)
                # 设置简单的格式
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                target_logger.addHandler(handler)

        # 仅捕获 modelscope 相关的日志，不捕获根日志 (避免显示全局启动日志)
        setup_stdlib_logger('modelscope')
        
    @pyqtSlot(str)
    def append_log(self, text):
        try:
            # 清除 ANSI 转义序列 (如 [A, [K 等)
            text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)

            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            
            # 处理进度条回车符 (覆盖当前行)
            # tqdm 可能会分多次输出，例如先输出 \r 再输出内容
            if '\r' in text:
                parts = text.split('\r')
                for i, part in enumerate(parts):
                    if i > 0: # 遇到了 \r，清除当前行
                         cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                         cursor.removeSelectedText()
                    if part:
                        cursor.insertText(part)
            else:
                cursor.insertText(text)
                
            self.log_text.setTextCursor(cursor)
            self.log_text.ensureCursorVisible()
        except Exception as e:
            # 如果日志处理出错，必须写回原始 stderr，否则会无限递归
            if self.original_stderr:
                self.original_stderr.write(f"Log Error: {e}\n")

