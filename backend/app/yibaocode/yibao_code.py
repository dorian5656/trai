#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：yibao_code.py
# 作者：liuhd
# 日期：2026-01-28 09:47:00
# 描述：医保数据抓取脚本（模块导入版）

"""
医保数据抓取脚本

使用 DrissionPage 自动化抓取医保数据，包含验证码识别与自动重试机制。
"""
import subprocess
import sys
import os
import platform

import logging

# 配置基础日志，用于依赖安装阶段
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def install_dependencies():
    """自动检查并安装依赖，如果缺少则使用清华源安装。"""
    required_packages = [
        'DrissionPage', 
        'ddddocr', 
        'pandas', 
        'sqlalchemy', 
        'pymysql', 
        'psycopg2-binary',
        'openpyxl',
        'loguru',
        'requests',
        'python-dotenv'
    ]
    
    logging.info("正在检查依赖...")
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            logging.info(f"正在安装 {package}...")
            try:
                subprocess.check_call([
                    sys.executable, '-m', 'pip', 'install', package, 
                    '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple'
                ])
                logging.info(f"{package} 安装成功.")
            except subprocess.CalledProcessError:
                logging.error(f"安装 {package} 失败. 请手动安装.")
    
    # 修复 ddddocr 在新版 Pillow 下的兼容性问题
    import PIL
    if not hasattr(PIL.Image, 'ANTIALIAS'):
        PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# 在导入之前检查并安装依赖
if __name__ == "__main__":
    install_dependencies()

from DrissionPage import ChromiumPage, ChromiumOptions
import ddddocr
import time
import glob
import pandas as pd
from sqlalchemy import create_engine, text, types
from loguru import logger
import requests
import urllib.parse
from dotenv import load_dotenv
import uuid

class DatabaseSink:
    """写入 PostgreSQL 数据库的 Loguru Sink"""
    def __init__(self):
        # 尝试加载环境变量
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 尝试在上级目录及根目录查找 .env
        potential_paths = [
            os.path.join(current_dir, '.env'),
            os.path.join(os.path.dirname(current_dir), '.env'),
            os.path.join(os.path.dirname(os.path.dirname(current_dir)), '.env')
        ]
        
        env_loaded = False
        for env_path in potential_paths:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                env_loaded = True
                break
        
        if not env_loaded:
            load_dotenv() # 尝试默认位置

        pg_server = os.getenv('POSTGRES_SERVER')
        pg_port = os.getenv('POSTGRES_PORT')
        pg_user = os.getenv('POSTGRES_USER')
        pg_password = os.getenv('POSTGRES_PASSWORD')
        pg_db = os.getenv('POSTGRES_DB_YIBAO')

        if pg_server and pg_user and pg_db:
             self.db_url = f"postgresql+psycopg2://{pg_user}:{urllib.parse.quote_plus(pg_password)}@{pg_server}:{pg_port}/{pg_db}"
        else:
             self.db_url = os.getenv('POSTGRES_DB_YIBAO')

        if not self.db_url:
            logger.error("错误: 环境变量 POSTGRES_* 或 POSTGRES_DB_YIBAO 未设置，无法初始化数据库日志 Sink")
            self.engine = None
            return

        try:
            self.engine = create_engine(self.db_url)
            self.init_db()
        except Exception as e:
            logger.error(f"初始化数据库连接失败: {e}")
            self.engine = None

    def init_db(self):
        """创建日志表 yibaocode_log"""
        if not self.engine:
            return
            
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS yibaocode_log (
            uuid VARCHAR(36) NOT NULL PRIMARY KEY,
            log_time TIMESTAMP NOT NULL,
            log_level VARCHAR(20) NOT NULL,
            message TEXT
        );
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text(create_table_sql))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_log_time ON yibaocode_log (log_time);"))
                conn.execute(text("COMMENT ON TABLE yibaocode_log IS '医保抓取日志表';"))
                conn.execute(text("COMMENT ON COLUMN yibaocode_log.uuid IS '唯一标识';"))
                conn.execute(text("COMMENT ON COLUMN yibaocode_log.log_time IS '日志时间';"))
                conn.execute(text("COMMENT ON COLUMN yibaocode_log.log_level IS '日志级别';"))
                conn.execute(text("COMMENT ON COLUMN yibaocode_log.message IS '日志内容';"))
                conn.commit()
        except Exception as e:
            logger.error(f"创建表 yibaocode_log 失败: {e}")

    def write(self, message):
        """写入日志记录"""
        if not self.engine:
            return

        record = message.record
        
        # 避免递归：如果日志带有 no_db 标记，则不写入数据库
        if record["extra"].get("no_db"):
            return

        # 获取需要的字段
        log_uuid = str(uuid.uuid4())
        # loguru 的 time 是 datetime 对象
        log_time = record["time"].strftime("%Y-%m-%d %H:%M:%S")
        log_level = record["level"].name
        log_msg = record["message"]

        insert_sql = """
        INSERT INTO yibaocode_log (uuid, log_time, log_level, message)
        VALUES (:uuid, :log_time, :log_level, :message)
        """
        
        try:
            with self.engine.connect() as conn:
                conn.execute(text(insert_sql), {
                    "uuid": log_uuid,
                    "log_time": log_time,
                    "log_level": log_level,
                    "message": log_msg
                })
                conn.commit()
        except Exception as e:
            # 避免日志循环错误，使用 logger.bind(no_db=True)
            logger.bind(no_db=True).error(f"写入数据库日志失败: {e}")

# 配置 logger
# if __name__ == "__main__":
#    logger.remove()
#    logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
#    # logger.add("yibao_demo.log", rotation="10 MB", encoding="utf-8", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}")
    
