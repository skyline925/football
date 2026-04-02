"""
足球数据爬虫主程序
定时抓取各大网站赔率和球队信息
"""
import os
import sys
import schedule
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入数据库模块
sys.path.append(os.path.dirname(__file__))
from database import init_db, upsert_match, insert_odds, update_team_info, get_today_matches

# 导入爬虫
from scrapers.oddsportal_scraper import OddsPortalScraper

class FootballScraper:
    def __init__(self):
        self.oddsportal = OddsPortalScraper()
        self.start_time = os.getenv("START_TIME", "10:00")
        self.end_time = os.getenv("END_TIME", "23:00")
        
    def is_within_working_hours(self):
        """检查是否在工作时间范围内"""
        now = datetime.now()
        start_h, start_m = map(int, self.start_time.split(':'))
        end_h, end_m = map(int, self.end_time.split(':'))
        
        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        
        return start_minutes <= current_minutes <= end_minutes
    
    def scrape_all(self):
        """执行全量抓取"""
        if not self.is_within_working_hours():
            print(f"[{datetime.now()}] 不在工作时间范围内，跳过抓取")
            return
        
        print(f"[{datetime.now()}] 开始全量抓取...")
        
        try:
            # 1. 从 OddsPortal 获取今日比赛
            matches = self.oddsportal.get_today_matches()
            print(f"找到 {len(matches)} 场比赛")
            
            # 2. 保存比赛信息
            for match in matches:
                upsert_match(match)
                
                # 3. 获取赔率数据
                # match_url = f"{self.oddsportal.base_url}{match['match_id']}/"
                # odds = self.oddsportal.get_match_odds(match_url)
                # if odds:
                #     odds['match_id'] = match['match_id']
                #     insert_odds(odds)
            
            print(f"[{datetime.now()}] 抓取完成")
            
        except Exception as e:
            print(f"抓取过程出错：{str(e)}")
    
    def scrape_high_frequency(self):
        """高频抓取（赛前 1 小时）"""
        if not self.is_within_working_hours():
            return
        
        print(f"[{datetime.now()}] 执行高频抓取...")
        # 实现逻辑：只抓取即将开始的比赛（未来 90 分钟内）
        # 更新赔率数据
        pass
    
    def run_scheduler(self):
        """运行定时任务调度器"""
        # 初始化数据库
        init_db()
        
        # 每天 10:00 首次抓取
        schedule.every().day.at("10:00").do(self.scrape_all)
        
        # 工作时间内每小时抓取
        schedule.every().hour.do(self.scrape_all)
        
        # 每 10 分钟高频抓取（赛前数据）
        schedule.every(10).minutes.do(self.scrape_high_frequency)
        
        print("爬虫调度器已启动...")
        
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    scraper = FootballScraper()
    scraper.run_scheduler()
