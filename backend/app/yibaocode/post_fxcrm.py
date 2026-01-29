#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：post_fxcrm.py
# 作者：liuhd
# 日期：2026-01-28 09:48:00
# 描述：将医保数据推送到纷享销客 CRM 系统（模块导入版）

"""
将医保数据推送到纷享销客 CRM 系统

功能：从本地数据库读取医保码数据，推送到纷享销客 ERP 接口。
"""
import os
import requests
import sys
import time
import json
import uuid
import urllib.parse
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from loguru import logger

# 动态添加项目根目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from wechat import wechat_service
except ImportError:
    wechat_service = None
try:
    from feishu import feishu_service
except Exception:
    feishu_service = None

_logging_initialized = False

def setup_logging():
    global _logging_initialized
    if _logging_initialized:
        return

    # 移除 setup_logging 中的控制台输出配置，避免被导入时重复添加
    # logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    
    try:
        _uploads_log_dir = os.path.join(project_root, "uploads", "nhsa", "logs")
        os.makedirs(_uploads_log_dir, exist_ok=True)
        logger.add(os.path.join(_uploads_log_dir, "sync_fxiaoke.log"), rotation="10 MB", encoding="utf-8", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}")
    except Exception:
        pass
    
    if wechat_service:
        wechat_sink = WeChatSink()
        logger.add(wechat_sink.write, level="INFO")
    
    _logging_initialized = True

# 移除顶层的自动配置，改为在 FxiaokeSyncer 初始化时调用
# 兼容单独运行
if __name__ == "__main__":
    logger.remove() # 单独运行时，重置默认 handler
    logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    setup_logging()

class WeChatSink:
    """自定义 Loguru Sink，用于缓冲并发送微信消息"""
    def __init__(self):
        self.buffer = []
        self.last_send_time = time.time()
        self.max_buffer_size = 50
        self.max_interval = 15.0

    def write(self, message):
        record = message.record
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
        if wechat_service:
            wechat_service.send_group_message(f"[CRM同步]\n{content}")
        else:
            print(f"[WeChat Fallback] {content}")
        if feishu_service:
            feishu_service.send_nhsa_message("CRM同步", content)
        self.buffer = []
        self.last_send_time = time.time()



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
        """创建日志表 post_fxcrm_log"""
        if not self.engine:
            return
            
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS post_fxcrm_log (
            uuid VARCHAR(36) NOT NULL PRIMARY KEY,
            log_time TIMESTAMP NOT NULL,
            log_level VARCHAR(20) NOT NULL,
            message TEXT
        );
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text(create_table_sql))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_post_fxcrm_log_time ON post_fxcrm_log (log_time);"))
                conn.execute(text("COMMENT ON TABLE post_fxcrm_log IS 'CRM同步日志表';"))
                conn.execute(text("COMMENT ON COLUMN post_fxcrm_log.uuid IS '唯一标识';"))
                conn.execute(text("COMMENT ON COLUMN post_fxcrm_log.log_time IS '日志时间';"))
                conn.execute(text("COMMENT ON COLUMN post_fxcrm_log.log_level IS '日志级别';"))
                conn.execute(text("COMMENT ON COLUMN post_fxcrm_log.message IS '日志内容';"))
                conn.commit()
        except Exception as e:
            logger.error(f"创建表 post_fxcrm_log 失败: {e}")

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
        INSERT INTO post_fxcrm_log (uuid, log_time, log_level, message)
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

