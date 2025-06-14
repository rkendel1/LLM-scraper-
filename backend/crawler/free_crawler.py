import scrapy
from scrapy.crawler import CrawlerProcess

class FreeSearchSpider(scrapy.Spider):
    name = 'free_spider'
    start_urls = []

    def __init__(self, urls=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = urls or []

    def parse(self, response):
        yield {
            'url': response.url,
            'html': response.text
        }

def run_free_crawler(urls):
    process = CrawlerProcess()
    process.crawl(FreeSearchSpider, urls=urls)
    process.start()

    # Save output
    import json
    with open('output.json') as f:
        return json.load(f)
