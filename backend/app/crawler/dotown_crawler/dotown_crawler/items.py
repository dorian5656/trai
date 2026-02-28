
import scrapy
from datetime import datetime
from pydantic import BaseModel, Field

class DotownImageItem(scrapy.Item):
    image_url = scrapy.Field()
    filename = scrapy.Field()
    page_num = scrapy.Field()
    image_path = scrapy.Field()  # 本地保存路径
    s3_key = scrapy.Field()
    s3_url = scrapy.Field()
    file_size = scrapy.Field()
