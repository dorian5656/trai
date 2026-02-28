#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：doc_tools_page.py
# 作者：liuhd
# 日期：2026-02-10 09:41:00
# 描述：文档工具箱页面，提供多种文档格式转换和处理功能入口

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGridLayout, QScrollArea, QFrame, 
                             QGraphicsDropShadowEffect, QMessageBox, QFileDialog, QProgressDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread, QUrl
from PyQt6.QtGui import QColor, QFont, QCursor, QDesktopServices
import os
import requests
from .config_loader import config

class DocConvertWorker(QThread):
    """通用文档转换异步工作线程"""
    finished_signal = pyqtSignal(bool, str, str)

    def __init__(self, input_path, output_path, api_key, token="", extra_data=None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.api_key = api_key
        self.token = token
        self.extra_data = extra_data or {}

    def run(self):
        opened_files = []
        try:
            # 1. 获取 API 地址
            url = config.get("doc_tools", {}).get(self.api_key, "")
            if not url:
                self.finished_signal.emit(False, f"配置错误: 未找到 {self.api_key}", "")
                return

            # 2. 上传文件并转换
            files_to_send = []
            if isinstance(self.input_path, list):
                # 多文件上传 (如图片转PDF)
                # 注意：这里假设 API 接收多个 'file' 字段，或者 'files' 字段
                # 根据 curl 示例 -F 'file=@...'，我们使用 'file' 作为 key，requests 会自动处理多个同名 key
                for path in self.input_path:
                    f = open(path, 'rb')
                    opened_files.append(f)
                    files_to_send.append(('file', f))
            else:
                # 单文件上传
                f = open(self.input_path, 'rb')
                opened_files.append(f)
                files_to_send = {'file': f}

            headers = {'accept': 'application/json'} 
            if self.token:
                headers['Authorization'] = f"Bearer {self.token}"
            
            # 发起转换请求
            response = requests.post(url, files=files_to_send, data=self.extra_data, headers=headers, timeout=120)
            
            if response.status_code != 200:
                self.finished_signal.emit(False, f"服务器返回错误: {response.status_code}", "")
                return

            res_json = response.json()
            if res_json.get("code") != 200:
                self.finished_signal.emit(False, f"转换失败: {res_json.get('msg', '未知错误')}", "")
                return

            # 3. 解析下载链接
            data = res_json.get("data")
            download_url = ""
            if isinstance(data, str):
                download_url = data
            elif isinstance(data, dict):
                download_url = data.get("url") or data.get("download_url")

            if not download_url:
                self.finished_signal.emit(False, "服务端未返回有效的下载链接", "")
                return

            # 4. 下载文件
            # 如果是相对路径或局域网路径，可能需要处理 base_url，但通常 API 返回完整 URL
            # 简单处理：直接下载
            file_res = requests.get(download_url, stream=True, timeout=60)
            if file_res.status_code == 200:
                with open(self.output_path, 'wb') as f:
                    for chunk in file_res.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.finished_signal.emit(True, f"转换成功！已保存至: {self.output_path}", self.output_path)
            else:
                self.finished_signal.emit(False, f"下载结果文件失败: {file_res.status_code}", "")

        except Exception as e:
            self.finished_signal.emit(False, f"发生异常: {str(e)}", "")
        finally:
            # 关闭所有打开的文件
            for f in opened_files:
                try:
                    f.close()
                except:
                    pass

class DocToolCard(QFrame):
    """文档工具功能卡片"""
    clicked = pyqtSignal(str)  # 发射功能ID

    def __init__(self, tool_id, title, icon_emoji, description="", parent=None):
        super().__init__(parent)
        self.tool_id = tool_id
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(200, 130)
        
        # 卡片样式
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
            QFrame:hover {
                background-color: #f9f9f9;
                border: 1px solid #2196F3;
            }
        """)
        
        # 添加阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)
        
        # 布局
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        
        # 图标
        self.icon_label = QLabel(icon_emoji)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 尝试使用 Segoe UI Emoji 字体以获得更好的 emoji 显示效果
        font = QFont("Segoe UI Emoji", 32)
        self.icon_label.setFont(font)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.icon_label)
        
        # 标题
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #333; background: transparent; border: none;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        
        # 描述 (可选，暂不显示以保持简洁，或作为tooltip)
        if description:
            self.setToolTip(description)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.tool_id)
        super().mousePressEvent(event)

class DocToolsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.token = ""
        self.init_ui()

    def set_auth_token(self, token):
        """设置认证 Token"""
        self.token = token

    def init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. 顶部标题栏
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e0e0e0;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 0, 30, 0)
        
        title_label = QLabel("📚 文档工具箱")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        main_layout.addWidget(header)
        
        # 2. 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("background-color: #f5f7fa;")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(50, 20, 50, 20)
        content_layout.setSpacing(20)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_widget.setMaximumWidth(1100)
        
        # --- 功能分组 ---
        
        # 分组1: 转 PDF (Import to PDF)
        self.add_section(content_layout, "转为 PDF", [
            ("md2pdf", "Markdown 转 PDF", "📝", "将 Markdown 文档转换为 PDF"),
            ("word2pdf", "Word 转 PDF", "📘", "将 Word 文档 (.doc, .docx) 转换为 PDF"),
            ("img2pdf", "图片 转 PDF", "🖼️", "将多张图片合并转换为 PDF"),
            ("excel2pdf", "Excel 转 PDF", "📊", "将 Excel 表格转换为 PDF"),
            ("ppt2pdf", "PPT 转 PDF", "📽️", "将 PowerPoint 演示文稿转换为 PDF"),
            ("html2pdf", "HTML 转 PDF", "🌐", "将网页或 HTML 文件转换为 PDF"),
            ("svg2pdf", "SVG 转 PDF", "📐", "将 SVG 矢量图转换为 PDF"),
            ("ofd2pdf", "OFD 转 PDF", "📑", "将 OFD 文档转换为 PDF"),
        ])
        
        # 分组2: PDF 转换与处理 (Export & Process)
        self.add_section(content_layout, "PDF 转换与处理", [
            ("pdf2img", "PDF 转图片", "🖼️", "将 PDF 页面转换为图片"),
            ("pdf2word", "PDF 转 Word", "📘", "将 PDF 转换为 Word 文档"),
            ("pdf2ppt", "PDF 转 PPT", "📽️", "将 PDF 转换为 PowerPoint 演示文稿"),
            ("pdf2pdfa", "PDF 转 PDF/A", "🅰️", "将 PDF 转换为归档标准 PDF/A 格式"),
            ("pdf_unlock", "PDF 解除限制", "🔓", "移除 PDF 的编辑和打印限制"),
            ("pdf_longimg", "PDF 转长图", "📜", "将 PDF 所有页面拼接为一张长图"),
        ])
        
        # 分组3: 其他工具 (Others)
        self.add_section(content_layout, "其他工具", [
            ("ofd2img", "OFD 转图片", "🖼️", "将 OFD 文档转换为图片"),
            ("img_convert", "图片格式转换", "🔄", "支持多种图片格式互转 (jpg, png, webp 等)"),
            ("ebook_convert", "电子书格式转换", "📚", "支持 epub, mobi, azw3, pdf 等格式互转"),
        ], center=False)
        
        content_layout.addStretch() # 底部弹簧

        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addStretch()
        wrapper_layout.addWidget(content_widget)
        wrapper_layout.addStretch()

        scroll_area.setWidget(wrapper)
        main_layout.addWidget(scroll_area)

    def add_section(self, parent_layout, title, tools, center=True):
        """添加一个功能分组"""
        # 分组标题
        section_label = QLabel(title)
        section_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #555; margin-bottom: 10px;")
        parent_layout.addWidget(section_label)
        
        # 网格布局容器
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(24)
        if center:
            grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        else:
            grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # 添加卡片
        col_count = 4 # 每行4列
        for i, (tid, name, icon, desc) in enumerate(tools):
            card = DocToolCard(tid, name, icon, desc)
            card.clicked.connect(self.on_tool_clicked)
            row = i // col_count
            col = i % col_count
            grid_layout.addWidget(card, row, col)
            
        parent_layout.addWidget(grid_widget)

    def on_tool_clicked(self, tool_id):
        """处理工具点击事件"""
        if tool_id == "md2pdf":
            self.handle_md2pdf()
            return
        elif tool_id == "word2pdf":
            self.handle_word2pdf()
            return
        elif tool_id == "img2pdf":
            self.handle_img2pdf()
            return
        elif tool_id == "excel2pdf":
            self.handle_excel2pdf()
            return
        elif tool_id == "ppt2pdf":
            self.handle_ppt2pdf()
            return
        elif tool_id == "html2pdf":
            self.handle_html2pdf()
            return
        elif tool_id == "svg2pdf":
            self.handle_svg2pdf()
            return
        elif tool_id == "ofd2pdf":
            self.handle_ofd2pdf()
            return
        elif tool_id == "ofd2img":
            self.handle_ofd2img()
            return
        elif tool_id == "pdf2img":
            self.handle_pdf2img()
            return
        elif tool_id == "pdf2word":
            self.handle_pdf2word()
            return
        elif tool_id == "pdf2ppt":
            self.handle_pdf2ppt()
            return
        elif tool_id == "pdf2pdfa":
            self.handle_pdf2pdfa()
            return
        elif tool_id == "pdf_unlock":
            self.handle_pdf_unlock()
            return
        elif tool_id == "pdf_longimg":
            self.handle_pdf_longimg()
            return
        elif tool_id == "img_convert":
            self.handle_img_convert()
            return
        elif tool_id == "ebook_convert":
            self.handle_ebook_convert()
            return

        # 其他工具暂未实现
        tools_map = {
            "md2pdf": "Markdown 转 PDF", "word2pdf": "Word 转 PDF", "img2pdf": "图片 转 PDF",
            "excel2pdf": "Excel 转 PDF", "ppt2pdf": "PPT 转 PDF", "html2pdf": "HTML 转 PDF",
            "svg2pdf": "SVG 转 PDF", "ofd2pdf": "OFD 转 PDF", "pdf2img": "PDF 转图片",
            "pdf2word": "PDF 转 Word", "pdf2ppt": "PDF 转 PPT", "pdf2pdfa": "PDF 转 PDF/A",
            "pdf_unlock": "PDF 解除限制", "pdf_longimg": "PDF 转长图", "ofd2img": "OFD 转图片",
            "img_convert": "图片格式转换", "ebook_convert": "电子书格式转换"
        }
        name = tools_map.get(tool_id, tool_id)
        QMessageBox.information(self, "功能开发中", f"【{name}】功能即将上线，敬请期待！\n\nAPI 接口准备中...")

    def handle_md2pdf(self):
        """处理 Markdown 转 PDF 逻辑"""
        # 1. 选择 Markdown 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 Markdown 文件", "", "Markdown Files (*.md);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "md2pdf_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_ebook_convert(self):
        """处理 电子书格式转换 逻辑"""
        # 1. 选择 电子书 文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择电子书文件", 
            "", 
            "E-books (*.epub *.mobi *.azw3 *.pdf *.txt *.docx *.djvu *.fb2 *.cbz *.cbr);;All Files (*)"
        )
        if not file_path:
            return

        # 2. 选择保存路径 (根据扩展名确定目标格式)
        default_name = os.path.splitext(os.path.basename(file_path))[0]
        save_path, filter_str = QFileDialog.getSaveFileName(
            self, 
            "保存电子书 (选择格式)", 
            default_name, 
            "EPUB Files (*.epub);;MOBI Files (*.mobi);;AZW3 Files (*.azw3);;PDF Files (*.pdf);;TXT Files (*.txt);;DOCX Files (*.docx)"
        )
        if not save_path:
            return
            
        # 3. 解析目标格式
        _, ext = os.path.splitext(save_path)
        target_fmt = ext.lower().replace('.', '')
        if not target_fmt:
            QMessageBox.warning(self, "错误", "无法识别目标格式，请确保文件名包含扩展名")
            return
            
        # 4. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 5. 启动后台线程
        self.worker = DocConvertWorker(
            file_path, 
            save_path, 
            "ebook_convert_url", 
            self.token, 
            extra_data={"target_fmt": target_fmt}
        )
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()
        
    def handle_word2pdf(self):
        """处理 Word 转 PDF 逻辑"""
        # 1. 选择 Word 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 Word 文件", "", "Word Files (*.docx *.doc);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "word2pdf_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_img2pdf(self):
        """处理 图片 转 PDF 逻辑"""
        # 1. 选择 图片 文件 (支持多选)
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片文件", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)")
        if not files:
            return

        # 2. 选择保存路径
        default_name = "combined_images.pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(files, save_path, "img2pdf_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_excel2pdf(self):
        """处理 Excel 转 PDF 逻辑"""
        # 1. 选择 Excel 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 Excel 文件", "", "Excel Files (*.xlsx *.xls);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "excel2pdf_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_ppt2pdf(self):
        """处理 PPT 转 PDF 逻辑"""
        # 1. 选择 PPT 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 PPT 文件", "", "PPT Files (*.pptx *.ppt);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "ppt2pdf_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_html2pdf(self):
        """处理 HTML 转 PDF 逻辑"""
        # 1. 选择 HTML 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 HTML 文件", "", "HTML Files (*.html *.htm);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "html2pdf_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_svg2pdf(self):
        """处理 SVG 转 PDF 逻辑"""
        # 1. 选择 SVG 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 SVG 文件", "", "SVG Files (*.svg);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "svg2pdf_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_ofd2pdf(self):
        """处理 OFD 转 PDF 逻辑"""
        # 1. 选择 OFD 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 OFD 文件", "", "OFD Files (*.ofd);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "ofd2pdf_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_ofd2img(self):
        """处理 OFD 转图片逻辑"""
        # 1. 选择 OFD 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 OFD 文件", "", "OFD Files (*.ofd);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径 (默认为zip，因为 OFD 可能是多页)
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".zip"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存图片压缩包", default_name, "ZIP Files (*.zip)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "ofd2img_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_pdf2img(self):
        """处理 PDF 转图片逻辑"""
        # 1. 选择 PDF 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 文件", "", "PDF Files (*.pdf);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径 (默认为zip)
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".zip"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存图片压缩包", default_name, "ZIP Files (*.zip)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "pdf2img_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_pdf2word(self):
        """处理 PDF 转 Word 逻辑"""
        # 1. 选择 PDF 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 文件", "", "PDF Files (*.pdf);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".docx"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 Word 文档", default_name, "Word Files (*.docx)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "pdf2word_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_pdf2ppt(self):
        """处理 PDF 转 PPT 逻辑"""
        # 1. 选择 PDF 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 文件", "", "PDF Files (*.pdf);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".pptx"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PPT 文档", default_name, "PPT Files (*.pptx)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "pdf2ppt_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_pdf2pdfa(self):
        """处理 PDF 转 PDF/A 逻辑"""
        # 1. 选择 PDF 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 文件", "", "PDF Files (*.pdf);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + "_pdfa.pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存 PDF/A 文档", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "pdf2pdfa_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_pdf_unlock(self):
        """处理 PDF 解除限制 逻辑"""
        # 1. 选择 PDF 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 文件", "", "PDF Files (*.pdf);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + "_unlocked.pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存解锁后的 PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "pdf_unlock_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def handle_pdf_longimg(self):
        """处理 PDF 转长图 逻辑"""
        # 1. 选择 PDF 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 文件", "", "PDF Files (*.pdf);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径
        default_name = os.path.splitext(os.path.basename(file_path))[0] + ".png"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存长图", default_name, "Image Files (*.png)")
        if not save_path:
            return
            
        # 3. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 4. 启动后台线程
        self.worker = DocConvertWorker(file_path, save_path, "pdf_longimg_url", self.token)
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()

    def on_convert_finished(self, success, msg, file_path=""):
        """转换完成回调"""
        self.progress.close()
        if success:
            # 自定义成功对话框
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("成功")
            msg_box.setText(msg)
            msg_box.setIcon(QMessageBox.Icon.Information)
            
            # 添加按钮
            open_file_btn = msg_box.addButton("打开文件", QMessageBox.ButtonRole.ActionRole)
            open_dir_btn = msg_box.addButton("打开所在目录", QMessageBox.ButtonRole.ActionRole)
            close_btn = msg_box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
            
            msg_box.exec()
            
            clicked_button = msg_box.clickedButton()
            if clicked_button == open_file_btn:
                if file_path and os.path.exists(file_path):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
            elif clicked_button == open_dir_btn:
                if file_path:
                    folder_path = os.path.dirname(file_path)
                    if os.path.exists(folder_path):
                        QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
        else:
            QMessageBox.warning(self, "失败", msg)

    def handle_img_convert(self):
        """处理 图片格式转换 逻辑"""
        # 1. 选择 图片 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片文件", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.ico);;All Files (*)")
        if not file_path:
            return

        # 2. 选择保存路径 (根据扩展名确定目标格式)
        default_name = os.path.splitext(os.path.basename(file_path))[0]
        save_path, filter_str = QFileDialog.getSaveFileName(
            self, 
            "保存图片 (选择格式)", 
            default_name, 
            "PNG Files (*.png);;JPG Files (*.jpg);;JPEG Files (*.jpeg);;WEBP Files (*.webp);;BMP Files (*.bmp);;TIFF Files (*.tiff);;ICO Files (*.ico)"
        )
        if not save_path:
            return
            
        # 3. 解析目标格式
        _, ext = os.path.splitext(save_path)
        target_fmt = ext.lower().replace('.', '')
        if not target_fmt:
            QMessageBox.warning(self, "错误", "无法识别目标格式，请确保文件名包含扩展名")
            return
            
        # 4. 显示进度条
        self.progress = QProgressDialog("正在上传并转换，请稍候...", "取消", 0, 0, self)
        self.progress.setWindowTitle("处理中")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()
        
        # 5. 启动后台线程
        self.worker = DocConvertWorker(
            file_path, 
            save_path, 
            "img_convert_url", 
            self.token, 
            extra_data={"target_fmt": target_fmt}
        )
        self.worker.finished_signal.connect(self.on_convert_finished)
        self.worker.start()
