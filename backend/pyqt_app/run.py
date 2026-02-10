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
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QT_VERSION_STR
from main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [启动日志] %(levelname)s: %(message)s",
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