#    # 添加数据库 Sink
#    try:
#        db_sink = DatabaseSink()
#        logger.add(db_sink.write, level="INFO")
#    except Exception as e:
#        logger.error(f"添加数据库 Sink 失败: {e}")

def send_wechat_webhook(content):
    """发送企业微信机器人消息（底层函数）。"""
    url = os.getenv("WECHAT_WEBHOOK_URL")
    if not url:
        # 尝试从 key 构建
        key = os.getenv("WECHAT_TRAI_ROBOT_KEY")
        if key:
            url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"

    if not url:
        print("错误: 未配置 WECHAT_WEBHOOK_URL 或 WECHAT_TRAI_ROBOT_KEY，无法发送微信消息")
        return

    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code != 200:
            print(f"微信消息发送失败: {response.text}")
    except Exception as e:
        print(f"发送微信消息时发生错误: {e}")

class WeChatSink:
    """自定义 Loguru Sink，用于缓冲并发送微信消息。"""
    def __init__(self):
        self.buffer = []
        self.last_send_time = time.time()
        self.max_buffer_size = 10  # 最多缓冲10条
        self.max_interval = 2.0    # 最长间隔2秒

    def write(self, message):
        record = message.record
        # 过滤掉不需要发送的日志 (可以通过 extra 标记)
        if record["extra"].get("no_wechat"):
            return
            
        # 格式化消息：时间 | 级别 | 内容
        log_entry = f"{record['time'].strftime('%H:%M:%S')} {record['message']}"
        self.buffer.append(log_entry)
        
        self.check_flush()

    def check_flush(self):
        current_time = time.time()
        if len(self.buffer) >= self.max_buffer_size or (current_time - self.last_send_time > self.max_interval):
            self.flush()

    def flush(self):
        if not self.buffer:
            return
        
        content = "\n".join(self.buffer)
        send_wechat_webhook(content)
        
        self.buffer = []
        self.last_send_time = time.time()

# 初始化微信 Sink
_logging_initialized = False

def setup_logging():
    """初始化日志配置（幂等操作）"""
    global _logging_initialized
    if _logging_initialized:
        return

    # 添加数据库 Sink
    try:
        db_sink = DatabaseSink()
        logger.add(db_sink.write, level="INFO")
    except Exception as e:
        logger.error(f"添加数据库 Sink 失败: {e}")

    # 添加微信 Sink
    try:
        wechat_sink = WeChatSink()
        logger.add(wechat_sink.write, level="INFO")
    except Exception as e:
        logger.error(f"添加微信 Sink 失败: {e}")

    _logging_initialized = True

if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    # logger.add("yibao_demo.log", rotation="10 MB", encoding="utf-8", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}")
    
    setup_logging()

