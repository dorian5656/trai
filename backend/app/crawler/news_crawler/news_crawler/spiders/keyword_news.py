import scrapy
from urllib.parse import urlparse, quote

class KeywordNewsSpider(scrapy.Spider):
    name = "keyword_news"
    # 允许的域名列表
    allowed_domains = ["sina.com.cn", "baidu.com", "ithome.com", "bing.com"]

    def __init__(self, keyword="小米", *args, **kwargs):
        super(KeywordNewsSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword
        self.logger.info(f"Initializing spider with keyword: {self.keyword}")
        
        q = quote(self.keyword)
        self.start_urls = [
            f"https://search.sina.com.cn/?q={q}&c=news",
            f"https://www.baidu.com/s?rtt=1&bsst=1&cl=2&tn=news&word={q}",
            f"https://cn.bing.com/news/search?q={q}"
        ]

    def parse(self, response):
        self.logger.info(f"正在抓取: {response.url}")
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
        self.logger.info(f"[新浪] 找到 {len(cards)} 条线索")

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
            
        self.logger.info(f"[百度] 找到 {len(cards)} 条线索")

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
        # IT之家搜索结果通常在 div.result_list li 或 div.block
        # 注意: IT之家搜索可能是 CSR (客户端渲染) 或者简单的 HTML
        # 我们先假设是 HTML。如果是 CSR，可能需要 API。
        # 检查源代码发现是 div.result-list -> li
        cards = response.css('ul.result-list li')
        self.logger.info(f"[IT之家] 找到 {len(cards)} 条线索")

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

        self.logger.info(f"[Bing] 找到 {len(cards)} 条线索")

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
