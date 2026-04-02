#!/usr/bin/env python3
"""
本地足球竞彩爬虫脚本
支持从澳客网、500网抓取数据，写入 Neon PostgreSQL 数据库
用法: python3 local_scraper.py
"""
import os
import sys
import requests
from bs4 import BeautifulSoup
import re
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ 请设置 DATABASE_URL 环境变量")
    print("   或者创建 .env 文件，内容：DATABASE_URL=postgresql://...")
    sys.exit(1)

# ============ 数据库写入 ============
def init_db():
    """初始化数据库表"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    # matches 表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id VARCHAR(255) PRIMARY KEY,
            league VARCHAR(100),
            home_team VARCHAR(100),
            away_team VARCHAR(100),
            match_time TIMESTAMP,
            status VARCHAR(20) DEFAULT 'SCHEDULED',
            source VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # odds 表（最新赔率）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id SERIAL PRIMARY KEY,
            match_id VARCHAR(255),
            source VARCHAR(50),
            home_win DECIMAL(5,2),
            draw DECIMAL(5,2),
            away_win DECIMAL(5,2),
            handicap_value VARCHAR(50),
            over_under DECIMAL(5,2),
            home_win_odds DECIMAL(5,2),
            draw_odds DECIMAL(5,2),
            away_win_odds DECIMAL(5,2),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(match_id, source)
        )
    """)
    
    # odds_history 表（赔率历史）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds_history (
            id SERIAL PRIMARY KEY,
            match_id VARCHAR(255),
            source VARCHAR(50),
            home_win DECIMAL(5,2),
            draw DECIMAL(5,2),
            away_win DECIMAL(5,2),
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # team_info 表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_info (
            team_name VARCHAR(100) PRIMARY KEY,
            league_position INTEGER,
            points INTEGER,
            wins INTEGER,
            draws INTEGER,
            losses INTEGER,
            goals_for INTEGER,
            goals_against INTEGER,
            recent_form VARCHAR(50),
            injuries TEXT,
            suspensions TEXT,
            probable_lineup TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ 数据库表初始化完成")

def upsert_match(match_data: dict):
    """插入或更新比赛"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO matches (match_id, league, home_team, away_team, match_time, status, source)
        VALUES (%(match_id)s, %(league)s, %(home_team)s, %(away_team)s, %(match_time)s, %(status)s, %(source)s)
        ON CONFLICT (match_id) DO UPDATE SET
            league = EXCLUDED.league,
            home_team = EXCLUDED.home_team,
            away_team = EXCLUDED.away_team,
            match_time = EXCLUDED.match_time
    """, match_data)
    
    conn.commit()
    cur.close()
    conn.close()

def insert_odds(odds_data: dict):
    """插入赔率"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO odds (match_id, source, home_win, draw, away_win, handicap_value, over_under)
        VALUES (%(match_id)s, %(source)s, %(home_win)s, %(draw)s, %(away_win)s, %(handicap_value)s, %(over_under)s)
        ON CONFLICT (match_id, source) DO UPDATE SET
            home_win = EXCLUDED.home_win,
            draw = EXCLUDED.draw,
            away_win = EXCLUDED.away_win,
            handicap_value = EXCLUDED.handicap_value,
            over_under = EXCLUDED.over_under,
            timestamp = CURRENT_TIMESTAMP
    """, odds_data)
    
    # 同时记录历史
    cur.execute("""
        INSERT INTO odds_history (match_id, source, home_win, draw, away_win)
        VALUES (%(match_id)s, %(source)s, %(home_win)s, %(draw)s, %(away_win)s)
    """, odds_data)
    
    conn.commit()
    cur.close()
    conn.close()

# ============ 爬虫 ============

