#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：image_tools_page.py
# 作者：liuhd
# 日期：2026-02-24 11:25:00
# 描述：图像工具箱页面，提供图片处理功能，如压缩、转换、调整尺寸等。

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
    QCheckBox,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QDesktopServices
import requests
import os
from .config_loader import config


class ImageDownloadWorker(QThread):
    """通用的文件下载工作线程"""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=60)
            if response.status_code == 200:
                # 确保目录存在
                os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
                with open(self.save_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.finished_signal.emit(True, self.save_path)
            else:
                self.finished_signal.emit(False, f"下载失败: HTTP {response.status_code}")
        except Exception as e:
            self.finished_signal.emit(False, f"下载发生异常: {str(e)}")


class ImageConvertWorker(QThread):
    finished_signal = pyqtSignal(bool, str, dict)

    def __init__(self, file_path, api_url, target_format, quality, token=""):
        super().__init__()
        self.file_path = file_path
        self.api_url = api_url
        self.target_format = target_format
        self.quality = quality
        self.token = token or ""

    def run(self):
        f = None
        try:
            f = open(self.file_path, "rb")
            files = {"file": f}
            data = {
                "format": self.target_format,
                "quality": str(self.quality),
            }
            headers = {"accept": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                headers=headers,
                timeout=120,
            )
            if response.status_code != 200:
                self.finished_signal.emit(False, f"服务器返回错误: {response.status_code}", {})
                return
            res_json = response.json()
            if res_json.get("code") != 200:
                msg = res_json.get("msg", "图片格式转换失败")
                self.finished_signal.emit(False, msg, {})
                return
            data_json = res_json.get("data") or {}
            msg = res_json.get("msg", "图片格式转换成功")
            self.finished_signal.emit(True, msg, data_json)
        except Exception as e:
            self.finished_signal.emit(False, f"发生异常: {str(e)}", {})
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass


class ImageIcoWorker(QThread):
    finished_signal = pyqtSignal(bool, str, dict)

    def __init__(self, file_path, api_url, sizes, token=""):
        super().__init__()
        self.file_path = file_path
        self.api_url = api_url
        self.sizes = sizes
        self.token = token or ""

    def run(self):
        f = None
        try:
            f = open(self.file_path, "rb")
            files = {"file": f}
            data = {"sizes": self.sizes}
            headers = {"accept": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                headers=headers,
                timeout=120,
            )
            if response.status_code != 200:
                self.finished_signal.emit(False, f"服务器返回错误: {response.status_code}", {})
                return
            res_json = response.json()
            if res_json.get("code") != 200:
                msg = res_json.get("msg", "图片转 ICO 失败")
                self.finished_signal.emit(False, msg, {})
                return
            data_json = res_json.get("data") or {}
            msg = res_json.get("msg", "图片转 ICO 成功")
            self.finished_signal.emit(True, msg, data_json)
        except Exception as e:
            self.finished_signal.emit(False, f"发生异常: {str(e)}", {})
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass


class ImageCompressWorker(QThread):
    finished_signal = pyqtSignal(bool, str, dict)

    def __init__(self, file_path, api_url, target_mb, token=""):
        super().__init__()
        self.file_path = file_path
        self.api_url = api_url
        self.target_mb = target_mb
        self.token = token or ""

    def run(self):
        f = None
        try:
            f = open(self.file_path, "rb")
            files = {"file": f}
            data = {"target_mb": str(self.target_mb)}
            headers = {"accept": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                headers=headers,
                timeout=120,
            )
            if response.status_code != 200:
                self.finished_signal.emit(False, f"服务器返回错误: {response.status_code}", {})
                return
            res_json = response.json()
            if res_json.get("code") != 200:
                msg = res_json.get("msg", "图片压缩失败")
                self.finished_signal.emit(False, msg, {})
                return
            data_json = res_json.get("data") or {}
            msg = res_json.get("msg", "图片压缩成功")
            self.finished_signal.emit(True, msg, data_json)
        except Exception as e:
            self.finished_signal.emit(False, f"发生异常: {str(e)}", {})
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass


class ImageResizeWorker(QThread):
    finished_signal = pyqtSignal(bool, str, dict)

    def __init__(self, file_path, api_url, width=None, height=None, token=""):
        super().__init__()
        self.file_path = file_path
        self.api_url = api_url
        self.width = width
        self.height = height
        self.token = token or ""

    def run(self):
        f = None
        try:
            f = open(self.file_path, "rb")
            files = {"file": f}
            data = {}
            if self.width is not None:
                data["width"] = str(self.width)
            if self.height is not None:
                data["height"] = str(self.height)

            headers = {"accept": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                headers=headers,
                timeout=120,
            )

            if response.status_code != 200:
                self.finished_signal.emit(False, f"服务器返回错误: {response.status_code}", {})
                return

            res_json = response.json()
            if res_json.get("code") != 200:
                msg = res_json.get("msg", "图片尺寸调整失败")
                self.finished_signal.emit(False, msg, {})
                return

            data_json = res_json.get("data") or {}
            msg = res_json.get("msg", "图片尺寸调整成功")
            self.finished_signal.emit(True, msg, data_json)
        except Exception as e:
            self.finished_signal.emit(False, f"发生异常: {str(e)}", {})
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass


class ImageToolsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.token = ""
        self.selected_image_path = ""
        self._init_ui()

    def set_auth_token(self, token: str) -> None:
        self.token = token or ""

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet(
            "background-color: #ffffff; border-bottom: 1px solid #e0e0e0;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 0, 30, 0)

        title_label = QLabel("🖼️ 图像工具箱")
        title_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #333333;"
        )
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addWidget(header)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(30, 20, 30, 20)
        content_layout.setSpacing(24)

        left_panel = QFrame()
        left_panel.setMinimumWidth(320)
        left_panel.setStyleSheet(
            "QFrame { background-color: #ffffff; border-radius: 8px; border: 1px solid #e0e0e0; }"
        )
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 16, 20, 16)
        left_layout.setSpacing(12)

        source_title = QLabel("源图片")
        source_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #444444; border: none;")
        left_layout.addWidget(source_title)

        select_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("请选择本地图片文件")
        select_row.addWidget(self.path_edit)

        select_btn = QPushButton("选择图片")
        select_btn.clicked.connect(self._choose_image)
        select_row.addWidget(select_btn)
        left_layout.addLayout(select_row)

        self.preview_label = QLabel("预览区")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(220)
        self.preview_label.setStyleSheet(
            "background-color: #f5f7fa; border-radius: 6px; border: 1px dashed #cccccc; color: #aaaaaa;"
        )
        left_layout.addWidget(self.preview_label)
        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QGridLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)

        format_card = self._create_format_convert_card()
        ico_card = self._create_ico_convert_card()
        compress_card = self._create_compress_card()
        resize_card = self._create_resize_card()

        right_layout.addWidget(format_card, 0, 0)
        right_layout.addWidget(ico_card, 0, 1)
        right_layout.addWidget(compress_card, 1, 0)
        right_layout.addWidget(resize_card, 1, 1)

        content_layout.addWidget(left_panel, stretch=2)
        content_layout.addWidget(right_panel, stretch=3)

        main_layout.addWidget(content)

    def _create_card_base(self, title: str, subtitle: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            """
QFrame {
    background-color: #ffffff;
    border-radius: 10px;
    border: 1px solid #e0e0e0;
}
QFrame:hover {
    border: 1px solid #2196F3;
}
"""
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #333333; border: none;")
        layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("font-size: 12px; color: #888888; border: none;")
        layout.addWidget(subtitle_label)

        return card

    def _create_format_convert_card(self) -> QFrame:
        card = self._create_card_base("图片格式转换", "将图片转换为指定格式")
        layout = card.layout()

        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel("目标格式")
        label.setStyleSheet("font-size: 12px; color: #555555; border: none;")
        row.addWidget(label)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG", "PNG", "WEBP"])
        row.addWidget(self.format_combo, stretch=1)

        layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(10)

        quality_label = QLabel("图片质量")
        quality_label.setStyleSheet("font-size: 12px; color: #555555; border: none;")
        row2.addWidget(quality_label)

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(85)
        self.quality_spin.setSuffix(" %")
        row2.addWidget(self.quality_spin, stretch=1)

        layout.addLayout(row2)

        action_btn = QPushButton("开始转换")
        action_btn.clicked.connect(self._on_format_convert_clicked)
        layout.addWidget(action_btn)

        self.format_convert_btn = action_btn

        layout.addStretch()
        return card

    def _create_ico_convert_card(self) -> QFrame:
        card = self._create_card_base("图片转 ICO", "生成应用图标文件")
        layout = card.layout()

        size_row = QHBoxLayout()
        size_row.setSpacing(10)

        size_label = QLabel("图标尺寸")
        size_label.setStyleSheet("font-size: 12px; color: #555555; border: none;")
        size_row.addWidget(size_label)

        self.ico_size_spin = QSpinBox()
        self.ico_size_spin.setRange(16, 512)
        self.ico_size_spin.setValue(256)
        self.ico_size_spin.setSuffix(" px")
        size_row.addWidget(self.ico_size_spin, stretch=1)

        layout.addLayout(size_row)

        btn = QPushButton("生成 ICO")
        btn.clicked.connect(self._on_ico_convert_clicked)
        layout.addWidget(btn)

        self.ico_convert_btn = btn

        layout.addStretch()
        return card

    def _create_compress_card(self) -> QFrame:
        card = self._create_card_base("图片压缩", "压缩到指定文件大小")
        layout = card.layout()

        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel("目标大小")
        label.setStyleSheet("font-size: 12px; color: #555555; border: none;")
        row.addWidget(label)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 1024)
        self.size_spin.setValue(3)
        self.size_spin.setSuffix(" MB")
        row.addWidget(self.size_spin, stretch=1)

        self.keep_size_check = QCheckBox("尽量保持分辨率")
        self.keep_size_check.setChecked(True)
        row.addWidget(self.keep_size_check)

        layout.addLayout(row)

        btn = QPushButton("开始压缩")
        btn.clicked.connect(self._on_compress_clicked)
        layout.addWidget(btn)

        self.compress_btn = btn

        layout.addStretch()
        return card

    def _create_resize_card(self) -> QFrame:
        card = self._create_card_base("尺寸调整", "修改图片宽高尺寸")
        layout = card.layout()

        row1 = QHBoxLayout()
        row1.setSpacing(10)

        width_label = QLabel("宽度")
        width_label.setStyleSheet("font-size: 12px; color: #555555; border: none;")
        row1.addWidget(width_label)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(16, 10000)
        self.width_spin.setValue(800)
        self.width_spin.setSuffix(" px")
        row1.addWidget(self.width_spin, stretch=1)

        height_label = QLabel("高度")
        height_label.setStyleSheet("font-size: 12px; color: #555555; border: none;")
        row1.addWidget(height_label)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(16, 10000)
        self.height_spin.setValue(600)
        self.height_spin.setSuffix(" px")
        row1.addWidget(self.height_spin, stretch=1)

        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)

        self.keep_ratio_check = QCheckBox("保持比例")
        self.keep_ratio_check.setChecked(True)
        row2.addWidget(self.keep_ratio_check)

        row2.addStretch()
        layout.addLayout(row2)

        btn = QPushButton("调整尺寸")
        btn.clicked.connect(self._on_resize_clicked)
        layout.addWidget(btn)

        self.resize_btn = btn

        layout.addStretch()
        return card

    def _ensure_image_selected(self) -> bool:
        if not self.selected_image_path:
            QMessageBox.warning(self, "提示", "请先选择图片文件")
            return False
        return True

    def _choose_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.ico);;所有文件 (*.*)",
        )
        if not file_path:
            return
        self.selected_image_path = file_path
        self.path_edit.setText(file_path)
        self._update_preview(file_path)

    def _update_preview(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview_label.setText("无法加载图片预览")
            self.preview_label.setPixmap(QPixmap())
            return
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.selected_image_path:
            self._update_preview(self.selected_image_path)

    def _show_placeholder_message(self, feature_name: str) -> None:
        QMessageBox.information(
            self,
            "功能开发中",
            f"{feature_name} 将通过服务端 API 实现，当前为界面预览。",
        )

    def _on_format_convert_clicked(self) -> None:
        if not self._ensure_image_selected():
            return
        api_url = ""
        try:
            api_url = config.get("image_tools", {}).get("convert_url", "")
        except Exception:
            api_url = ""
        if not api_url:
            QMessageBox.warning(self, "错误", "配置错误: 未找到图像格式转换接口地址")
            return
        target_format = self.format_combo.currentText()
        quality = self.quality_spin.value()
        if hasattr(self, "format_convert_btn"):
            self.format_convert_btn.setEnabled(False)
            self.format_convert_btn.setText("正在转换...")
        self.convert_api_url = api_url
        self.convert_worker = ImageConvertWorker(
            self.selected_image_path,
            api_url,
            target_format,
            quality,
            self.token,
        )
        self.convert_worker.finished_signal.connect(self._on_format_convert_finished)
        self.convert_worker.start()

    def _on_format_convert_finished(self, success: bool, message: str, data: dict) -> None:
        if hasattr(self, "format_convert_btn"):
            self.format_convert_btn.setEnabled(True)
            self.format_convert_btn.setText("开始转换")
        if not success:
            QMessageBox.warning(self, "转换失败", message or "图片格式转换失败")
            return
        detail_parts = []
        if isinstance(data, dict):
            fmt = data.get("format")
            width = data.get("width")
            height = data.get("height")
            size = data.get("size")
            if fmt:
                detail_parts.append(f"格式: {fmt}")
            if width and height:
                detail_parts.append(f"分辨率: {width} x {height}")
            if size:
                detail_parts.append(f"文件大小: {size} 字节")
        detail_text = "\n".join(detail_parts) if detail_parts else ""
        final_msg = message
        if detail_text:
            final_msg = f"{message}\n\n{detail_text}"
        QMessageBox.information(self, "转换成功", final_msg)

        # 自动触发下载
        self._trigger_download(data, self.convert_api_url)

    def _on_ico_convert_clicked(self) -> None:
        if not self._ensure_image_selected():
            return
        api_url = ""
        try:
            api_url = config.get("image_tools", {}).get("image2ico_url", "")
        except Exception:
            api_url = ""
        if not api_url:
            QMessageBox.warning(self, "错误", "配置错误: 未找到图片转 ICO 接口地址")
            return
        size_value = self.ico_size_spin.value()
        sizes = str(size_value)
        if hasattr(self, "ico_convert_btn"):
            self.ico_convert_btn.setEnabled(False)
            self.ico_convert_btn.setText("正在生成...")
        self.ico_api_url = api_url
        self.ico_worker = ImageIcoWorker(
            self.selected_image_path,
            api_url,
            sizes,
            self.token,
        )
        self.ico_worker.finished_signal.connect(self._on_ico_convert_finished)
        self.ico_worker.start()

    def _on_ico_convert_finished(self, success: bool, message: str, data: dict) -> None:
        if hasattr(self, "ico_convert_btn"):
            self.ico_convert_btn.setEnabled(True)
            self.ico_convert_btn.setText("生成 ICO")
        if not success:
            QMessageBox.warning(self, "生成失败", message or "图片转 ICO 失败")
            return
        detail_parts = []
        if isinstance(data, dict):
            sizes = data.get("sizes") or data.get("size_list")
            fmt = data.get("format")
            if sizes:
                detail_parts.append(f"包含尺寸: {sizes}")
            if fmt:
                detail_parts.append(f"格式: {fmt}")
        detail_text = "\n".join(detail_parts) if detail_parts else ""
        final_msg = message
        if detail_text:
            final_msg = f"{message}\n\n{detail_text}"
        QMessageBox.information(self, "生成成功", final_msg)

        # 自动触发下载
        self._trigger_download(data, self.ico_api_url)

    def _on_compress_clicked(self) -> None:
        if not self._ensure_image_selected():
            return
        api_url = ""
        try:
            api_url = config.get("image_tools", {}).get("compress_url", "")
        except Exception:
            api_url = ""
        if not api_url:
            QMessageBox.warning(self, "错误", "配置错误: 未找到图片压缩接口地址")
            return
        target_mb = self.size_spin.value()
        if target_mb <= 0:
            QMessageBox.warning(self, "提示", "目标大小必须大于 0 MB")
            return
        if hasattr(self, "compress_btn"):
            self.compress_btn.setEnabled(False)
            self.compress_btn.setText("正在压缩...")
        self.compress_api_url = api_url
        self.compress_worker = ImageCompressWorker(
            self.selected_image_path,
            api_url,
            target_mb,
            self.token,
        )
        self.compress_worker.finished_signal.connect(self._on_compress_finished)
        self.compress_worker.start()

    def _on_compress_finished(self, success: bool, message: str, data: dict) -> None:
        if hasattr(self, "compress_btn"):
            self.compress_btn.setEnabled(True)
            self.compress_btn.setText("开始压缩")
        if not success:
            QMessageBox.warning(self, "压缩失败", message or "图片压缩失败")
            return
        detail_parts = []
        if isinstance(data, dict):
            width = data.get("width")
            height = data.get("height")
            size = data.get("size")
            fmt = data.get("format")
            if fmt:
                detail_parts.append(f"格式: {fmt}")
            if width and height:
                detail_parts.append(f"分辨率: {width} x {height}")
            if size:
                detail_parts.append(f"文件大小: {size} 字节")
        detail_text = "\n".join(detail_parts) if detail_parts else ""
        final_msg = message
        if detail_text:
            final_msg = f"{message}\n\n{detail_text}"
        QMessageBox.information(self, "压缩成功", final_msg)

        # 自动触发下载
        self._trigger_download(data, self.compress_api_url)

    def _on_resize_clicked(self) -> None:
        if not self._ensure_image_selected():
            return
        api_url = ""
        try:
            api_url = config.get("image_tools", {}).get("resize_url", "")
        except Exception:
            api_url = ""
        if not api_url:
            QMessageBox.warning(self, "错误", "配置错误: 未找到图片尺寸调整接口地址")
            return

        width = self.width_spin.value()
        height = self.height_spin.value()
        
        # 如果勾选了保持比例，根据 API 逻辑，我们可以只传一个参数。
        # 这里为了符合 API 示例，我们传两个值。
        # 如果后端支持只传一个参数来保持比例，可以在这里做逻辑分支。
        
        if hasattr(self, "resize_btn"):
            self.resize_btn.setEnabled(False)
            self.resize_btn.setText("正在调整...")

        self.resize_api_url = api_url
        self.resize_worker = ImageResizeWorker(
            self.selected_image_path,
            api_url,
            width=width,
            height=height,
            token=self.token,
        )
        self.resize_worker.finished_signal.connect(self._on_resize_finished)
        self.resize_worker.start()

    def _on_resize_finished(self, success: bool, message: str, data: dict) -> None:
        if hasattr(self, "resize_btn"):
            self.resize_btn.setEnabled(True)
            self.resize_btn.setText("调整尺寸")
        if not success:
            QMessageBox.warning(self, "调整失败", message or "图片尺寸调整失败")
            return
        
        detail_parts = []
        if isinstance(data, dict):
            width = data.get("width")
            height = data.get("height")
            size = data.get("size")
            fmt = data.get("format")
            if fmt:
                detail_parts.append(f"格式: {fmt}")
            if width and height:
                detail_parts.append(f"分辨率: {width} x {height}")
            if size:
                detail_parts.append(f"文件大小: {size} 字节")
        
        detail_text = "\n".join(detail_parts) if detail_parts else ""
        final_msg = message
        if detail_text:
            final_msg = f"{message}\n\n{detail_text}"
        QMessageBox.information(self, "调整成功", final_msg)
        
        # 自动触发下载
        self._trigger_download(data, self.resize_api_url)

    def _trigger_download(self, data: dict, api_url: str) -> None:
        """根据 API 返回的数据触发文件下载"""
        if not isinstance(data, dict):
            return
            
        rel_path = data.get("relative_path")
        if not rel_path:
            return
            
        # 1. 拼凑下载 URL
        base_url = ""
        if api_url:
            parts = api_url.split("/api_trai", 1)
            base_url = parts[0]
        if not base_url:
            return
            
        download_url = f"{base_url}/{rel_path.lstrip('/')}"
        
        # 2. 确定保存路径 (当前程序同级目录下的 downloads/image_tools 文件夹)
        current_dir = os.getcwd()
        save_dir = os.path.join(current_dir, "downloads", "image_tools")
        filename = os.path.basename(rel_path)
        save_path = os.path.join(save_dir, filename)
        
        # 3. 启动下载线程
        self.download_worker = ImageDownloadWorker(download_url, save_path)
        self.download_worker.finished_signal.connect(self._on_download_finished)
        self.download_worker.start()

    def _on_download_finished(self, success: bool, path_or_error: str) -> None:
        """下载完成回调"""
        if success:
            reply = QMessageBox.question(
                self,
                "下载完成",
                f"处理后的图片已自动下载至：\n{path_or_error}\n\n是否立即打开文件夹查看？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # 打开文件夹并选中文件 (Windows)
                import subprocess
                norm_path = os.path.normpath(path_or_error)
                subprocess.Popen(f'explorer /select,"{norm_path}"')
        else:
            QMessageBox.warning(self, "下载失败", path_or_error)

