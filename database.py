"""
数据库操作模块
负责初始化数据库表和 CRUD 操作
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

def get_db_connection():
    """获取数据库连接"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "❌ DATABASE_URL 环境变量未设置！\n"
            "请在 Railway 项目 Settings → Environment Variables 中添加：\n"
            "  DATABASE_URL = postgresql://neondb_owner:xxx@ep-xxx/neondb?sslmode=require"
        )
    conn = psycopg2.connect(
        db_url,
        cursor_factory=RealDictCursor
    )
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 创建比赛表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            match_id VARCHAR(100) UNIQUE,
            league VARCHAR(200),
            home_team VARCHAR(200),
            away_team VARCHAR(200),
            match_time TIMESTAMP,
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 创建赔率表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id SERIAL PRIMARY KEY,
            match_id VARCHAR(100),
            source VARCHAR(100),
            home_win DECIMAL(10,4),
            draw DECIMAL(10,4),
            away_win DECIMAL(10,4),
            home_handicap DECIMAL(10,4),
            away_handicap DECIMAL(10,4),
            handicap_value VARCHAR(20),
            over_under DECIMAL(10,4),
            over_odds DECIMAL(10,4),
            under_odds DECIMAL(10,4),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE
        )
    """)
    
    # 创建球队信息表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_info (
            id SERIAL PRIMARY KEY,
            team_name VARCHAR(200),
            recent_form VARCHAR(100),
            injuries TEXT,
            suspensions TEXT,
            probable_lineup TEXT,
            league_position INTEGER,
            points INTEGER,
            matches_played INTEGER,
            wins INTEGER,
            draws INTEGER,
            losses INTEGER,
            goals_for INTEGER,
            goals_against INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 创建指数变化历史表（用于时间序列分析）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS odds_history (
            id SERIAL PRIMARY KEY,
            match_id VARCHAR(100),
            source VARCHAR(100),
            home_win DECIMAL(10,4),
            draw DECIMAL(10,4),
            away_win DECIMAL(10,4),
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("数据库表初始化完成")

def upsert_match(match_data):
    """插入或更新比赛信息"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO matches (match_id, league, home_team, away_team, match_time, status, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (match_id) DO UPDATE SET
            status = EXCLUDED.status,
            updated_at = CURRENT_TIMESTAMP
    """, (
        match_data['match_id'],
        match_data['league'],
        match_data['home_team'],
        match_data['away_team'],
        match_data['match_time'],
        match_data.get('status', 'SCHEDULED')
    ))
    
    conn.commit()
    cur.close()
    conn.close()

def insert_odds(odds_data):
    """插入赔率数据"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO odds (match_id, source, home_win, draw, away_win, 
                         home_handicap, away_handicap, handicap_value,
                         over_under, over_odds, under_odds)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        odds_data['match_id'],
        odds_data['source'],
        odds_data.get('home_win'),
        odds_data.get('draw'),
        odds_data.get('away_win'),
        odds_data.get('home_handicap'),
        odds_data.get('away_handicap'),
        odds_data.get('handicap_value'),
        odds_data.get('over_under'),
        odds_data.get('over_odds'),
        odds_data.get('under_odds')
    ))
    
    # 同时记录历史
    cur.execute("""
        INSERT INTO odds_history (match_id, source, home_win, draw, away_win)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        odds_data['match_id'],
        odds_data['source'],
        odds_data.get('home_win'),
        odds_data.get('draw'),
        odds_data.get('away_win')
    ))
    
    conn.commit()
    cur.close()
    conn.close()

def update_team_info(team_data):
    """更新球队信息"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO team_info (team_name, recent_form, injuries, suspensions,
                              probable_lineup, league_position, points,
                              matches_played, wins, draws, losses,
                              goals_for, goals_against, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (team_name) DO UPDATE SET
            recent_form = EXCLUDED.recent_form,
            injuries = EXCLUDED.injuries,
            suspensions = EXCLUDED.suspensions,
            probable_lineup = EXCLUDED.probable_lineup,
            league_position = EXCLUDED.league_position,
            points = EXCLUDED.points,
            updated_at = CURRENT_TIMESTAMP
    """, (
        team_data['team_name'],
        team_data.get('recent_form'),
        team_data.get('injuries'),
        team_data.get('suspensions'),
        team_data.get('probable_lineup'),
        team_data.get('league_position'),
        team_data.get('points'),
        team_data.get('matches_played'),
        team_data.get('wins'),
        team_data.get('draws'),
        team_data.get('losses'),
        team_data.get('goals_for'),
        team_data.get('goals_against')
    ))
    
    conn.commit()
    cur.close()
    conn.close()

def get_today_matches():
    """获取今日比赛列表"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    today = datetime.now().date()
    cur.execute("""
        SELECT * FROM matches 
        WHERE DATE(match_time) = %s 
        ORDER BY match_time
    """, (today,))
    
    matches = cur.fetchall()
    cur.close()
    conn.close()
    return matches

def get_match_full_data(match_id):
    """获取单场比赛的完整数据（含赔率和球队信息）"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 获取比赛基本信息
    cur.execute("SELECT * FROM matches WHERE match_id = %s", (match_id,))
    match = cur.fetchone()
    
    if not match:
        return None
    
    # 获取最新赔率
    cur.execute("""
        SELECT DISTINCT ON (source) *
        FROM odds
        WHERE match_id = %s
        ORDER BY source, timestamp DESC
    """, (match_id,))
    odds = cur.fetchall()
    
    # 获取赔率历史
    cur.execute("""
        SELECT * FROM odds_history
        WHERE match_id = %s
        ORDER BY captured_at DESC
        LIMIT 20
    """, (match_id,))
    odds_history = cur.fetchall()
    
    # 获取球队信息
    cur.execute("""
        SELECT * FROM team_info 
        WHERE team_name IN (%s, %s)
    """, (match['home_team'], match['away_team']))
    team_info = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        'match': dict(match),
        'odds': [dict(o) for o in odds],
        'odds_history': [dict(h) for h in odds_history],
        'team_info': [dict(t) for t in team_info]
    }

if __name__ == "__main__":
    init_db()