class MedicalConsumableImporter:
    def __init__(self):
        # 确保日志已初始化
        setup_logging()

        # 加载 .env 文件
        # 计算项目根目录路径
        # 当前文件在 /home/tuoren_apps/nhsa_post_crm/yibao_demo.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 依次尝试在当前目录、上级目录及根目录查找 .env 文件
        potential_paths = [
            os.path.join(current_dir, '.env'),
            os.path.join(os.path.dirname(current_dir), '.env'),
            os.path.join(os.path.dirname(os.path.dirname(current_dir)), '.env')
        ]
        
        env_loaded = False
        for env_path in potential_paths:
            if os.path.exists(env_path):
                 load_dotenv(env_path)
                 logger.info(f"已加载配置文件: {env_path}")
                 env_loaded = True
                 break
                 
        if not env_loaded:
             load_dotenv() # 尝试默认加载
             logger.warning(f"未找到配置文件 (已尝试: {', '.join(potential_paths)}), 尝试默认加载")

        # 数据库配置
        pg_server = os.getenv('POSTGRES_SERVER')
        pg_port = os.getenv('POSTGRES_PORT')
        pg_user = os.getenv('POSTGRES_USER')
        pg_password = os.getenv('POSTGRES_PASSWORD')
        pg_db = os.getenv('POSTGRES_DB_YIBAO')

        if pg_server and pg_user and pg_db:
             self.db_url = f"postgresql+psycopg2://{pg_user}:{urllib.parse.quote_plus(pg_password)}@{pg_server}:{pg_port}/{pg_db}"
             logger.info(f"使用环境变量中的 POSTGRES 配置连接数据库: {pg_db}")
        else:
            self.db_url = os.getenv('DB_URL_YIBAO')
            if not self.db_url:
                logger.warning("未在环境变量中找到 POSTGRES_* 或 DB_URL_YIBAO，使用默认本地配置")
                self.db_user = 'root'
                self.db_password = '123456' 
                self.db_host = '192.168.100.119'
                self.db_port = 13307
                self.db_name = 'nhsa_data'
                self.db_url = f"mysql+pymysql://{self.db_user}:{urllib.parse.quote_plus(self.db_password)}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
            else:
                logger.info(f"使用环境变量中的 DB_URL: {self.db_url.split('@')[-1]}") # 简单的脱敏打印

        self.sqlite_db_name = 'nhsa_data.db'
        
        self.cwd = os.getcwd()
        self.page = None

    def clean_old_files(self):
        """清理旧的 Excel 文件"""
        logger.info("正在清理旧的 Excel 文件...")
        xls_files = glob.glob(os.path.join(self.cwd, "*.xls"))
        for f in xls_files:
            try:
                os.remove(f)
                logger.info(f"已删除: {f}")
            except Exception as e:
                logger.error(f"删除文件 {f} 失败: {e}")

    def init_browser(self):
        """初始化浏览器。"""
        co = ChromiumOptions()
        
        # 根据系统类型配置浏览器
        sys_plat = platform.system()
        if sys_plat == 'Linux':
            logger.info("检测到 Linux 系统，正在应用 Linux 浏览器配置...")
            
            # 确保 HOME 环境变量存在，Cron 中可能丢失，导致 Chrome 启动失败
            if 'HOME' not in os.environ:
                os.environ['HOME'] = self.cwd
                logger.info(f"环境变量 HOME 未设置，临时设置为: {self.cwd}")

            co.set_argument('--no-sandbox')
            co.set_argument('--disable-setuid-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument('--disable-dev-shm-usage') 
            co.set_argument('--disable-software-rasterizer')
            co.set_argument('--ignore-certificate-errors')
            
            # 在服务器环境中，即使检测到 DISPLAY (可能是 SSH X11 Forwarding 残留或无效会话)，
            # 也建议默认使用无头模式，除非环境变量 explicitly 要求有头。
            # 这能解决宝塔/Cron 定时任务中因 DISPLAY 指向无效地址导致的 "Browser connection fails" 错误。
            
            show_browser = os.environ.get('SHOW_BROWSER') == '1'
            has_display = bool(os.environ.get('DISPLAY'))
            
            if show_browser and has_display:
                logger.info(f"检测到 DISPLAY ({os.environ.get('DISPLAY')}) 且 SHOW_BROWSER=1, 尝试有头模式运行...")
            else:
                if has_display and not show_browser:
                    logger.info(f"检测到 DISPLAY ({os.environ.get('DISPLAY')}), 但未设置 SHOW_BROWSER=1, 强制启用无头模式以保证稳定性...")
                else:
                    logger.info("未检测到显示设备, 启用无头模式 (Headless)...")
                
                # 回退到 standard headless 模式，--headless=new 在某些环境/版本组合下会导致 404 Handshake 错误
                co.headless(True)
        else:
            logger.info(f"检测到 {sys_plat} 系统, 使用默认配置...")
            # 在 Windows 上尝试定位浏览器路径
            candidates = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            ]
            for p in candidates:
                try:
                    if os.path.exists(p):
                        co.set_browser_path(p)
                        logger.info(f"已设置浏览器路径: {p}")
                        break
                except Exception as e:
                    logger.warning(f"设置浏览器路径失败: {e}")
            # 启用无头，以提升兼容性
            # try:
            #     co.headless(True)
            #     logger.info("已启用无头模式 (Headless).")
            # except Exception as e:
            #     logger.warning(f"启用无头模式失败: {e}")

        co.auto_port()
        co.set_download_path(self.cwd)
        self.page = ChromiumPage(co)
        self.page.set.download_path(self.cwd)

    def close_browser(self):
        """关闭浏览器"""
        if self.page:
            logger.info("正在关闭浏览器……")
            try:
                self.page.quit()
            except Exception as e:
                logger.error(f"关闭浏览器出错: {e}")
            finally:
                self.page = None
        else:
            logger.info("浏览器未启动或已关闭.")

    def download_file(self, account_info):
        """执行浏览器自动化操作并下载医保代码 Excel 文件。"""
        company_name = account_info['company']
        username = account_info['username']
        password = account_info['password']
        
        logger.info(f"开始处理: {company_name} (账号: {username})")
        logger.info("开始登录...")
        
        url = 'https://code.nhsa.gov.cn/hc/login.html'
        # 如果当前不在登录页，则打开
        if url not in self.page.url:
            logger.info(f"正在打开 {url}...")
            self.page.get(url)
            logger.info("页面打开成功.")
        
        # 处理可能出现的引导弹窗（通过点击遮罩层或空白区域关闭）
        try:
            # 检查是否存在引导弹窗遮罩层（layui-layer-shade）
            shade = self.page.ele('xpath://*[contains(@class, "layui-layer-shade")]')
            if shade and shade.states.is_displayed:
                logger.info("检测到引导弹窗遮罩，尝试点击空白处关闭...")
                # 尝试点击遮罩层本身，或者页面 body 元素
                shade.click()
                time.sleep(1)
            # 或者尝试点击 body 的某个无害位置，例如左上角
            # self.page.ele('tag:body').click(by_js=True)  # 也可以通过 JS 点击 body 关闭
        except Exception as e:
            logger.warning(f"处理引导弹窗时忽略错误: {e}")

        # 输入凭据
        
        # 确保输入框存在
        if self.page.ele('xpath://*[@id="username0"]'):
            logger.info(f"正在输入用户名: {username}")
            self.page.ele('xpath://*[@id="username0"]').input(username)
            logger.info("正在输入密码...")
            self.page.ele('xpath://*[@id="password0"]').input(password)
        
        # 等待验证码图片元素渲染完成
        logger.info("等待验证码图片加载...")
        if not self.page.wait.ele_displayed('xpath://*[@id="captchaImg0"]', timeout=10):
            logger.error("验证码图片未加载.")
            return False

        # 首次加载验证码可能为灰色占位符，先点击一次进行刷新
        try:
            first_captcha = self.page.ele('xpath://*[@id="captchaImg0"]')
            if first_captcha:
                logger.info("首次点击验证码以确保加载...")
                first_captcha.click()
                time.sleep(2)
        except Exception as e:
            logger.warning(f"首次点击验证码失败: {e}")

        max_login_retries = 20
        for login_attempt in range(max_login_retries):
            logger.info(f"=== 登录尝试第 {login_attempt + 1}/{max_login_retries} 次 ===")
            
            # 1. 识别并输入验证码
            captcha_success = False
            # 尝试几次识别
            for _ in range(3):
                captcha_img = self.page.ele('xpath://*[@id="captchaImg0"]')
                if captcha_img:
                    try:
                        img_bytes = captcha_img.src()
                        ocr = ddddocr.DdddOcr() 
                        res = ocr.classification(img_bytes)
                        filtered_res = "".join([c for c in (res or "") if c.isalnum()])
                        logger.info(f"验证码识别结果: 原始[{res}] -> 过滤后[{filtered_res}]")
                        
                        if len(filtered_res) == 5: # 假设验证码是5位，如果不确定可以放宽
                            logger.info(f"正在填入验证码: {filtered_res}")
                            self.page.ele('xpath://*[@id="answer0"]').input(filtered_res)
                            captcha_success = True
                            break
                        else:
                            logger.warning(f"验证码长度不对 ({len(filtered_res)}), 刷新...")
                            captcha_img.click()
                            time.sleep(1)
                    except Exception as e:
                         logger.warning(f"验证码识别出错: {e}")
            
            if not captcha_success:
                logger.warning("验证码自动识别多次失败，尝试刷新后继续...")
                if self.page.ele('xpath://*[@id="captchaImg0"]'):
                    self.page.ele('xpath://*[@id="captchaImg0"]').click()
                    time.sleep(1)
                # 继续尝试登录，说不定运气好或者逻辑允许
            
            # 2. 点击登录按钮
            login_btn = self.page.ele('text:登录')
            if login_btn:
                logger.info("点击登录按钮...")
                login_btn.click()
                time.sleep(2) # 等待响应
            else:
                logger.error("未找到登录按钮.")
                return False

            # 检测登录结果：
            # 先检测浏览器原生 Alert（验证码错误通常会以此形式提示），
            # handle_alert(accept=True) 会自动点击确定按钮并返回弹窗文本。
            alert_text = self.page.handle_alert(accept=True)
            if alert_text:
                logger.warning(f"检测到弹窗: {alert_text}")
                if "验证码" in alert_text or "不正确" in alert_text:
                    logger.info("验证码错误，准备重试...")
                    # 刷新验证码
                    captcha_img = self.page.ele('xpath://*[@id="captchaImg0"]')
                    if captcha_img:
                        captcha_img.click()
                        time.sleep(2)
                    continue # 进行下一次大循环
                elif "请输入用户名密码" in alert_text:
                    logger.warning("检测到'请输入用户名密码'提示，可能是输入框内容丢失，准备刷新页面重新输入...")
                    self.page.refresh()
                    time.sleep(2)
                    # 重新输入用户名和密码
                    if self.page.ele('xpath://*[@id="username0"]'):
                        logger.info(f"重新输入用户名: {username}")
                        self.page.ele('xpath://*[@id="username0"]').input(username)
                        logger.info("重新输入密码...")
                        self.page.ele('xpath://*[@id="password0"]').input(password)
                    continue
                else:
                    logger.info(f"遇到其他弹窗: {alert_text}，尝试继续后续流程...")
            
            # 检测是否已经登录成功（出现确认弹窗 layer 100002）
            if self.page.ele('xpath://*[@id="layui-layer100002"]'):
                logger.info("检测到登录成功后的确认弹窗 (layer100002).")
                break
            
            # 通过检测 URL 是否离开 login.html 来判断是否登录成功
            if "login.html" not in self.page.url:
                 logger.info(f"登录成功 (URL跳转至 {self.page.url}).")
                 break

            # 如果仍停留在登录页且无任何响应，可能是验证码错误但未弹窗，或者前端状态卡死
            logger.warning("未检测到成功标志，也未检测到错误弹窗，刷新页面重试...")
            self.page.refresh()
            time.sleep(3)
        else:
            logger.error("超过最大登录重试次数，登录失败。")
            return False

        # 登录成功后的页面操作与导出流程
        try:
            # 第一次登录确认弹窗
            logger.info("等待第一次确认弹窗...")
            if self.page.wait.ele_displayed('xpath://*[@id="layui-layer100002"]', timeout=10):
                logger.info("正在点击第一次确认...")
                self.page.ele('xpath://*[@id="layui-layer100002"]/div[3]/a').click()
                logger.info("第一次确认已点击.")
            else:
                logger.warning("未出现第一次确认弹窗，可能已跳过.")

            # 第二次登录确认弹窗
            logger.info("等待第二次确认弹窗...")
            time.sleep(2)
            if self.page.ele('xpath://*[@id="layui-layer100001"]'):
                logger.info("正在点击第二次确认...")
                self.page.ele('xpath://*[@id="layui-layer100001"]/div[3]/a').click()
                logger.info("第二次确认已点击.")
            
            # 点击一级、二级菜单，进入数据导出页面
            logger.info("正在点击一级菜单...")
            menu_item = self.page.ele('xpath://*[@id="sys-1"]/li[4]/a/span')
            if menu_item:
                menu_item.click()
                logger.info("一级菜单已点击.")
                
                logger.info("等待 2 秒展开子菜单...")
                time.sleep(2)
                
                logger.info("正在点击二级菜单...")
                sub_menu_item = self.page.ele('xpath://*[@id="sys-1"]/li[4]/ul/li[3]/a/span')
                if sub_menu_item:
                    sub_menu_item.click()
                    logger.info("二级菜单已点击.")
                    
                    logger.info("等待 5 秒加载页面内容...")
                    time.sleep(5)
                    
                    logger.info("正在点击导出按钮...")
                    export_btn = self.page.ele('xpath:/html/body/section[2]/div[2]/button[3]')
                    if export_btn:
                        # 下载前先记录当前目录下已存在的文件集合
                        before_files = set(os.listdir(self.cwd))
                        
                        export_btn.click()
                        logger.info("导出按钮已点击, 等待下载...")
                        
                        # 等待新文件生成（超时时间 60 秒）
                        timeout = 60
                        start_time = time.time()
                        
                        while time.time() - start_time < timeout:
                            current_files = set(os.listdir(self.cwd))
                            new_files = list(current_files - before_files)
                            final_files = [
                                f
                                for f in new_files
                                if not f.endswith('.crdownload')
                                and not f.endswith('.tmp')
                                and (f.lower().endswith('.xls') or f.lower().endswith('.xlsx'))
                            ]
                            if final_files:
                                downloaded_file = final_files[0]
                                logger.info(f"下载完成! 新文件: {downloaded_file}")
                                return os.path.join(self.cwd, downloaded_file)
                            
                            time.sleep(1)
                        else:
                             logger.error("下载超时.")
                    else:
                        logger.error("未找到导出按钮.")
                else:
                    logger.error("未找到二级菜单.")
            else:
                logger.error("未找到一级菜单.")
                
        except Exception as e:
            logger.error(f"登录后操作错误: {e}")
        
        return None

    def process_excel_to_db(self, file_path):
        """读取医保 Excel 文件并增量写入数据库。"""
        if not file_path or not os.path.exists(file_path):
            logger.error("无效的文件路径, 无法导入数据库.")
            return

        try:
            # 读取 Excel 文件
            df = pd.read_excel(file_path, dtype={'流水号': str})
            logger.info(f"正在读取文件: {file_path}，原始行数: {len(df)}")
            
            # 重命名列
            column_mapping = {
                '医用耗材代码': 'consumable_code',
                '流水号': 'serial_number',
                '注册证编号': 'registration_cert_no',
                '注册备案证号': 'registration_record_no',
                '原注册备案号': 'original_registration_record_no',
                '注册备案产品名称': 'registration_product_name',
                '旧注册备案证号': 'old_registration_record_no',
                '旧注册备案产品名称': 'old_registration_product_name',
                '注册、备案人': 'registrant',
                '耗材分类': 'consumable_category',
                '单件产品编号': 'single_product_code',
                '单件产品名称': 'single_product_name',
                '耗材企业': 'enterprise_name',
                '规格': 'specification',
                '型号': 'model',
                '规格型号编号': 'spec_model_id',
                'UDI-DI': 'udi_di'
            }
            
            df = df.rename(columns=column_mapping)
            
            if 'spec_model_id' not in df.columns:
                logger.error("错误: Excel 文件中缺少 'spec_model_id' 列")
                return
            
            df['status'] = 1
                
            # 修改唯一标识 ID 生成逻辑: 医用耗材代码 + 流水号
            # 确保两列都是字符串类型，处理可能的 NaN
            df['consumable_code'] = df['consumable_code'].astype(str)
            df['serial_number'] = df['serial_number'].astype(str)
            
            # 使用医用耗材代码与流水号组合生成 uuid（示例：C1402020000000005977-0000205）
            def generate_uuid(row):
                return f"{row['consumable_code']}-{row['serial_number']}"
            
            df['uuid'] = df.apply(generate_uuid, axis=1)
            df = df.drop_duplicates(subset=['uuid'])
            
            logger.info(f"准备写入 {len(df)} 条记录到数据库...")
            
            # 尝试连接 PostgreSQL
            try:
                engine = create_engine(self.db_url)
                with engine.connect() as con:
                    pass # 测试连接
                logger.info(f"成功连接到 PostgreSQL 数据库 (table: medical_consumables).")
                is_sqlite = False
            except Exception as e:
                logger.error(f"连接 PostgreSQL 失败: {e}")
                return # 终止后续操作
                
            temp_table_name = 'medical_consumables_temp'
            
            # 1. 处理临时表
            with engine.connect() as con:
                con.execute(text(f"DROP TABLE IF EXISTS {temp_table_name}"))
                con.commit()
                
            df.to_sql(name=temp_table_name, con=engine, if_exists='replace', index=False, dtype={
                'uuid': types.VARCHAR(128),
                'spec_model_id': types.VARCHAR(64),
                'consumable_code': types.VARCHAR(50),
                'serial_number': types.VARCHAR(50),
                'registration_cert_no': types.VARCHAR(100),
                'registration_record_no': types.VARCHAR(100),
                'original_registration_record_no': types.VARCHAR(100),
                'registration_product_name': types.VARCHAR(255),
                'old_registration_record_no': types.VARCHAR(100),
                'old_registration_product_name': types.VARCHAR(255),
                'registrant': types.VARCHAR(255),
                'consumable_category': types.VARCHAR(100),
                'single_product_code': types.VARCHAR(100),
                'single_product_name': types.VARCHAR(255),
                'enterprise_name': types.VARCHAR(255),
                'specification': types.TEXT(),
                'model': types.TEXT(),
                'udi_di': types.VARCHAR(100),
                'status': types.INTEGER(),
            })
            
            # 2. 创建主表
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS medical_consumables (
                uuid VARCHAR(128) NOT NULL PRIMARY KEY,
                spec_model_id VARCHAR(64),
                consumable_code VARCHAR(50),
                serial_number VARCHAR(50),
                registration_cert_no VARCHAR(100),
                registration_record_no VARCHAR(100),
                original_registration_record_no VARCHAR(100),
                registration_product_name VARCHAR(255),
                old_registration_record_no VARCHAR(100),
                old_registration_product_name VARCHAR(255),
                registrant VARCHAR(255),
                consumable_category VARCHAR(100),
                single_product_code VARCHAR(100),
                single_product_name VARCHAR(255),
                enterprise_name VARCHAR(255),
                specification TEXT,
                model TEXT,
                udi_di VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status SMALLINT NOT NULL DEFAULT 1
            );
            """
            
            index_sqls = [
                "CREATE INDEX IF NOT EXISTS idx_consumable_code ON medical_consumables (consumable_code);",
                "CREATE INDEX IF NOT EXISTS idx_registration_cert_no ON medical_consumables (registration_cert_no);",
                "CREATE INDEX IF NOT EXISTS idx_spec_model_id ON medical_consumables (spec_model_id);",
                "COMMENT ON TABLE medical_consumables IS '医用耗材分类与代码表';",
                "COMMENT ON COLUMN medical_consumables.uuid IS '主键 (医用耗材代码 + 流水号)';",
                "COMMENT ON COLUMN medical_consumables.spec_model_id IS '规格型号编号';",
                "COMMENT ON COLUMN medical_consumables.consumable_code IS '医用耗材代码';",
                "COMMENT ON COLUMN medical_consumables.serial_number IS '流水号';",
                "COMMENT ON COLUMN medical_consumables.registration_cert_no IS '注册证编号';",
                "COMMENT ON COLUMN medical_consumables.registration_record_no IS '注册备案证号';",
                "COMMENT ON COLUMN medical_consumables.original_registration_record_no IS '原注册备案号';",
                "COMMENT ON COLUMN medical_consumables.registration_product_name IS '注册备案产品名称';",
                "COMMENT ON COLUMN medical_consumables.old_registration_record_no IS '旧注册备案证号';",
                "COMMENT ON COLUMN medical_consumables.old_registration_product_name IS '旧注册备案产品名称';",
                "COMMENT ON COLUMN medical_consumables.registrant IS '注册、备案人';",
                "COMMENT ON COLUMN medical_consumables.consumable_category IS '耗材分类';",
                "COMMENT ON COLUMN medical_consumables.single_product_code IS '单件产品编号';",
                "COMMENT ON COLUMN medical_consumables.single_product_name IS '单件产品名称';",
                "COMMENT ON COLUMN medical_consumables.enterprise_name IS '耗材企业';",
                "COMMENT ON COLUMN medical_consumables.specification IS '规格';",
                "COMMENT ON COLUMN medical_consumables.model IS '型号';",
                "COMMENT ON COLUMN medical_consumables.udi_di IS 'UDI-DI';",
                "COMMENT ON COLUMN medical_consumables.created_at IS '创建时间';",
                "COMMENT ON COLUMN medical_consumables.updated_at IS '更新时间';",
                "COMMENT ON COLUMN medical_consumables.status IS '状态:1=正常,2=停用';"
            ]
            
            with engine.connect() as con:
                 con.execute(text(create_table_sql))
                 for idx_sql in index_sqls:
                     con.execute(text(idx_sql))
                 con.commit()
                 
                 result = con.execute(text("SELECT COUNT(*) FROM medical_consumables"))
                 initial_db_count = result.scalar()
                 
            columns = [c for c in df.columns if c != 'uuid']
            all_columns = ['uuid'] + columns
            column_list = ", ".join([f"{col}" for col in all_columns])
            
            logger.info("正在根据 Excel 与数据库差异更新状态并插入数据...")
            
            with engine.connect() as con:
                result = con.execute(text("SELECT COUNT(*) FROM medical_consumables"))
                initial_db_count = result.scalar()
                
                update_sql = f"""
                UPDATE medical_consumables
                SET status = 2
                WHERE uuid NOT IN (SELECT uuid FROM {temp_table_name})
                """
                
                insert_sql = f"""
                INSERT INTO medical_consumables ({column_list})
                SELECT {column_list} FROM {temp_table_name}
                ON CONFLICT (uuid) DO UPDATE SET status = EXCLUDED.status
                """
                
                con.execute(text(update_sql))
                con.execute(text(insert_sql))
                con.execute(text(f"DROP TABLE {temp_table_name}"))
                result = con.execute(text("SELECT COUNT(*) FROM medical_consumables"))
                final_db_count = result.scalar()
                con.commit()
            
            added_rows = final_db_count - initial_db_count
            
            actual_added = added_rows 
            
            success_msg = (
                f"数据处理完成!\n"
                f"数据库: PostgreSQL\n"
                f"入库前记录数: {initial_db_count}\n"
                f"入库后记录数: {final_db_count}\n"
                f"实际新增记录数: {actual_added}\n"
                f"Excel 有效记录数: {len(df)}\n"
                f"重复/已存在记录数: {len(df) - actual_added}"
            )
            logger.info(success_msg)
             
        except Exception as e:
            error_msg = f"数据库操作错误: {e}"
            logger.error(error_msg)

    def process_excels_to_db(self, file_paths: list[str]):
        valid_files = [
            p
            for p in file_paths
            if p
            and os.path.exists(p)
            and (p.lower().endswith('.xls') or p.lower().endswith('.xlsx'))
        ]
        invalid_files = [p for p in file_paths if p and p not in valid_files]
        if not valid_files:
            logger.error("没有可用的 Excel 文件进行合并入库。")
            return
        logger.info(f"将合并 {len(valid_files)} 个 Excel 文件后统一入库。")
        if invalid_files:
            logger.warning(f"以下文件在合并时未找到，将被忽略: {', '.join(invalid_files)}")
        try:
            dfs: list[pd.DataFrame] = []
            total_rows = 0
            column_mapping = {
                '医用耗材代码': 'consumable_code',
                '流水号': 'serial_number',
                '注册证编号': 'registration_cert_no',
                '注册备案证号': 'registration_record_no',
                '原注册备案号': 'original_registration_record_no',
                '注册备案产品名称': 'registration_product_name',
                '旧注册备案证号': 'old_registration_record_no',
                '旧注册备案产品名称': 'old_registration_product_name',
                '注册、备案人': 'registrant',
                '耗材分类': 'consumable_category',
                '单件产品编号': 'single_product_code',
                '单件产品名称': 'single_product_name',
                '耗材企业': 'enterprise_name',
                '规格': 'specification',
                '型号': 'model',
                '规格型号编号': 'spec_model_id',
                'UDI-DI': 'udi_di'
            }
            for fp in valid_files:
                df = pd.read_excel(fp, dtype={'流水号': str})
                logger.info(f"读取文件: {fp}，原始行数: {len(df)}")
                total_rows += len(df)
                df = df.rename(columns=column_mapping)
                if 'spec_model_id' not in df.columns:
                    logger.error(f"文件缺少 'spec_model_id' 列: {fp}")
                    continue
                df['status'] = 1
                df['consumable_code'] = df['consumable_code'].astype(str)
                df['serial_number'] = df['serial_number'].astype(str)
                df['uuid'] = df.apply(lambda r: f"{r['consumable_code']}-{r['serial_number']}", axis=1)
                dfs.append(df)

            if not dfs:
                logger.error("所有文件解析失败，入库中止。")
                return

            merged_df = pd.concat(dfs, ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=['uuid'])
            logger.info(
                f"合并前总行数: {total_rows}，去重后有效记录数: {len(merged_df)}，跨文件重复记录数: {total_rows - len(merged_df)}"
            )

            # 尝试连接 PostgreSQL
            try:
                engine = create_engine(self.db_url)
                with engine.connect() as con:
                    pass
                logger.info("成功连接到 PostgreSQL 数据库 (table: medical_consumables).")
            except Exception as e:
                logger.error(f"连接 PostgreSQL 失败: {e}")
                return

            temp_table_name = 'medical_consumables_temp'
            with engine.connect() as con:
                con.execute(text(f"DROP TABLE IF EXISTS {temp_table_name}"))
                con.commit()

            merged_df.to_sql(name=temp_table_name, con=engine, if_exists='replace', index=False, dtype={
                'uuid': types.VARCHAR(128),
                'spec_model_id': types.VARCHAR(64),
                'consumable_code': types.VARCHAR(50),
                'serial_number': types.VARCHAR(50),
                'registration_cert_no': types.VARCHAR(100),
                'registration_record_no': types.VARCHAR(100),
                'original_registration_record_no': types.VARCHAR(100),
                'registration_product_name': types.VARCHAR(255),
                'old_registration_record_no': types.VARCHAR(100),
                'old_registration_product_name': types.VARCHAR(255),
                'registrant': types.VARCHAR(255),
                'consumable_category': types.VARCHAR(100),
                'single_product_code': types.VARCHAR(100),
                'single_product_name': types.VARCHAR(255),
                'enterprise_name': types.VARCHAR(255),
                'specification': types.TEXT(),
                'model': types.TEXT(),
                'udi_di': types.VARCHAR(100),
                'status': types.INTEGER(),
            })

            create_table_sql = """
            CREATE TABLE IF NOT EXISTS medical_consumables (
                uuid VARCHAR(128) NOT NULL PRIMARY KEY,
                spec_model_id VARCHAR(64),
                consumable_code VARCHAR(50),
                serial_number VARCHAR(50),
                registration_cert_no VARCHAR(100),
                registration_record_no VARCHAR(100),
                original_registration_record_no VARCHAR(100),
                registration_product_name VARCHAR(255),
                old_registration_record_no VARCHAR(100),
                old_registration_product_name VARCHAR(255),
                registrant VARCHAR(255),
                consumable_category VARCHAR(100),
                single_product_code VARCHAR(100),
                single_product_name VARCHAR(255),
                enterprise_name VARCHAR(255),
                specification TEXT,
                model TEXT,
                udi_di VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status SMALLINT NOT NULL DEFAULT 1
            );
            """
            
            index_sqls = [
                "CREATE INDEX IF NOT EXISTS idx_consumable_code ON medical_consumables (consumable_code);",
                "CREATE INDEX IF NOT EXISTS idx_registration_cert_no ON medical_consumables (registration_cert_no);",
                "CREATE INDEX IF NOT EXISTS idx_spec_model_id ON medical_consumables (spec_model_id);",
                "COMMENT ON TABLE medical_consumables IS '医用耗材分类与代码表';",
                "COMMENT ON COLUMN medical_consumables.uuid IS '主键 (医用耗材代码 + 流水号)';",
                "COMMENT ON COLUMN medical_consumables.spec_model_id IS '规格型号编号';",
                "COMMENT ON COLUMN medical_consumables.consumable_code IS '医用耗材代码';",
                "COMMENT ON COLUMN medical_consumables.serial_number IS '流水号';",
                "COMMENT ON COLUMN medical_consumables.registration_cert_no IS '注册证编号';",
                "COMMENT ON COLUMN medical_consumables.registration_record_no IS '注册备案证号';",
                "COMMENT ON COLUMN medical_consumables.original_registration_record_no IS '原注册备案号';",
                "COMMENT ON COLUMN medical_consumables.registration_product_name IS '注册备案产品名称';",
                "COMMENT ON COLUMN medical_consumables.old_registration_record_no IS '旧注册备案证号';",
                "COMMENT ON COLUMN medical_consumables.old_registration_product_name IS '旧注册备案产品名称';",
                "COMMENT ON COLUMN medical_consumables.registrant IS '注册、备案人';",
                "COMMENT ON COLUMN medical_consumables.consumable_category IS '耗材分类';",
                "COMMENT ON COLUMN medical_consumables.single_product_code IS '单件产品编号';",
                "COMMENT ON COLUMN medical_consumables.single_product_name IS '单件产品名称';",
                "COMMENT ON COLUMN medical_consumables.enterprise_name IS '耗材企业';",
                "COMMENT ON COLUMN medical_consumables.specification IS '规格';",
                "COMMENT ON COLUMN medical_consumables.model IS '型号';",
                "COMMENT ON COLUMN medical_consumables.udi_di IS 'UDI-DI';",
                "COMMENT ON COLUMN medical_consumables.created_at IS '创建时间';",
                "COMMENT ON COLUMN medical_consumables.updated_at IS '更新时间';",
                "COMMENT ON COLUMN medical_consumables.status IS '状态:1=正常,2=停用';"
            ]

            with engine.connect() as con:
                con.execute(text(create_table_sql))
                for idx_sql in index_sqls:
                    con.execute(text(idx_sql))
                con.commit()

                result = con.execute(text("SELECT COUNT(*) FROM medical_consumables"))
                initial_db_count = result.scalar()

            columns = [c for c in merged_df.columns if c != 'uuid']
            all_columns = ['uuid'] + columns
            column_list = ", ".join([f"{col}" for col in all_columns])

            logger.info("根据合并数据更新状态并插入数据...")
            with engine.connect() as con:
                result = con.execute(text("SELECT COUNT(*) FROM medical_consumables"))
                initial_db_count = result.scalar()

                update_sql = f"""
                UPDATE medical_consumables
                SET status = 2
                WHERE uuid NOT IN (SELECT uuid FROM {temp_table_name})
                """
                
                insert_sql = f"""
                INSERT INTO medical_consumables ({column_list})
                SELECT {column_list} FROM {temp_table_name}
                ON CONFLICT (uuid) DO UPDATE SET status = EXCLUDED.status
                """

                con.execute(text(update_sql))
                con.execute(text(insert_sql))
                con.execute(text(f"DROP TABLE {temp_table_name}"))
                result = con.execute(text("SELECT COUNT(*) FROM medical_consumables"))
                final_db_count = result.scalar()
                con.commit()

            added_rows = final_db_count - initial_db_count
            actual_added = added_rows
            logger.info(f"合并入库完成 | 入库前: {initial_db_count} | 入库后: {final_db_count} | 新增: {actual_added} | 合并记录: {len(merged_df)}")
        except Exception as e:
            logger.error(f"合并入库错误: {e}")

    def check_db_connection(self):
        """检查数据库连接"""
        try:
            engine = create_engine(self.db_url)
            with engine.connect() as con:
                pass
            logger.info(f"数据库连接检查通过: {self.db_url.split('@')[-1]}")
            return True
        except Exception as e:
            logger.error(f"数据库连接检查失败: {e}")
            return False

    def run(self):
        # 启动前先检查数据库
        if not self.check_db_connection():
            logger.error("无法连接到数据库，程序终止。")
            return

        try:
            self.clean_old_files()
        except Exception:
            pass

        accounts = [
            {"company": "河南驼人医疗器械集团有限公司", "username": "hntr01", "password": "Tr8100559@"},
            {"company": "河南驼人贝斯特医疗器械有限公司", "username": "bst666888", "password": "TRbst8100559@"},
            {"company": "河南省驼人医疗科技有限公司", "username": "TRKJ003", "password": "TRkj8100559#"},
            # {"company": "河南驼人医用卫生材料有限公司", "username": "TRSR0660", "password": "TRSR*0660"},
            # {"company": "河南驼人鑫安医疗器械有限公司", "username": "xinangongsi123", "password": "xinan123"},
            # {"company": "河南驼人医疗用品有限公司", "username": "trylyp05", "password": "trylyp123456"},
            {"company": "河南驼人新辉医疗科技有限公司", "username": "TRXH453600", "password": "Aa123456"},
        ]
        
        total_accounts = len(accounts)
        logger.info(f"任务开始执行... 总共需处理 {total_accounts} 个账号")
        
        results = {"success": [], "failed": []}
        downloaded_files: list[str] = []
        
        for index, account in enumerate(accounts, 1):
            logger.info(f"=== [进度 {index}/{total_accounts}] 正在处理账号: {account['company']} ({account['username']}) ===")
            max_tries = 3 # 每个账号重试次数
            
            try:
                for i in range(1, max_tries + 1):
                    logger.info(f"账号 {account['username']} 第 {i} 次尝试...")
                    try:
                        self.init_browser()
                        downloaded_file = self.download_file(account)
                        if downloaded_file:
                            downloaded_files.append(downloaded_file)
                            logger.info(f"账号 {account['username']} 处理成功.")
                            results["success"].append(account['username'])
                            break
                        else:
                            logger.warning(f"账号 {account['username']} 文件下载失败, 准备重试.")
                    except Exception as e:
                        logger.error(f"账号 {account['username']} 本次尝试出现错误: {e}")
                    finally:
                        try:
                            self.close_browser()
                        except Exception:
                            pass
                    if i < max_tries:
                        time.sleep(2)
                else:
                    logger.error(f"账号 {account['username']} 所有尝试均失败.")
                    results["failed"].append(account['username'])
            except Exception as e:
                logger.exception(f"处理账号 {account['username']} 时发生未处理异常: {e}")
                results["failed"].append(account['username'])
            
            # 账号间暂停
            time.sleep(3)
            
        if downloaded_files:
            logger.info(f"开始合并并统一入库 {len(downloaded_files)} 个文件: {', '.join(downloaded_files)}")
            self.process_excels_to_db(downloaded_files)
        else:
            logger.warning("无成功下载的文件，跳过入库步骤。")

        logger.info("="*50)
        logger.info(f"所有任务执行完毕. 总计: {total_accounts}, 成功: {len(results['success'])}, 失败: {len(results['failed'])}")
        if results['success']:
            logger.info(f"成功账号: {', '.join(results['success'])}")
        if results['failed']:
            logger.info(f"失败账号: {', '.join(results['failed'])}")
        logger.info("="*50)
        
        try:
            wechat_sink.flush()
        except Exception:
            pass

if __name__ == '__main__':
    importer = MedicalConsumableImporter()
    importer.run()
