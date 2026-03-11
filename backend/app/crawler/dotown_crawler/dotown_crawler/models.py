
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, BigInteger
from sqlalchemy.sql import func
from backend.app.utils.pg_utils import Base

class DotownImage(Base):
    __tablename__ = "crawler_dotown_images"

    id = Column(BigInteger, primary_key=True, index=True)
    filename = Column(String(255), unique=True, nullable=False, index=True, comment="文件名")
    source_url = Column(String(1024), nullable=False, comment="原始URL")
    s3_key = Column(String(1024), nullable=True, comment="S3存储Key")
    s3_url = Column(String(1024), nullable=True, comment="S3访问URL")
    local_path = Column(String(1024), nullable=True, comment="本地存储路径")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    width = Column(Integer, nullable=True, comment="图片宽度")
    height = Column(Integer, nullable=True, comment="图片高度")
    
    # 爬取信息
    page_num = Column(Integer, nullable=True, comment="来源页码")
    crawled_at = Column(DateTime(timezone=True), server_default=func.now(), comment="爬取时间")
    uploaded_at = Column(DateTime(timezone=True), nullable=True, comment="上传S3时间")
    
    # 状态
    is_uploaded = Column(Boolean, default=False, comment="是否已上传S3")
    is_deleted = Column(Boolean, default=False, comment="是否已删除")

class CrawlerTask(Base):
    __tablename__ = "crawler_tasks"

    id = Column(BigInteger, primary_key=True, index=True)
    task_name = Column(String(100), nullable=False, comment="任务名称")
    spider_name = Column(String(100), nullable=False, comment="爬虫名称")
    
    # 任务配置
    target_count = Column(Integer, default=1000, comment="目标数量")
    start_page = Column(Integer, default=1, comment="起始页码")
    current_page = Column(Integer, default=1, comment="当前页码")
    
    # 统计
    total_crawled = Column(Integer, default=0, comment="本次爬取数量")
    total_saved = Column(Integer, default=0, comment="本次入库数量")
    
    # 状态
    status = Column(String(50), default="pending", comment="状态: pending/running/stopped/completed/failed")
    error_msg = Column(Text, nullable=True, comment="错误信息")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
