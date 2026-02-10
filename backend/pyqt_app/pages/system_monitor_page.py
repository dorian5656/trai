#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名: system_monitor_page.py
# 作者: liuhd
# 日期: 2026-02-09 10:06:00
# 描述: 系统监控模块页面，包含GPU检测、系统资源监控、模型状态和系统检查功能

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QGroupBox, QProgressBar, QTextEdit, 
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QFrame,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
import requests
import datetime
from .config_loader import config

class GpuCheckWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            url = config["system_monitor"].get("gpu_url", "")
            if not url:
                raise ValueError("Config missing 'gpu_url'")
            
            # API Call
            resp = requests.post(url, headers={"accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 200:
                self.finished.emit(data.get("data", {}))
            else:
                self.error.emit(f"API Error: {data.get('msg')}")
                
        except Exception as e:
            self.error.emit(str(e))

class SystemResourceWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            url = config["system_monitor"].get("system_url", "")
            if not url:
                raise ValueError("Config missing 'system_url'")
            
            # API Call
            resp = requests.post(url, headers={"accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 200:
                self.finished.emit(data.get("data", {}))
            else:
                self.error.emit(f"API Error: {data.get('msg')}")
                
        except Exception as e:
            self.error.emit(str(e))

class ModelStatusWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            url = config["system_monitor"].get("models_url", "")
            if not url:
                raise ValueError("Config missing 'models_url'")
            
            # API Call
            resp = requests.post(url, headers={"accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 200:
                self.finished.emit(data.get("data", []))
            else:
                self.error.emit(f"API Error: {data.get('msg')}")
                
        except Exception as e:
            self.error.emit(str(e))

class SystemHealthWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            url = config["system_monitor"].get("health_url", "")
            if not url:
                raise ValueError("Config missing 'health_url'")
            
            # API Call
            resp = requests.get(url, headers={"accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 200:
                self.finished.emit(data.get("data", {}))
            else:
                self.error.emit(f"API Error: {data.get('msg')}")
                
        except Exception as e:
            self.error.emit(str(e))

class SystemMonitorPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
        # 启动自动检测
        QTimer.singleShot(1000, self.start_gpu_check)
        QTimer.singleShot(1500, self.start_sys_check)
        QTimer.singleShot(2000, self.start_model_check)
        QTimer.singleShot(2500, self.start_health_check)

    def init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 第一部分：顶部资源监控 (GPU + 系统资源)
        top_layout = QHBoxLayout()
        
        # 1. GPU环境检测
        self.gpu_group = self.create_gpu_group()
        top_layout.addWidget(self.gpu_group, 1) # 1是拉伸比例
        
        # 2. 系统资源监控
        self.sys_group = self.create_sys_group()
        top_layout.addWidget(self.sys_group, 1)
        
        main_layout.addLayout(top_layout)

        # 第二部分：模型状态
        # 3. 获取所有模型状态
        self.model_group = self.create_model_group()
        main_layout.addWidget(self.model_group) # 自适应高度

        # 第三部分：系统检查
        # 4. 系统健康检查
        self.check_group = self.create_check_group()
        main_layout.addWidget(self.check_group, 1)

    def create_gpu_group(self):
        group = QGroupBox("GPU 环境检测")
        layout = QVBoxLayout(group)
        
        # 顶部信息栏 (Driver/CUDA)
        info_layout = QHBoxLayout()
        self.driver_label = QLabel("Driver: --")
        self.cuda_label = QLabel("CUDA: --")
        self.driver_label.setStyleSheet("font-weight: bold; color: #555;")
        self.cuda_label.setStyleSheet("font-weight: bold; color: #555;")
        
        info_layout.addWidget(self.driver_label)
        info_layout.addSpacing(20)
        info_layout.addWidget(self.cuda_label)
        info_layout.addStretch()
        
        # 刷新时间和按钮
        self.gpu_update_time = QLabel("")
        self.gpu_update_time.setStyleSheet("color: #666; font-size: 11px; margin-right: 10px;")
        info_layout.addWidget(self.gpu_update_time)
        
        self.gpu_refresh_btn = QPushButton("刷新")
        self.gpu_refresh_btn.setFixedSize(80, 25)
        self.gpu_refresh_btn.clicked.connect(self.start_gpu_check)
        info_layout.addWidget(self.gpu_refresh_btn)
        
        layout.addLayout(info_layout)
        
        # GPU 列表区域 (支持多GPU滚动显示)
        self.gpu_scroll = QScrollArea()
        self.gpu_scroll.setWidgetResizable(True)
        self.gpu_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.gpu_list_widget = QWidget()
        self.gpu_list_layout = QVBoxLayout(self.gpu_list_widget)
        self.gpu_list_layout.setContentsMargins(0, 0, 0, 0)
        self.gpu_list_layout.setSpacing(10)
        self.gpu_list_layout.addStretch() # 初始占位
        
        self.gpu_scroll.setWidget(self.gpu_list_widget)
        # 设置最小高度，确保能看到更多内容
        self.gpu_scroll.setMinimumHeight(200)
        layout.addWidget(self.gpu_scroll)
        
        return group

    def start_health_check(self):
        """开始系统健康检查"""
        self.check_log.clear()
        self.check_log.append("正在启动系统健康诊断...\n")
        
        if hasattr(self, 'start_check_btn'):
            self.start_check_btn.setEnabled(False)
            self.start_check_btn.setText("诊断中...")
            QApplication.processEvents()
            
        self.health_worker = SystemHealthWorker()
        self.health_worker.finished.connect(self.on_health_check_success)
        self.health_worker.error.connect(self.on_health_check_error)
        self.health_worker.start()

    def on_health_check_success(self, data):
        """处理健康检查成功"""
        # 恢复按钮
        if hasattr(self, 'start_check_btn'):
            self.start_check_btn.setEnabled(True)
            self.start_check_btn.setText("刷新")
            
        # 更新时间
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'check_update_time'):
            self.check_update_time.setText(f"更新: {now}")
            
        # 解析数据
        status = data.get("status", "unknown")
        timestamp = data.get("timestamp", 0)
        checks = data.get("checks", {})
        
        # 格式化时间
        try:
            ts_dt = datetime.datetime.fromtimestamp(timestamp)
            ts_str = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            ts_str = str(timestamp)
        
        # 总体状态颜色配置
        status_colors = {
            "ok": "#4CAF50",      # Green
            "degraded": "#FF9800", # Orange
            "error": "#F44336",    # Red
            "unknown": "#9E9E9E"   # Grey
        }
        main_color = status_colors.get(status, "#9E9E9E")
        
        # 构建HTML
        html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif;">
            <!-- 总体状态卡片 -->
            <div style="
                border-left: 5px solid {main_color}; 
                padding: 10px; 
                margin-bottom: 15px;
            ">
                <h2 style="margin: 0; color: {main_color}; font-size: 18px;">
                    总体状态: {status.upper()}
                </h2>
                <p style="margin: 5px 0 0 0; color: #666; font-size: 12px;">
                    检测时间: {ts_str}
                </p>
            </div>
            
            <!-- 详细检查项表格 -->
            <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse: separate; border-spacing: 0 10px;">
        """
        
        # 遍历子项检查
        for key, val in checks.items():
            sub_status = val.get("status", "unknown")
            sub_color = status_colors.get(sub_status, "#9E9E9E")
            
            # 详情内容构建
            details_html = ""
            if key == "ai_models":
                models = val.get("models", [])
                # 模型列表用逗号隔开
                model_str = ", ".join(models)
                details_html = f"<div style='margin-top: 5px; color: #1565C0; font-size: 12px;'>{model_str}</div>"
                
            elif key == "database":
                details = val.get("details", {})
                conn = details.get("connection", "unknown")
                missing = details.get("missing_tables", [])
                
                conn_color = "#4CAF50" if conn == "ok" else "#F44336"
                details_html += f"<div style='margin-top: 5px; font-size: 12px; color: #555;'>连接状态: <span style='color:{conn_color}; font-weight:bold;'>{conn}</span></div>"
                
                if missing:
                    details_html += f"<div style='margin-top: 3px; font-size: 12px; color: #F44336;'>⚠️ 缺失表: {', '.join(missing)}</div>"
                    
            elif key == "storage":
                stype = val.get("type", "unknown")
                details_html = f"<div style='margin-top: 5px; font-size: 12px; color: #555;'>存储类型: <b>{stype}</b></div>"
                
            else:
                details = val.get("details", "")
                if details:
                    details_html = f"<div style='margin-top: 5px; font-size: 12px; color: #666;'>{details}</div>"
            
            # 单个检查项卡片行
            html += f"""
            <tr>
                <td style="
                    border-bottom: 1px solid #E0E0E0; 
                    padding: 10px; 
                ">
                    <div style="margin-bottom: 5px;">
                        <span style="font-size: 14px; font-weight: bold; color: #333;">{key}</span>
                        <span style="
                            float: right; 
                            color: {sub_color}; 
                            font-size: 12px; 
                            font-weight: bold;
                        ">{sub_status.upper()}</span>
                    </div>
                    {details_html}
                </td>
            </tr>
            """
            
        html += "</table></div>"
        self.check_log.setHtml(html)

    def on_health_check_error(self, err):
        """处理健康检查失败"""
        if hasattr(self, 'start_check_btn'):
            self.start_check_btn.setEnabled(True)
            self.start_check_btn.setText("刷新")
            
        self.check_log.setHtml(f"<h3 style='color: red'>诊断失败</h3><p>{err}</p>")

    def start_gpu_check(self):
        """开始检测GPU信息"""
        self.driver_label.setText("Driver: 检测中...")
        if hasattr(self, 'gpu_refresh_btn'):
            self.gpu_refresh_btn.setEnabled(False)
            self.gpu_refresh_btn.setText("...")
            QApplication.processEvents()

        self.worker = GpuCheckWorker()
        self.worker.finished.connect(self.on_gpu_check_success)
        self.worker.error.connect(self.on_gpu_check_error)
        self.worker.start()

    def on_gpu_check_success(self, data):
        """处理GPU检测成功数据"""
        if hasattr(self, 'gpu_refresh_btn'):
            self.gpu_refresh_btn.setEnabled(True)
            self.gpu_refresh_btn.setText("刷新")
            
        # 更新时间
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'gpu_update_time'):
            self.gpu_update_time.setText(f"更新: {now}")

        nvidia_smi = data.get("nvidia_smi", {})
        if not nvidia_smi.get("available"):
            self.on_gpu_check_error("NVIDIA-SMI不可用")
            return

        # 更新基础信息
        self.driver_label.setText(f"Driver: {nvidia_smi.get('driver_version', '--')}")
        self.cuda_label.setText(f"CUDA: {nvidia_smi.get('cuda_version', '--')}")
        
        # 清空旧列表
        self.clear_layout(self.gpu_list_layout)
        
        # 遍历GPU列表
        gpus = nvidia_smi.get("gpus", [])
        for i, gpu in enumerate(gpus):
            gpu_widget = self.create_single_gpu_widget(i, gpu)
            self.gpu_list_layout.addWidget(gpu_widget)
            
        self.gpu_list_layout.addStretch() # 底部弹簧

    def on_gpu_check_error(self, err_msg):
        """处理GPU检测失败"""
        if hasattr(self, 'gpu_refresh_btn'):
            self.gpu_refresh_btn.setEnabled(True)
            self.gpu_refresh_btn.setText("刷新")
            
        self.driver_label.setText("检测失败")
        self.cuda_label.setText(err_msg)

    def create_single_gpu_widget(self, index, gpu_data):
        """创建单个GPU信息卡片"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: #f9f9f9;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # 标题行: GPU ID + Name + Temp
        title_layout = QHBoxLayout()
        name = gpu_data.get("product_name", "Unknown GPU")
        temp = gpu_data.get("temperature", "--")
        
        name_label = QLabel(f"GPU {index}: {name}")
        name_label.setStyleSheet("font-weight: bold; border: none;")
        temp_label = QLabel(f"🌡️ {temp}")
        temp_label.setStyleSheet("color: #FF5722; border: none;")
        
        title_layout.addWidget(name_label)
        title_layout.addStretch()
        title_layout.addWidget(temp_label)
        layout.addLayout(title_layout)
        
        # 显存信息
        mem = gpu_data.get("memory", {})
        used = mem.get("used", "0 MiB")
        total = mem.get("total", "0 MiB")
        
        # 解析数值用于进度条 (去除 " MiB")
        try:
            used_val = int(used.split()[0])
            total_val = int(total.split()[0])
            percent = int((used_val / total_val) * 100) if total_val > 0 else 0
        except:
            percent = 0
            
        mem_label = QLabel(f"显存: {used} / {total}")
        mem_label.setStyleSheet("font-size: 11px; color: #666; border: none;")
        layout.addWidget(mem_label)
        
        mem_bar = QProgressBar()
        mem_bar.setRange(0, 100)
        mem_bar.setValue(percent)
        mem_bar.setFixedHeight(10)
        mem_bar.setTextVisible(False)
        # 根据占用率变色
        color = "#4CAF50" if percent < 80 else "#FFC107" if percent < 90 else "#F44336"
        mem_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: #e0e0e0;
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(mem_bar)
        
        # 利用率信息
        util = gpu_data.get("utilization", {})
        gpu_util = util.get("gpu", "0 %")
        mem_util = util.get("memory", "0 %")
        layout.addWidget(QLabel(f"GPU利用率: {gpu_util}  |  显存利用率: {mem_util}", styleSheet="font-size: 11px; color: #666; border: none;"))

        return widget

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()


    def create_sys_group(self):
        group = QGroupBox("系统资源监控")
        layout = QVBoxLayout(group)
        
        # 顶部刷新按钮
        top_layout = QHBoxLayout()
        top_layout.addStretch()
        
        self.sys_update_time = QLabel("")
        self.sys_update_time.setStyleSheet("color: #666; font-size: 11px; margin-right: 10px;")
        top_layout.addWidget(self.sys_update_time)
        
        self.sys_refresh_btn = QPushButton("刷新")
        self.sys_refresh_btn.setFixedSize(80, 25)
        self.sys_refresh_btn.clicked.connect(self.start_sys_check)
        top_layout.addWidget(self.sys_refresh_btn)
        layout.addLayout(top_layout)

        # CPU
        cpu_layout = QVBoxLayout()
        cpu_title = QHBoxLayout()
        cpu_title.addWidget(QLabel("CPU"))
        self.cpu_info_label = QLabel("--% | -- Cores")
        self.cpu_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.cpu_info_label.setStyleSheet("color: #666; font-size: 11px;")
        cpu_title.addWidget(self.cpu_info_label)
        cpu_layout.addLayout(cpu_title)
        
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setValue(0)
        self.cpu_bar.setFixedHeight(8)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setStyleSheet("""
            QProgressBar { border: none; background-color: #e0e0e0; border-radius: 4px; }
            QProgressBar::chunk { background-color: #2196F3; border-radius: 4px; }
        """)
        cpu_layout.addWidget(self.cpu_bar)
        layout.addLayout(cpu_layout)
        
        # RAM
        ram_layout = QVBoxLayout()
        ram_title = QHBoxLayout()
        ram_title.addWidget(QLabel("内存"))
        self.ram_info_label = QLabel("--% | Used: -- / Total: --")
        self.ram_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.ram_info_label.setStyleSheet("color: #666; font-size: 11px;")
        ram_title.addWidget(self.ram_info_label)
        ram_layout.addLayout(ram_title)

        self.ram_bar = QProgressBar()
        self.ram_bar.setValue(0)
        self.ram_bar.setFixedHeight(8)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setStyleSheet("""
            QProgressBar { border: none; background-color: #e0e0e0; border-radius: 4px; }
            QProgressBar::chunk { background-color: #9C27B0; border-radius: 4px; }
        """)
        ram_layout.addWidget(self.ram_bar)
        layout.addLayout(ram_layout)
        
        # Disk
        disk_layout = QVBoxLayout()
        disk_title = QHBoxLayout()
        disk_title.addWidget(QLabel("磁盘"))
        self.disk_info_label = QLabel("--% | Used: -- / Total: --")
        self.disk_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.disk_info_label.setStyleSheet("color: #666; font-size: 11px;")
        disk_title.addWidget(self.disk_info_label)
        disk_layout.addLayout(disk_title)

        self.disk_bar = QProgressBar()
        self.disk_bar.setValue(0)
        self.disk_bar.setFixedHeight(8)
        self.disk_bar.setTextVisible(False)
        self.disk_bar.setStyleSheet("""
            QProgressBar { border: none; background-color: #e0e0e0; border-radius: 4px; }
            QProgressBar::chunk { background-color: #FF9800; border-radius: 4px; }
        """)
        disk_layout.addWidget(self.disk_bar)
        layout.addLayout(disk_layout)
        
        layout.addStretch()
        return group

    def start_sys_check(self):
        """开始检测系统资源"""
        if hasattr(self, 'sys_refresh_btn'):
            self.sys_refresh_btn.setEnabled(False)
            self.sys_refresh_btn.setText("...")
            QApplication.processEvents()

        self.sys_worker = SystemResourceWorker()
        self.sys_worker.finished.connect(self.on_sys_check_success)
        self.sys_worker.error.connect(self.on_sys_check_error)
        self.sys_worker.start()

    def on_sys_check_success(self, data):
        """处理系统资源检测成功"""
        if hasattr(self, 'sys_refresh_btn'):
            self.sys_refresh_btn.setEnabled(True)
            self.sys_refresh_btn.setText("刷新")

        # 更新时间
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'sys_update_time'):
            self.sys_update_time.setText(f"更新: {now}")

        # CPU
        cpu = data.get("cpu", {})
        cpu_percent = cpu.get("percent", 0)
        cpu_cores = cpu.get("cores", 0)
        self.cpu_bar.setValue(int(cpu_percent))
        self.cpu_info_label.setText(f"{cpu_percent}% | {cpu_cores} Cores")
        
        # Memory
        mem = data.get("memory", {})
        mem_total = mem.get("total_gb", 0)
        mem_avail = mem.get("available_gb", 0)
        mem_percent = mem.get("percent", 0)
        mem_used = mem_total - mem_avail
        self.ram_bar.setValue(int(mem_percent))
        self.ram_info_label.setText(f"{mem_percent}% | Used: {mem_used:.2f}GB / Total: {mem_total:.2f}GB")
        
        # Disk
        disk = data.get("disk", {})
        disk_total = disk.get("total_gb", 0)
        disk_used = disk.get("used_gb", 0)
        disk_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0
        self.disk_bar.setValue(int(disk_percent))
        self.disk_info_label.setText(f"{disk_percent:.1f}% | Used: {disk_used:.2f}GB / Total: {disk_total:.2f}GB")

    def on_sys_check_error(self, err):
        """处理系统资源检测失败"""
        if hasattr(self, 'sys_refresh_btn'):
            self.sys_refresh_btn.setEnabled(True)
            self.sys_refresh_btn.setText("刷新")
            
        self.cpu_info_label.setText("检测失败")
        self.ram_info_label.setText("检测失败")
        self.disk_info_label.setText("检测失败")

    def create_model_group(self):
        group = QGroupBox("模型状态")
        layout = QVBoxLayout(group)
        
        # 顶部刷新栏
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        
        self.model_update_time = QLabel("更新: --:--:--")
        self.model_update_time.setStyleSheet("color: #666; font-size: 11px; margin-right: 10px;")
        refresh_layout.addWidget(self.model_update_time)
        
        self.model_refresh_btn = QPushButton("刷新")
        self.model_refresh_btn.setFixedSize(80, 25)
        self.model_refresh_btn.clicked.connect(self.start_model_check)
        refresh_layout.addWidget(self.model_refresh_btn)
        
        layout.addLayout(refresh_layout)

        # 模型列表表格
        self.model_table = QTableWidget()
        self.model_table.setMinimumHeight(200) # 最小高度
        self.model_table.setMaximumHeight(400) # 最大高度，避免占用过多空间
        self.model_table.setColumnCount(5)
        self.model_table.setHorizontalHeaderLabels(["模型名称", "类型", "状态", "显卡", "描述"])
        self.model_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.model_table.horizontalHeader().setStretchLastSection(True)
        # 设置初始列宽
        self.model_table.setColumnWidth(0, 250) # 模型名称
        self.model_table.setColumnWidth(1, 100) # 类型
        self.model_table.setColumnWidth(2, 100) # 状态
        self.model_table.setColumnWidth(3, 100) # 显卡
        # 描述列宽一点 (ResizeToContents 会导致无法手动调整，改用 StretchLastSection)
        # self.model_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.model_table.setAlternatingRowColors(True)
        self.model_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.model_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.model_table)
        
        return group

    def start_model_check(self):
        """开始获取模型状态"""
        # 清空列表以示刷新
        self.model_table.setRowCount(0)
        
        if hasattr(self, 'model_refresh_btn'):
            self.model_refresh_btn.setEnabled(False)
            self.model_refresh_btn.setText("刷新中...")
            QApplication.processEvents() # 强制刷新UI
            
        self.model_worker = ModelStatusWorker()
        self.model_worker.finished.connect(self.on_model_check_success)
        self.model_worker.error.connect(self.on_model_check_error)
        self.model_worker.start()

    def on_model_check_success(self, data):
        """处理模型状态获取成功"""
        # 更新时间
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'model_update_time'):
            self.model_update_time.setText(f"更新: {now}")

        if hasattr(self, 'model_refresh_btn'):
            self.model_refresh_btn.setEnabled(True)
            self.model_refresh_btn.setText("刷新")

        self.model_table.setRowCount(0)
        self.model_table.setRowCount(len(data))
        
        for i, model in enumerate(data):
            # Name
            name_item = QTableWidgetItem(model.get("name", "--"))
            name_item.setToolTip(model.get("filename", ""))
            self.model_table.setItem(i, 0, name_item)
            
            # Type
            type_item = QTableWidgetItem(model.get("type", "--"))
            self.model_table.setItem(i, 1, type_item)
            
            # Status
            status = model.get("status", "unknown")
            status_item = QTableWidgetItem(status)
            if status == "loaded":
                status_item.setForeground(Qt.GlobalColor.green)
            elif status == "pending":
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            elif status == "error":
                status_item.setForeground(Qt.GlobalColor.red)
            self.model_table.setItem(i, 2, status_item)
            
            # GPU Info
            use_gpu = model.get("use_gpu", False)
            gpu_id = model.get("gpu_id", 0)
            gpu_text = f"GPU {gpu_id}" if use_gpu else "CPU"
            self.model_table.setItem(i, 3, QTableWidgetItem(gpu_text))
            
            # Description
            desc = model.get("description", "")
            desc_item = QTableWidgetItem(desc)
            desc_item.setToolTip(desc)
            self.model_table.setItem(i, 4, desc_item)

    def on_model_check_error(self, err):
        """处理模型状态获取失败"""
        if hasattr(self, 'model_refresh_btn'):
            self.model_refresh_btn.setEnabled(True)
            self.model_refresh_btn.setText("刷新")

        self.model_table.setRowCount(1)
        self.model_table.setItem(0, 0, QTableWidgetItem("加载失败"))
        self.model_table.setItem(0, 4, QTableWidgetItem(err))

    def create_check_group(self):
        group = QGroupBox("系统健康检查")
        layout = QVBoxLayout(group)
        
        # 操作栏
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        self.check_update_time = QLabel("")
        self.check_update_time.setStyleSheet("color: #666; font-size: 11px; margin-right: 10px;")
        
        self.start_check_btn = QPushButton("刷新")
        self.start_check_btn.setFixedSize(80, 25)
        # self.start_check_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.start_check_btn.clicked.connect(self.start_health_check)
        
        action_layout.addWidget(self.check_update_time)
        action_layout.addWidget(self.start_check_btn)
        
        layout.addLayout(action_layout)
        
        # 日志输出
        self.check_log = QTextEdit()
        self.check_log.setReadOnly(True)
        # self.check_log.setPlaceholderText("点击“刷新”以运行系统诊断...")
        self.check_log.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd; font-family: Consolas;")
        
        layout.addWidget(self.check_log)
        
        return group
