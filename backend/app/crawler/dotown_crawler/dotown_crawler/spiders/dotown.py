
import os
import scrapy
from dotown_crawler.items import DotownImageItem
from urllib.parse import urljoin
from pathlib import Path

class DotownSpider(scrapy.Spider):
    name = "dotown"
    allowed_domains = ["dotown.maeda-design-room.net"]
    
    # 默认配置，可通过 run_crawler 传递参数覆盖
    target_count = 1000
    start_page = 1
    max_page = 100
    save_dir = "/tmp/dotown_images"
    
    def __init__(self, target_count=1000, start_page=1, max_page=100, save_dir=None, *args, **kwargs):
        super(DotownSpider, self).__init__(*args, **kwargs)
        self.target_count = int(target_count)
        self.start_page = int(start_page)
        self.max_page = int(max_page)
        
        # 默认保存到 backend/static/dotown
        if save_dir:
            self.save_dir = Path(save_dir)
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
            self.save_dir = base_dir / "static" / "dotown"
            
        self.total_downloaded = 0
        
        # 确保目录存在
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
    def start_requests(self):
        base_url = "https://dotown.maeda-design-room.net/page/{}/"
        for page_num in range(self.start_page, self.max_page + 1):
            if self.total_downloaded >= self.target_count:
                break
            url = base_url.format(page_num)
            yield scrapy.Request(url, meta={'page_num': page_num})

    def parse(self, response):
        page_num = response.meta['page_num']
        
        # 提取图片链接
        img_urls = response.css('img::attr(src)').re(r'.*/uploads/.*\.(?:png|jpg|jpeg)')
        img_urls = list(set(img_urls)) # 去重
        
        if not img_urls:
            self.logger.warning(f"第 {page_num} 页未找到图片")
            return

        self.logger.info(f"第 {page_num} 页找到 {len(img_urls)} 张潜在图片")
        
        for src in img_urls:
            if self.total_downloaded >= self.target_count:
                return
                
            item = DotownImageItem()
            item['image_url'] = src
            item['page_num'] = page_num
            
            # 生成文件名
            filename = src.split('/')[-1].split('?')[0]
            item['filename'] = filename
            
            # 下载图片 (通过 Pipeline 处理)
            yield item