class OkoooScraper:
    """澳客网爬虫"""
    
    def __init__(self):
        self.base_url = "https://www.okooo.com"
        self.jingcai_url = "https://www.okooo.com/jingcai/"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.okooo.com/"
        })
    
    def scrape(self):
        """执行抓取"""
        print("[澳客网] 正在抓取...")
        
        try:
            resp = self.session.get(self.jingcai_url, timeout=20)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            
            matches = self._parse_matches(resp.text)
            print(f"[澳客网] 找到 {len(matches)} 场比赛")
            
            for m in matches:
                upsert_match(m)
                if m.get('home_win'):
                    insert_odds({
                        'match_id': m['match_id'],
                        'source': 'okooo',
                        'home_win': m.get('home_win'),
                        'draw': m.get('draw'),
                        'away_win': m.get('away_win'),
                        'handicap_value': m.get('handicap'),
                        'over_under': None
                    })
            
            return len(matches)
            
        except Exception as e:
            print(f"[澳客网] 抓取失败: {e}")
            return 0
    
    def _parse_matches(self, html: str) -> list:
        """解析比赛数据"""
        soup = BeautifulSoup(html, 'html.parser')
        matches = []
        
        # 找所有包含赔率的行
        text = soup.get_text()
        
        # 用正则匹配澳客网的比赛格式
        # 格式: 日期时间 联赛 时间 主队 赔率 客队
        # 例如: 2026-04-02 星期四 003 英甲 22:00 维冈竞技 2.15 3.07 2.95 莱顿东方
        
        # 找所有赔率组合 (三个数字，通常是主胜 平 客胜)
        odds_pattern = r'([\u4e00-\u9fa5a-zA-Z·\(\)s]+?)\s+(\d[\d.]+)\s+(\d[\d.]+)\s+(\d[\d.]+)'
        
        # 先找日期
        date_matches = re.findall(
            r'(\d{4}-\d{2}-\d{2})\s*星期[一二三四五六日]\s*(\d+)',
            text
        )
        
        # 按行处理
        lines = text.split('\n')
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # 匹配赔率三联
            odds_match = re.findall(odds_pattern, line)
            if len(odds_match) >= 1:
                for om in odds_match:
                    team_name, o1, o2, o3 = om
                    o1f, o2f, o3f = float(o1), float(o2), float(o3)
                    
                    # 过滤无效赔率（太小或太大）
                    if not (1.1 < o1f < 20 and 1.5 < o2f < 10 and 1.1 < o3f < 20):
                        continue
                    
                    # 这行可能包含主队
                    # 继续搜索客队信息
                    context = '\n'.join(lines[max(0,i-3):min(len(lines),i+3)])
                    
                    # 简化处理：提取队名
                    # 格式通常是: 主队名 数字 数字 数字 客队名
                    parts = re.split(r'\s{2,}|\s+(?=\d)', context)
                    
        # 更精确的解析：用 bs4 找特定结构
        matches = self._parse_bs4(soup, current_date)
        return matches
    
    def _parse_bs4(self, soup: BeautifulSoup, current_date: str) -> list:
        """用 BeautifulSoup 解析"""
        matches = []
        
        # 找所有包含数字赔率的行
        # 澳客网页面结构：<tr><td>时间</td><td>联赛</td><td>主队</td><td>赔率</td><td>客队</td></tr>
        
        for tr in soup.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) < 5:
                continue
            
            # 提取文本
            texts = [td.get_text(strip=True) for td in tds]
            
            # 查找包含赔率格式的行
            # 格式: 时间 主队 [赔率x3] 客队
            odds_values = []
            team_names = []
            
            for j, td in enumerate(tds):
                # 找数字（赔率）
                nums = re.findall(r'\b(\d+\.\d+)\b', td.get_text())
                if 3 <= len(nums) <= 4:
                    odds_values = [(float(n) for n in nums[:3])]
                    # 前后应该是队名
                    prev_text = tds[j-1].get_text(strip=True) if j > 0 else ''
                    next_text = tds[j+1].get_text(strip=True) if j < len(tds)-1 else ''
                    if prev_text and next_text and not re.match(r'^[\d.]+$', prev_text):
                        team_names = [prev_text, next_text]
                        break
            
            if odds_values and len(team_names) == 2:
                home, away = team_names
                o1, o2, o3 = list(odds_values)[:3]
                
                # 找时间
                time_str = ''
                for td in tds[:2]:
                    t = re.search(r'(\d{2}:\d{2})', td.get_text())
                    if t:
                        time_str = t.group(1)
                        break
                
                # 找联赛
                league = ''
                for td in tds:
                    text = td.get_text(strip=True)
                    if re.match(r'^[\u4e00-\u9fa5]+$', text) and len(text) < 10 and text != home and text != away:
                        league = text
                        break
                
                if home and away and o1 > 1.1:
                    match_id = f"okooo_{home}_{away}_{time_str}".replace(' ', '_')
                    match_time = f"{current_date} {time_str}:00"
                    
                    matches.append({
                        'match_id': match_id,
                        'league': league,
                        'home_team': home,
                        'away_team': away,
                        'match_time': match_time,
                        'status': 'SCHEDULED',
                        'source': 'okooo',
                        'home_win': o1,
                        'draw': o2,
                        'away_win': o3
                    })
        
        return matches