class FxiaokeSyncer:
    def __init__(self):
        # 确保日志已初始化
        setup_logging()

        # 加载环境变量
        self._load_env()
        
        self.db_url = os.getenv('POSTGRES_DB_YIBAO')
        if not self.db_url:
            raise ValueError("未找到 POSTGRES_DB_YIBAO 环境变量")
            
        # 使用 pool_pre_ping 自动检测连接活性，pool_recycle 自动回收旧连接
        self.engine = create_engine(
            self.db_url,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        
        # 纷享销客 API 配置 (示例)
        self.api_base = os.getenv("FXIAOKE_API_BASE", "https://open.fxiaoke.com/cgi")
        self.app_id = os.getenv("FXIAOKE_APP_ID", "")
        self.app_secret = os.getenv("FXIAOKE_APP_SECRET", "")
        self.permanent_code = os.getenv("FXIAOKE_PERMANENT_CODE", "")
        self.dry_run = os.getenv("FXIAOKE_DRY_RUN", "0") == "1"
        self.progress_step = int(os.getenv("FXIAOKE_PROGRESS_STEP", "100"))
        self.direct_post_url = os.getenv("FXIAOKE_DIRECT_POST_URL", "")
        _hdr = os.getenv("FXIAOKE_DIRECT_POST_HEADERS", "")
        try:
            self.direct_post_headers = json.loads(_hdr) if _hdr else {}
        except Exception:
            self.direct_post_headers = {}
        self.dc_id = os.getenv("FXIAOKE_DC_ID", "")
        self.tenant_id = os.getenv("FXIAOKE_TENANT_ID", "")
        self.push_token = os.getenv("FXIAOKE_TOKEN", "")

    def _load_env(self):
        current = os.path.dirname(os.path.abspath(__file__))
        # 向上查找 .env
        while current != os.path.dirname(current):
            if os.path.exists(os.path.join(current, '.env')):
                load_dotenv(os.path.join(current, '.env'))
                break
            current = os.path.dirname(current)

    def get_access_token(self):
        """获取纷享销客 Access Token"""
        url = f"{self.api_base}/corpAccessToken/get/V2"
        payload = {
            "appId": self.app_id,
            "appSecret": self.app_secret,
            "permanentCode": self.permanent_code
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                res = resp.json()
                if res.get("errorCode") == 0:
                    return res.get("corpAccessToken")
                else:
                    logger.error(f"获取 Token 失败: {res.get('errorMessage')}")
            return None
        except Exception as e:
            logger.error(f"获取 Token 失败: {e}")
            return None

    def fetch_data(self):
        """一次性拉取所有待同步数据，避免长连接持有"""
        data = []
        try:
            with self.engine.connect() as conn:
                # 假设表名为 medical_consumables，如果是其他表名修改此处
                # 优先同步未处理的数据 (status=0?)
                logger.info("正在从数据库拉取数据...")
                # 检查表是否存在
                conn.execute(text("SELECT 1 FROM medical_consumables LIMIT 1"))
                sql = "SELECT * FROM medical_consumables"
                result = conn.execute(text(sql))
                # 将 SQLAlchemy Row 转换为 dict
                data = [dict(row._mapping) for row in result]
        except Exception as e:
            logger.error(f"数据库读取失败: {e}")
        
        return data

    def push_data(self):
        """主推送逻辑"""
        # 1. 先拉取数据，随后关闭 DB 连接，避免处理过程中的 Timeout
        records = self.fetch_data()
        total = len(records)
        logger.info(f"已获取 {total} 条数据，准备推送...")
        
        if total == 0:
            logger.info("无数据需要推送")
            return
        token = None
        if not self.dry_run and not self.direct_post_url:
            token = self.get_access_token()
            if not token:
                logger.error("无法获取 Access Token，终止推送")
                try:
                    if feishu_service:
                        feishu_service.send_rich_post("CRM同步失败", ["无法获取 Access Token，请检查 appId/appSecret/permanentCode"])
                    if wechat_service:
                        wechat_service.send_markdown("**CRM同步失败**\n> 无法获取 Access Token，请检查 appId/appSecret/permanentCode")
                except Exception:
                    pass
                return

        success_count = 0
        fail_count = 0
        success_traces = []
        
        # 2. 遍历推送 (此时不持有 DB 连接)
        url = f"{self.api_base}/crm/v2/object/create"

        for i, record in enumerate(records):
            try:
                # 构造符合纷享销客要求的数据包
                # 假设同步到 "MedicalConsumable" 对象
                if self.dry_run:
                    success_count += 1
                    logger.info(f"模拟推送成功 (ID: {record.get('id')}, 名称: {record.get('file_name','未命名')})")
                    try:
                        if feishu_service:
                            feishu_service.send_rich_post("CRM同步成功", [f"ID: {record.get('id')}", f"名称: {record.get('file_name','未命名')}"])
                    except Exception:
                        pass
                else:
                    if self.direct_post_url:
                        code = str(record.get("consumable_code") or "").strip()
                        serial = str(record.get("serial_number") or "").strip()
                        unique_id = f"{code}-{serial}" if code and serial else record.get("id") or ""
                        body = {
                            "objAPIName": "MedicalInsuranceCodeFile",
                            "masterFieldVal": {
                                "consumablesCategory": record.get("consumable_category", ""),
                                "consumablesEnterprise": record.get("enterprise_name", ""),
                                "id": unique_id,
                                "medicalConsumablesCode": code,
                                "model": record.get("model", ""),
                                "oldRegistrationFilingCertificateNumber": record.get("old_registration_record_no", ""),
                                "oldRegistrationFilingProductName": record.get("old_registration_product_name", ""),
                                "originalRegistrationFilingNumber": record.get("original_registration_record_no", ""),
                                "registrantFilingPerson": record.get("registrant", ""),
                                "registrationCertificateNumber": record.get("registration_cert_no", ""),
                                "registrationFilingCertificateNumber": record.get("registration_record_no", ""),
                                "registrationFilingProductName": record.get("registration_product_name", ""),
                                "serialNumber": serial,
                                "singleProductName": record.get("single_product_name", ""),
                                "singleProductNumber": record.get("single_product_code", ""),
                                "specification": record.get("specification", ""),
                                "specificationModelNumber": record.get("spec_model_id", ""),
                                "status": int(record.get("status", 1) or 1),
                                "udiDi": record.get("udi_di", "")
                            }
                        }
                        headers = {
                            "Content-Type": "application/json",
                            "dataCenterId": self.dc_id,
                            "tenantId": self.tenant_id,
                            "objectApiName": "MedicalInsuranceCodeFile",
                            "id": unique_id,
                            "version": "v1",
                            "directSync": "false",
                            "token": self.push_token
                        }
                        if self.direct_post_headers:
                            headers.update(self.direct_post_headers)
                        resp = requests.post(self.direct_post_url, json=body, headers=headers, timeout=15)
                        ok = False
                        err_msg = ""
                        trace_msg = ""
                        try:
                            res_json = resp.json()
                            err_code = res_json.get("errCode")
                            err_msg = res_json.get("errMsg") or ""
                            trace_msg = res_json.get("traceMsg") or ""
                            ok = err_code == "s106240000"
                        except Exception:
                            ok = (200 <= resp.status_code < 300)
                        if ok:
                            success_count += 1
                            if trace_msg:
                                success_traces.append((unique_id, trace_msg))
                        else:
                            fail_count += 1
                            logger.error(f"推送失败 (ID: {record.get('id')}): HTTP {resp.status_code} {resp.text[:200]} {err_msg}")
                            try:
                                if feishu_service:
                                    feishu_service.send_rich_post("CRM同步失败", [f"ID: {record.get('id')}", f"错误: {err_msg or 'HTTP ' + str(resp.status_code)}"])
                            except Exception:
                                pass
                    else:
                        payload = {
                            "corpAccessToken": token,
                            "corpId": self.app_id,
                            "data": {
                                "object_data": {
                                    "data": {
                                        "name": record.get("file_name", "未命名"),
                                        "code": record.get("file_hash", ""),
                                        "content": record.get("content", "")
                                    }
                                },
                                "api_name": "MedicalConsumable"
                            }
                        }
                        resp = requests.post(url, json=payload, timeout=10)
                        res = resp.json()
                        if res.get("errorCode") == 0:
                            success_count += 1
                            try:
                                if feishu_service:
                                    feishu_service.send_rich_post("CRM同步成功", [f"ID: {record.get('id')}", f"名称: {record.get('file_name','未命名')}"])
                            except Exception:
                                pass
                        else:
                            fail_count += 1
                            logger.error(f"推送失败 (ID: {record.get('id')}): {res.get('errorMessage')}")
                            try:
                                if feishu_service:
                                    feishu_service.send_rich_post("CRM同步失败", [f"ID: {record.get('id')}", f"错误: {res.get('errorMessage')}"])
                            except Exception:
                                pass
                
                # 每 1000 条打印一次进度
                if (i + 1) % self.progress_step == 0:
                    logger.info(f"进度: {i + 1}/{total} 成功:{success_count} 失败:{fail_count}")
                    try:
                        if feishu_service:
                            feishu_service.send_rich_post("CRM同步进度", [f"{i + 1}/{total}", f"成功: {success_count}", f"失败: {fail_count}"])
                    except Exception:
                        pass
                    
            except Exception as e:
                fail_count += 1
                logger.error(f"推送异常 (ID: {record.get('id')}): {e}")

        logger.info(f"推送任务完成! 总计: {total}, 成功: {success_count}, 失败: {fail_count}")
        logger.info("=" * 50)
        if self.dry_run:
            logger.info("已启用 DRY_RUN，跳过 ERP 推送，仅发送通知")
        if self.direct_post_url:
            logger.info(f"已启用 DIRECT_POST_URL 推送: {self.direct_post_url}")
        try:
            if feishu_service:
                _public = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{os.getenv('PORT','5689')}")
                _detail_url = f"{_public}/uploads/nhsa/logs/sync_fxiaoke.log"
                _paragraphs = [
                    [{"tag":"text","text":f"总计: {total}"}],
                    [{"tag":"text","text":f"成功: {success_count}"}],
                    [{"tag":"text","text":f"失败: {fail_count}"}],
                    [{"tag":"a","text":"详情","href":_detail_url}]
                ]
                try:
                    for uid, trace in success_traces[:5]:
                        _paragraphs.append([{"tag":"text","text":f"{uid} | {trace}"}])
                except Exception:
                    pass
                try:
                    _uid = os.getenv("FEISHU_WUHAOFENG_USER_ID")
                    if _uid:
                        _paragraphs.append([{"tag":"at","user_id":_uid}])
                except Exception:
                    pass
                feishu_service.send_post("CRM同步完成", _paragraphs)
            if wechat_service:
                wechat_service.send_markdown(f"**CRM同步完成**\n> 总计: {total}\n> 成功: {success_count}\n> 失败: {fail_count}")
        except Exception:
            pass

    def run(self):
        try:
            self.push_data()
        finally:
            # 显式关闭引擎池，防止脚本退出时残留连接报错
            self.engine.dispose()

if __name__ == "__main__":
    try:
        # 添加数据库 Sink
        try:
            db_sink = DatabaseSink()
            logger.add(db_sink.write, level="INFO")
        except Exception as e:
            logger.error(f"添加数据库 Sink 失败: {e}")

        syncer = FxiaokeSyncer()
        syncer.run()
    except Exception as e:
        logger.error(f"执行过程中发生全局异常: {e}")
