import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.linkextractors import LinkExtractor
import json
import os

class SiteSpider(scrapy.Spider):
    name = 'site_spider'
    custom_settings = {
        'LOG_LEVEL': 'ERROR',
        'FEED_FORMAT': 'json',
        'FEED_URI': 'output.json'
    }

    def __init__(self, *args, domain=None, depth=2, **kwargs):
        self.start_urls = [f'https://{domain}'] 
        self.allowed_domains = [domain]
        self.max_depth = int(depth)
        super().__init__(*args, **kwargs)

    def parse(self, response):
        yield {
            'url': response.url,
            'html': response.text
        }

        if response.meta.get('depth', 0) < self.max_depth:
            le = LinkExtractor()
            for link in le.extract_links(response):
                yield scrapy.Request(link.url, callback=self.parse)

def run_crawler(domain, depth):
    process = CrawlerProcess()
    process.crawl(SiteSpider, domain=domain, depth=depth)
    process.start()

    try:
        with open("output.json") as f:
            return json.load(f)
    except Exception as e:
        print("No output file found:", e)
        return []
