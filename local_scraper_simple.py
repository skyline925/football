#!/usr/bin/env python3
"""
本地足球竞彩爬虫（简化版，支持VPN模式）
用法: python local_scraper_simple.py
需要: requests beautifulsoup4 psycopg2-binary python-dotenv
"""
import os, sys, requests, re, time, socket
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("请先创建 .env 文件，内容：DATABASE_URL=postgresql://...")
    sys.exit(1)

# ============ SSL修复 ============
# 有些网站SSL有问题，用这个修复
import urllib3
urllib3.disable_warnings()

# ============ 数据库 ============
def init_db():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    for sql in [
        """CREATE TABLE IF NOT EXISTS matches (
            match_id VARCHAR(255) PRIMARY KEY, league VARCHAR(100),
            home_team VARCHAR(100), away_team VARCHAR(100),
            match_time TIMESTAMP, status VARCHAR(20) DEFAULT 'SCHEDULED',
            source VARCHAR(50), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS odds (
            id SERIAL PRIMARY KEY, match_id VARCHAR(255), source VARCHAR(50),
            home_win DECIMAL(5,2), draw DECIMAL(5,2), away_win DECIMAL(5,2),
            handicap_value VARCHAR(50), over_under DECIMAL(5,2),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(match_id, source))""",
        """CREATE TABLE IF NOT EXISTS odds_history (
            id SERIAL PRIMARY KEY, match_id VARCHAR(255), source VARCHAR(50),
            home_win DECIMAL(5,2), draw DECIMAL(5,2), away_win DECIMAL(5,2),
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS team_info (
            team_name VARCHAR(100) PRIMARY KEY, league_position INTEGER, points INTEGER,
            wins INTEGER, draws INTEGER, losses INTEGER,
            goals_for INTEGER, goals_against INTEGER,
            recent_form VARCHAR(50), injuries TEXT,
            suspensions TEXT, probable_lineup TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
    ]:
        cur.execute(sql)
    conn.commit()
    cur.close(); conn.close()
    print("数据库就绪")

def upsert(m):
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("""INSERT INTO matches (match_id,league,home_team,away_team,match_time,status,source)
        VALUES (%(match_id)s,%(league)s,%(home_team)s,%(away_team)s,%(match_time)s,%(status)s,%(source)s)
        ON CONFLICT (match_id) DO UPDATE SET league=EXCLUDED.league""", m)
    conn.commit(); cur.close(); conn.close()

def save_odds(o):
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("""INSERT INTO odds (match_id,source,home_win,draw,away_win,handicap_value)
        VALUES (%(match_id)s,%(source)s,%(home_win)s,%(draw)s,%(away_win)s,%(handicap_value)s)
        ON CONFLICT (match_id,source) DO UPDATE SET home_win=EXCLUDED.home_win""", o)
    cur.execute("""INSERT INTO odds_history (match_id,source,home_win,draw,away_win)
        VALUES (%(match_id)s,%(source)s,%(home_win)s,%(draw)s,%(away_win)s)""", o)
    conn.commit(); cur.close(); conn.close()

def test_db():
    """测试数据库连接"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close(); conn.close()
        print("数据库连接: OK")
        return True
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return False

# ============ 爬虫 ============

def scrape_okooo():
    """澳客网"""
    urls = [
        "https://www.okooo.com/jingcai/",
        "https://m.okooo.com/jczq/",
    ]
    for url in urls:
        try:
            print(f"[澳客网] 尝试: {url}")
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.okooo.com/"
            })
            r = s.get(url, timeout=15, verify=False)
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')
            matches = _parse_bs4(soup, "okooo")
            if matches:
                print(f"[澳客网] 成功抓取 {len(matches)} 场")
                return matches
        except Exception as e:
            print(f"[澳客网] 失败: {e}")
    return []

def scrape_500():
    """500网"""
    urls = [
        "https://www.500.com/jczq/",
        "https://m.500.com/jczq/",
    ]
    for url in urls:
        try:
            print(f"[500网] 尝试: {url}")
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) Mobile",
                "Accept-Language": "zh-CN",
                "Referer": "https://www.500.com/"
            })
            r = s.get(url, timeout=15, verify=False)
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')
            matches = _parse_bs4(soup, "500.com")
            if matches:
                print(f"[500网] 成功抓取 {len(matches)} 场")
                return matches
        except Exception as e:
            print(f"[500网] 失败: {e}")
    return []

def _parse_bs4(soup, source):
    """通用解析"""
    matches = []
    today = datetime.now().strftime('%Y-%m-%d')
    seen = set()
    
    for tr in soup.find_all('tr'):
        try:
            tds = [td.get_text(strip=True) for td in tr.find_all('td')]
            if len(tds) < 4: continue
            
            all_text = ' '.join(tds)
            nums = re.findall(r'\b(\d+\.\d+)\b', all_text)
            
            # 过滤：3个赔率数字，且合理范围
            valid_odds = [float(n) for n in nums if 1.1 < float(n) < 20]
            if len(valid_odds) < 3: continue
            
            o1, o2, o3 = valid_odds[0], valid_odds[1], valid_odds[2]
            if not (1.5 < o2 < 10): continue  # 平局必须在合理范围
            
            # 提取队名（在赔率前后的中文字符串）
            # 找时间
            tm = re.search(r'(\d{2}:\d{2})', all_text)
            time_str = tm.group(1) if tm else "00:00"
            dt = f"{today} {time_str}:00"
            
            # 提取队名 - 找赔率前后的非数字文本
            parts = re.split(r'\s*\d+\.\d+\s*', all_text)
            teams = [p.strip() for p in parts if len(p.strip()) > 1 and len(p.strip()) < 20]
            # 去重，保持顺序
            unique_teams = []
            for t in teams:
                if t not in unique_teams and re.match(r'^[\u4e00-\u9fa5a-zA-Z·\(\)·]+$', t):
                    unique_teams.append(t)
            
            if len(unique_teams) >= 2:
                home = unique_teams[0]
                away = unique_teams[-1]
                if home == away or len(home) < 2 or len(away) < 2: continue
                
                key = f"{home}_{away}_{time_str}"
                if key in seen: continue
                seen.add(key)
                
                mid = f"{source}_{home}_{away}_{time_str}".replace(' ', '_')
                m = {'match_id':mid,'league':'','home_team':home,'away_team':away,
                     'match_time':dt,'status':'SCHEDULED','source':source}
                o = {'match_id':mid,'source':source,'home_win':o1,'draw':o2,'away_win':o3,'handicap_value':''}
                upsert(m); save_odds(o)
                matches.append(m)
        except: continue
    
    return matches

# ============ 主程序 ============

if __name__ == "__main__":
    print("="*50)
    print(f"🏆 本地足球竞彩爬虫")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*50)
    
    # 1. 测试数据库
    if not test_db():
        print("请检查 .env 中的 DATABASE_URL 是否正确")
        sys.exit(1)
    
    init_db()
    
    total = 0
    
    # 2. 抓取澳客网
    try:
        n = len(scrape_okooo())
        total += n
    except Exception as e:
        print(f"澳客网异常: {e}")
    
    time.sleep(3)
    
    # 3. 抓取500网
    try:
        n = len(scrape_500())
        total += n
    except Exception as e:
        print(f"500网异常: {e}")
    
    print()
    print("="*50)
    print(f"✅ 完成！共处理 {total} 场比赛")
    print("="*50)
