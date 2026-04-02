"""
基础爬虫类
所有网站爬虫的基类
"""
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import time
import random

class BaseScraper:
    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        
    def get_headers(self):
        """获取随机 User-Agent 的请求头"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def fetch_page(self, url, use_playwright=False):
        """
        获取网页内容
        :param url: 目标 URL
        :param use_playwright: 是否使用 Playwright（用于动态加载的页面）
        :return: HTML 内容或 None
        """
        try:
            if use_playwright:
                return self.fetch_with_playwright(url)
            
            response = self.session.get(
                url, 
                headers=self.get_headers(),
                timeout=30,
                verify=True
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            time.sleep(random.uniform(1, 3))  # 随机延迟，避免被封
            return response.text
            
        except Exception as e:
            print(f"抓取失败 {url}: {str(e)}")
            return None
    
    def fetch_with_playwright(self, url):
        """使用 Playwright 抓取动态页面"""
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until='networkidle')
                content = page.content()
                browser.close()
                return content
        except Exception as e:
            print(f"Playwright 抓取失败 {url}: {str(e)}")
            return None
    
    def parse_html(self, html):
        """解析 HTML"""
        if not html:
            return None
        return BeautifulSoup(html, 'lxml')
    
    def safe_float(self, value, default=None):
        """安全转换为浮点数"""
        try:
            if value is None:
                return default
            return float(str(value).replace(',', '').strip())
        except:
            return default
    
    def safe_int(self, value, default=None):
        """安全转换为整数"""
        try:
            if value is None:
                return default
            return int(str(value).replace(',', '').strip())
        except:
            return default