class SC500Scraper:
    """500网爬虫"""
    
    def __init__(self):
        self.base_url = "https://www.500.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.500.com/"
        })
    
    def scrape(self):
        """执行抓取"""
        print("[500网] 正在抓取...")
        
        try:
            resp = self.session.get(f"{self.base_url}/jczq/", timeout=20)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            
            matches = self._parse_matches(resp.text)
            print(f"[500网] 找到 {len(matches)} 场比赛")
            
            for m in matches:
                upsert_match(m)
                if m.get('home_win'):
                    insert_odds({
                        'match_id': m['match_id'],
                        'source': '500.com',
                        'home_win': m.get('home_win'),
                        'draw': m.get('draw'),
                        'away_win': m.get('away_win'),
                        'handicap_value': m.get('handicap'),
                        'over_under': None
                    })
            
            return len(matches)
            
        except Exception as e:
            print(f"[500网] 抓取失败: {e}")
            return 0
    
    def _parse_matches(self, html: str) -> list:
        """解析比赛数据"""
        soup = BeautifulSoup(html, 'html.parser')
        matches = []
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for tr in soup.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) < 6:
                continue
            
            texts = [td.get_text(strip=True) for td in tds]
            
            # 500网格式：联赛 时间 主队 赔率 客队
            # 找包含数字赔率的行
            all_text = ' '.join(texts)
            odds_match = re.findall(r'(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)', all_text)
            
            if odds_match:
                for om in odds_match:
                    o1, o2, o3 = float(om[0]), float(om[1]), float(om[2])
                    if 1.1 < o1 < 20 and 1.5 < o2 < 10 and 1.1 < o3 < 20:
                        # 提取队名
                        team_pattern = r'([\u4e00-\u9fa5a-zA-Z·\(\)·]+?)\s+\d+\.\d+\s+\d+\.\d+\s+\d+\.\d+'
                        teams = re.findall(team_pattern, all_text)
                        if len(teams) >= 2:
                            home, away = teams[0], teams[1]
                            time_match = re.search(r'(\d{2}:\d{2})', all_text)
                            time_str = time_match.group(1) if time_match else '00:00'
                            
                            league = ''
                            for text in texts:
                                if re.match(r'^[\u4e00-\u9fa5]+$', text) and len(text) < 10 and text not in [home, away]:
                                    league = text
                                    break
                            
                            match_id = f"500_{home}_{away}_{time_str}".replace(' ', '_')
                            matches.append({
                                'match_id': match_id,
                                'league': league,
                                'home_team': home,
                                'away_team': away,
                                'match_time': f"{current_date} {time_str}:00",
                                'status': 'SCHEDULED',
                                'source': '500.com',
                                'home_win': o1,
                                'draw': o2,
                                'away_win': o3
                            })
        
        return matches


# ============ 主程序 ============

def main():
    print("=" * 50)
    print(f"🏆 本地足球竞彩爬虫 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    
    # 初始化数据库
    init_db()
    
    total = 0
    
    # 抓取澳客网
    scraper1 = OkoooScraper()
    total += scraper1.scrape()
    time.sleep(2)
    
    # 抓取500网
    scraper2 = SC500Scraper()
    total += scraper2.scrape()
    
    print()
    print("=" * 50)
    print(f"✅ 抓取完成！共处理 {total} 场比赛")
    print("=" * 50)

if __name__ == "__main__":
    main()
