#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：doc_tools_page.py
# 作者：liuhd
# 日期：2026-02-10 09:41:00
# 描述：文档工具箱页面，提供多种文档格式转换和处理功能入口

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGridLayout, QScrollArea, QFrame, 
                             QGraphicsDropShadowEffect, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QFont, QCursor

class DocToolCard(QFrame):
    """文档工具功能卡片"""
    clicked = pyqtSignal(str)  # 发射功能ID

    def __init__(self, tool_id, title, icon_emoji, description="", parent=None):
        super().__init__(parent)
        self.tool_id = tool_id
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(220, 140)
        
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
        self.init_ui()

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
        content_layout.setContentsMargins(40, 40, 40, 40)
        content_layout.setSpacing(30)
        
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
        ])
        
        content_layout.addStretch() # 底部弹簧
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    def add_section(self, parent_layout, title, tools):
        """添加一个功能分组"""
        # 分组标题
        section_label = QLabel(title)
        section_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #555; margin-bottom: 10px;")
        parent_layout.addWidget(section_label)
        
        # 网格布局容器
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(20)
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
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
        # 这里后续对接具体的 API 实现页面或弹窗
        # 目前仅显示提示
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
