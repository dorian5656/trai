#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：run.py
# 作者：liuhd
# 日期：2026-02-04 10:00:00
# 描述：TRAI 程序入口文件（含详细启动日志）

import sys
import os
import logging
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QT_VERSION_STR, QSharedMemory
from main_window import MainWindow

# 配置 logging
# 注意：在 PyInstaller 打包后的无控制台模式下 (noconsole)，sys.stderr 为 None
# 此时默认的 StreamHandler 会导致 AttributeError: 'NoneType' object has no attribute 'write'
# 因此我们需要检查环境，避免添加默认 handler
handlers = []
if sys.stderr:
    handlers.append(logging.StreamHandler())
else:
    # 可以在这里添加 FileHandler 用于调试，或者什么都不加 (使用 NullHandler)
    handlers.append(logging.NullHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [启动日志] %(levelname)s: %(message)s",
    handlers=handlers
)

def get_resource_path(relative_path):
    """获取资源绝对路径，兼容开发环境和打包环境"""
    if getattr(sys, 'frozen', False):
        # 打包后，资源文件在 sys._MEIPASS
        base_path = sys._MEIPASS
    else:
        # 开发环境，资源文件在当前脚本所在目录
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def load_stylesheet(app):
    try:
        style_path = get_resource_path(os.path.join("styles", "style.qss"))
        logging.info(f"加载样式表: {os.path.abspath(style_path)}")
        if not os.path.exists(style_path):
            logging.warning(f"样式文件不存在: {style_path}")
            return
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        logging.info("样式表加载完成")
    except Exception as e:
        logging.error(f"样式表加载失败: {e}")
        logging.debug(traceback.format_exc())

def main():
    try:
        logging.info("启动应用: 创建 QApplication")
        app = QApplication(sys.argv)
        
        # --- 单实例检查开始 ---
        # 使用 QSharedMemory 检查是否已经有实例在运行
        # 这里的 Key 必须是系统唯一的，建议包含应用名称和版本信息
        shared_memory_key = "TraiClient_Unique_Instance_Key_2026"
        shared_memory = QSharedMemory(shared_memory_key)
        
        if shared_memory.attach():
            # 尝试附加成功，说明共享内存段已存在，即另一个实例正在运行
            logging.warning("检测到应用程序已在运行，正在退出当前实例...")
            
            # 可以在这里弹窗提示用户
            msg_box = QMessageBox()
            msg_box.setWindowTitle("提示")
            msg_box.setText("程序已经在运行中！")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            
            sys.exit(0)
        
        if not shared_memory.create(1):
            # 创建失败，可能是权限问题或者其他异常
            # 但通常如果是 create 失败且 attach 也失败，说明可以继续尝试运行
            # 不过为了保险起见，如果 create 失败，我们记录错误但允许运行，或者根据需求退出
            # 这里我们记录错误日志
            logging.error(f"无法创建共享内存段: {shared_memory.errorString()}")
            # 如果仅仅是之前的实例崩溃导致的段残留，Qt在Unix上可能需要处理，但在Windows上系统会自动回收
            # 考虑到Windows环境，这里可以视为非阻塞性错误，或者选择退出
            # 暂时允许继续，除非非常严格
        # --- 单实例检查结束 ---

        # 设置工作目录
        if getattr(sys, 'frozen', False):
            # 打包后，工作目录设置为可执行文件所在目录 (方便读取外部 config.json)
            script_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境，工作目录为脚本所在目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
        logging.info(f"设置工作目录: {script_dir}")
        os.chdir(script_dir)
        logging.info(f"Qt 版本: {QT_VERSION_STR}")

        load_stylesheet(app)

        logging.info("创建主窗口 MainWindow")
        window = MainWindow()
        logging.info("显示主窗口")
        window.show()

        logging.info("进入事件循环 app.exec()")
        exit_code = app.exec()
        logging.info(f"事件循环退出，代码: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logging.error(f"启动失败: {e}")
        logging.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
