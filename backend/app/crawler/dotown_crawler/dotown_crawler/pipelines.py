
import os
from pathlib import Path
import requests
import json
import logging
from sqlalchemy.future import select
from sqlalchemy import update
from backend.app.utils.pg_utils import PGUtils
from backend.app.utils.upload_utils import UploadUtils
import asyncio
from asgiref.sync import async_to_sync

from dotown_crawler.models import DotownImage, CrawlerTask
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class DotownDownloadPipeline:
    def process_item(self, item, spider):
        # 1. 下载图片到本地
        save_path = spider.save_dir / item['filename']
        
        # 检查本地文件是否存在
        if save_path.exists():
            spider.logger.info(f"⏭️ 跳过已存在: {item['filename']}")
            item['image_path'] = str(save_path)
            item['file_size'] = save_path.stat().st_size
            return item
            
        try:
            # 自动创建父目录（如果不存在）
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            response = requests.get(item['image_url'], timeout=10)
            if response.status_code == 200:
                save_path.write_bytes(response.content)
                item['image_path'] = str(save_path)
                item['file_size'] = len(response.content)
                spider.total_downloaded += 1
                spider.logger.info(f"✅ 已下载: {item['filename']}")
            else:
                spider.logger.error(f"❌ 下载失败 {item['image_url']}: Status {response.status_code}")
        except Exception as e:
            spider.logger.error(f"❌ 下载异常 {item['image_url']}: {e}")
            
        return item

class DotownDatabasePipeline:
    def open_spider(self, spider):
        self.session_factory = PGUtils.get_session_factory()

    async def process_item(self, item, spider):
        if not item.get('image_path'):
            return item
            
        async with self.session_factory() as session:
            try:
                # 检查数据库去重
                stmt = select(DotownImage).where(DotownImage.filename == item['filename'])
                result = await session.execute(stmt)
                exists = result.scalar_one_or_none()
                
                if exists:
                    return item
                
                # 入库
                db_image = DotownImage(
                    filename=item['filename'],
                    source_url=item['image_url'],
                    local_path=item['image_path'],
                    file_size=item['file_size'],
                    page_num=item['page_num']
                )
                session.add(db_image)
                await session.commit()
                # await session.refresh(db_image) # refresh requires bound session, which async session is.

                # 更新任务统计
                if hasattr(spider, 'task_id'):
                    # 注意：这里需要重新获取 task 或者直接执行 update 语句
                    # 简单起见，执行 update 语句
                    stmt = update(CrawlerTask).where(CrawlerTask.id == spider.task_id).values(
                        total_saved = CrawlerTask.total_saved + 1
                    )
                    await session.execute(stmt)
                    await session.commit()
            except Exception as e:
                spider.logger.error(f"数据库操作失败: {e}")
                await session.rollback()
        
        return item

class DotownS3Pipeline:
    def open_spider(self, spider):
        self.session_factory = PGUtils.get_session_factory()

    async def process_item(self, item, spider):
        if not item.get('image_path'):
            return item
            
        # 检查 S3 开关
        if os.getenv("S3_ENABLED", "false").lower() != "true":
            return item
            
        try:
            # 上传到 S3
            s3_key = f"dotown/{item['filename']}"
            local_path = Path(item['image_path']).resolve()
            
            # 直接调用异步上传
            s3_url = await UploadUtils.upload_local_file(local_path, s3_key)
            
            if s3_url:
                item['s3_key'] = s3_key
                item['s3_url'] = s3_url
                
                # 更新数据库
                async with self.session_factory() as session:
                    stmt = select(DotownImage).where(DotownImage.filename == item['filename'])
                    result = await session.execute(stmt)
                    db_image = result.scalar_one_or_none()
                    
                    if db_image:
                        db_image.s3_key = s3_key
                        db_image.s3_url = s3_url
                        db_image.is_uploaded = True
                        db_image.uploaded_at = datetime.now()
                        await session.commit()
                
                spider.logger.info(f"☁️ S3上传成功: {s3_key}")
        except Exception as e:
            spider.logger.error(f"❌ S3上传失败: {e}")
            
        return item

class FeishuNotificationPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def __init__(self, settings):
        webhook_url = settings.get("FEISHU_WEBHOOK") or os.getenv("FEISHU_DOTOWN_CRAWLER_WEBHOOK")
        
        # 如果只有 UUID，拼接成完整 URL
        if webhook_url and not webhook_url.startswith("http"):
             self.webhook_url = f"https://open.feishu.cn/open-apis/bot/v2/hook/{webhook_url}"
        else:
             self.webhook_url = webhook_url

        self.new_images_count = 0
        # self.db = next(get_db()) # 不需要 DB 连接

    def process_item(self, item, spider):
        # 只对新增图片计数
        # 这里的判断逻辑依赖于 DatabasePipeline 是否成功插入
        # 我们可以简单地在 spider 中维护计数，或者在 close_spider 时查询数据库
        if item.get('image_path'):
             # 假设能走到这里且没被去重就是新增的（需要更严谨的判断）
             # 这里简单加1，实际准确数字在 close_spider 统计
             self.new_images_count += 1
        return item

    def close_spider(self, spider):
        if not self.webhook_url:
            return

        # 查询任务信息
        total_crawled = spider.total_downloaded
        
        # 发送飞书通知
        msg = {
            "msg_type": "text",
            "content": {
                "text": f"🏁 Dotown 爬虫任务完成\n"
                        f"📊 本次新增下载: {total_crawled} 张\n"
                        f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        try:
            requests.post(self.webhook_url, json=msg, timeout=10)
            spider.logger.info("✅ 飞书通知发送成功")
        except Exception as e:
            spider.logger.error(f"❌ 飞书通知发送失败: {e}")
