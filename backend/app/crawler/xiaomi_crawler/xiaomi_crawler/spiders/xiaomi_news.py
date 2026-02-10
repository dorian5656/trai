import scrapy
from urllib.parse import urlparse, quote

class XiaomiNewsSpider(scrapy.Spider):
    name = "xiaomi_news"
    # 允许的域名列表
    allowed_domains = ["sina.com.cn", "baidu.com", "ithome.com", "bing.com"]
    
    # 关键词列表
    keywords = ["小米", "小米汽车", "小米手机", "雷军"]
    
    def start_requests(self):
        """生成初始请求"""
        # 每个关键词抓取前 3 页
        max_pages = 3
        
        for kw in self.keywords:
            kw_encoded = quote(kw)
            
            # 1. 新浪新闻 (page 参数)
            for page in range(1, max_pages + 1):
                url = f"https://search.sina.com.cn/?q={kw_encoded}&c=news&page={page}"
                yield scrapy.Request(url, callback=self.parse)
            
            # 2. 百度资讯 (pn 参数, 0, 10, 20...)
            for page in range(1, max_pages + 1):
                pn = (page - 1) * 10
                url = f"https://www.baidu.com/s?rtt=1&bsst=1&cl=2&tn=news&word={kw_encoded}&pn={pn}"
                yield scrapy.Request(url, callback=self.parse)
            
            # 3. 必应新闻 (first 参数, 1, 11, 21...)
            for page in range(1, max_pages + 1):
                first = (page - 1) * 10 + 1
                url = f"https://cn.bing.com/news/search?q={kw_encoded}&first={first}"
                yield scrapy.Request(url, callback=self.parse)

            # 4. IT之家 (暂时跳过，DNS 不稳定)
            # url = f"https://search.ithome.com/search?q={kw_encoded}"
            # yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        # self.logger.info(f"正在抓取: {response.url}")
        domain = urlparse(response.url).netloc

        if "sina.com.cn" in domain:
            yield from self.parse_sina(response)
        elif "baidu.com" in domain:
            yield from self.parse_baidu(response)
        elif "ithome.com" in domain:
            yield from self.parse_ithome(response)
        elif "bing.com" in domain:
            yield from self.parse_bing(response)
        else:
            self.logger.warning(f"未知域名: {domain}")

    def parse_sina(self, response):
        """解析新浪新闻"""
        cards = response.css('div.box-result')
        # self.logger.info(f"[新浪] 找到 {len(cards)} 条线索")

        for card in cards:
            title = card.css('h2 a::text').get()
            link = card.css('h2 a::attr(href)').get()
            snippet = card.css('p.content::text').get()
            source = card.css('span.fgray_time::text').get()

            if title and link:
                yield {
                    'platform': 'Sina',
                    'title': title.strip(),
                    'link': link,
                    'snippet': snippet.strip() if snippet else None,
                    'source': source.strip() if source else None,
                }

    def parse_baidu(self, response):
        """解析百度资讯"""
        # 百度资讯通常是一个 div.result-op.c-container.xpath-log
        cards = response.css('div.result-op')
        if not cards:
            cards = response.css('div.c-container')
            
        # self.logger.info(f"[百度] 找到 {len(cards)} 条线索")

        for card in cards:
            # 标题通常在 h3.news-title_1YtI1 a (新版) 或 h3.c-title a (旧版)
            title = card.css('h3 a::text').get()
            if not title:
                # 尝试获取所有文本拼接 (有时会有em标签高亮)
                title = "".join(card.css('h3 a *::text').getall())
            
            link = card.css('h3 a::attr(href)').get()
            
            # 摘要
            snippet = "".join(card.css('div.c-summary_2s9E3 *::text').getall()) # 新版
            if not snippet:
                 snippet = "".join(card.css('div.c-summary *::text').getall()) # 旧版
            
            # 来源/时间
            source = "".join(card.css('div.news-source_Xj4Dv *::text').getall()) # 新版
            if not source:
                 source = "".join(card.css('div.c-span-last *::text').getall())

            if title and link:
                yield {
                    'platform': 'Baidu',
                    'title': title.strip(),
                    'link': link,
                    'snippet': snippet.strip() if snippet else None,
                    'source': source.strip() if source else None,
                }

    def parse_ithome(self, response):
        """解析 IT之家"""
        cards = response.css('ul.result-list li')
        
        for card in cards:
            title = card.css('a.result-title::text').get()
            if not title:
                title = "".join(card.css('a.result-title *::text').getall())
                
            link = card.css('a.result-title::attr(href)').get()
            
            snippet = card.css('div.result-summary::text').get()
            
            # 时间/来源
            source = card.css('div.result-meta span::text').get()

            if title and link:
                yield {
                    'platform': 'ITHome',
                    'title': title.strip(),
                    'link': link,
                    'snippet': snippet.strip() if snippet else None,
                    'source': source.strip() if source else None,
                }

    def parse_bing(self, response):
        """解析必应新闻"""
        cards = response.css('div.news-card')
        if not cards:
            cards = response.css('div.card-with-cluster')
        if not cards:
             cards = response.css('div.algo')

        # self.logger.info(f"[Bing] 找到 {len(cards)} 条线索")

        for card in cards:
            title = card.css('a.title::text').get()
            if not title:
                title = card.css('h2 a::text').get()
            
            link = card.css('a.title::attr(href)').get()
            if not link:
                link = card.css('h2 a::attr(href)').get()

            snippet = card.css('div.snippet::text').get()
            if not snippet:
                snippet = card.css('div.b_caption p::text').get()

            source = card.css('div.source span::text').get()
            if not source:
                 source = card.css('div.b_attribution cite::text').get()

            if title and link:
                yield {
                    'platform': 'Bing',
                    'title': title.strip(),
                    'link': link,
                    'snippet': snippet.strip() if snippet else None,
                    'source': source.strip() if source else None,
                }
