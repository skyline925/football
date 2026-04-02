"""
足球数据爬虫主程序
支持两种模式：
  SCRAPER_MODE=overseas  → 爬取海外网站（Railway/云服务器）
  SCRAPER_MODE=domestic  → 爬取国内网站（本地运行）
  SCRAPER_MODE=all       → 两者都爬
"""
import os
import sys
import schedule
import time
from datetime import datetime, timedelta

# Railway 环境下不加载 .env（用系统环境变量）
if os.getenv("RAILWAY_ENVIRONMENT") is None:
    from dotenv import load_dotenv
    load_dotenv()

# 导入数据库模块
sys.path.append(os.path.dirname(__file__))
from database import init_db, upsert_match, insert_odds, update_team_info, get_today_matches

# 海外爬虫
from scrapers.oddsportal_scraper import OddsPortalScraper
from scrapers.flashscore_scraper import FlashScoreScraper
from scrapers.sofascore_scraper import SofaScoreScraper

# 国内爬虫
from scrapers.sc500_scraper import SC500Scraper
from scrapers.okooo_scraper import OkoooScraper
from scrapers.dongqiudi_scraper import DongqiudiScraper

class FootballScraper:
    def __init__(self):
        self.mode = os.getenv("SCRAPER_MODE", "overseas").lower()
        
        # 海外爬虫
        self.oddsportal = OddsPortalScraper()
        self.flashscore = FlashScoreScraper()
        self.sofascore = SofaScoreScraper()
        
        # 国内爬虫
        self.sc500 = SC500Scraper()
        self.okooo = OkoooScraper()
        self.dongqiudi = DongqiudiScraper()
        
        self.start_time = os.getenv("START_TIME", "10:00")
        self.end_time = os.getenv("END_TIME", "23:00")
        
        print(f"[启动] 爬虫模式: {self.mode}")
        print(f"[启动] 工作时间: {self.start_time} - {self.end_time}")
        
    def is_within_working_hours(self):
        """检查是否在工作时间范围内"""
        now = datetime.now()
        start_h, start_m = map(int, self.start_time.split(':'))
        end_h, end_m = map(int, self.end_time.split(':'))
        
        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        
        return start_minutes <= current_minutes <= end_minutes
    
    def scrape_overseas(self):
        """爬取海外网站"""
        print(f"[{datetime.now()}] 开始爬取海外网站...")
        total = 0
        
        try:
            # FlashScore（最全的比赛数据源）
            matches = self.flashscore.get_today_matches()
            print(f"  FlashScore: 找到 {len(matches)} 场比赛")
            for m in matches:
                upsert_match(m)
                total += 1
        except Exception as e:
            print(f"  FlashScore 出错: {e}")
        
        try:
            # SofaScore（实时数据+伤停）
            matches = self.sofascore.get_today_matches()
            print(f"  SofaScore: 找到 {len(matches)} 场比赛")
        except Exception as e:
            print(f"  SofaScore 出错: {e}")
        
        try:
            # OddsPortal（赔率数据）
            matches = self.oddsportal.get_today_matches()
            print(f"  OddsPortal: 找到 {len(matches)} 场比赛")
        except Exception as e:
            print(f"  OddsPortal 出错: {e}")
        
        print(f"  海外网站抓取完成，共处理 {total} 场比赛")
        return total
    
    def scrape_domestic(self):
        """爬取国内网站"""
        print(f"[{datetime.now()}] 开始爬取国内网站...")
        total = 0
        
        try:
            # 500网（国内竞彩数据）
            matches = self.sc500.get_today_matches()
            print(f"  500网: 找到 {len(matches)} 场比赛")
            for m in matches:
                upsert_match(m)
                total += 1
        except Exception as e:
            print(f"  500网 出错: {e}")
        
        try:
            # 澳客网
            matches = self.okooo.get_today_matches()
            print(f"  澳客网: 找到 {len(matches)} 场比赛")
        except Exception as e:
            print(f"  澳客网 出错: {e}")
        
        try:
            # 懂球帝
            matches = self.dongqiudi.get_today_matches()
            print(f"  懂球帝: 找到 {len(matches)} 场比赛")
        except Exception as e:
            print(f"  懂球帝 出错: {e}")
        
        print(f"  国内网站抓取完成，共处理 {total} 场比赛")
        return total
    
    def scrape_all(self):
        """执行全量抓取"""
        if not self.is_within_working_hours():
            print(f"[{datetime.now()}] 不在工作时间范围内（{self.start_time}-{self.end_time}），跳过")
            return
        
        print(f"[{datetime.now()}] === 开始全量抓取 ===")
        
        if self.mode in ("overseas", "all"):
            self.scrape_overseas()
        
        if self.mode in ("domestic", "all"):
            self.scrape_domestic()
        
        print(f"[{datetime.now()}] === 抓取完成 ===")
            
    def scrape_high_frequency(self):
        """高频抓取（赛前 1 小时，每 5 分钟一次）"""
        if not self.is_within_working_hours():
            return
        
        print(f"[{datetime.now()}] 执行赛前高频抓取...")
        # 只更新赔率变化，不重复写入比赛信息
        # 详细实现略...
        pass
    
    def run_scheduler(self):
        """运行定时任务调度器"""
        print("初始化数据库...")
        init_db()
        print("数据库初始化完成")
        
        # 每天 10:00 首次抓取
        schedule.every().day.at(self.start_time).do(self.scrape_all)
        
        # 工作时间内每小时抓取
        schedule.every().hour.at(":00").do(self.scrape_all)
        
        # 赛前高频（每10分钟，仅在比赛前2小时内）
        schedule.every(10).minutes.do(self.scrape_high_frequency)
        
        print("=" * 40)
        print("爬虫调度器已启动！")
        print(f"模式: {self.mode}")
        print(f"工作时间: {self.start_time} - {self.end_time}")
        print("=" * 40)
        
        # 立即执行一次（用于验证）
        print("[启动验证] 执行首次抓取...")
        self.scrape_all()
        
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    scraper = FootballScraper()
    scraper.run_scheduler()
