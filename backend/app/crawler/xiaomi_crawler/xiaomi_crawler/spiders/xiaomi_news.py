import scrapy

class XiaomiNewsSpider(scrapy.Spider):
    name = "xiaomi_news"
    allowed_domains = ["sina.com.cn"]
    # 搜索 "小米" - 新浪新闻搜索
    start_urls = ["https://search.sina.com.cn/?q=%E5%B0%8F%E7%B1%B3&c=news"]

    def parse(self, response):
        self.logger.info(f"正在抓取: {response.url}")
        
        # 新浪新闻搜索结果
        cards = response.css('div.box-result')
        self.logger.info(f"找到 {len(cards)} 条新闻线索")

        for card in cards:
            # 标题
            title = card.css('h2 a::text').get()
            # 链接
            link = card.css('h2 a::attr(href)').get()
            # 摘要
            snippet = card.css('p.content::text').get()
            # 来源/时间
            source = card.css('span.fgray_time::text').get()

            if title and link:
                yield {
                    'title': title.strip(),
                    'link': link,
                    'snippet': snippet.strip() if snippet else None,
                    'source': source.strip() if source else None,
                }
