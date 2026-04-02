"""SofaScore 爬虫 - 有公开 API，数据较全"""
import requests
import json

class SofaScoreScraper:
    def __init__(self):
        self.base_url = "https://www.sofascore.com"
        # SofaScore 有公开 API，无需登录即可获取部分数据
        self.api_url = "https://www.sofascore.com/api/v1"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.sofascore.com/"
        }
    
    def get_today_matches(self):
        """获取今日比赛"""
        # 使用 sofascore 公开赛事 API
        import datetime
        today = datetime.date.today().strftime("%Y-%m-%d")
        url = f"{self.api_url}/sport/football/scheduled-events/{today}"
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                events = data.get('events', [])
                matches = []
                for e in events:
                    matches.append({
                        'match_id': f"sofascore_{e.get('id', '')}",
                        'league': e.get('tournament', {}).get('name', ''),
                        'home_team': e.get('homeTeam', {}).get('name', ''),
                        'away_team': e.get('awayTeam', {}).get('name', ''),
                        'match_time': datetime.datetime.fromtimestamp(e.get('startTimestamp', 0)).strftime("%Y-%m-%d %H:%M"),
                        'status': 'SCHEDULED'
                    })
                return matches
        except Exception as e:
            print(f"  [SofaScore] API 请求失败: {e}")
        return []
    
    def get_match_odds(self, match_id):
        """获取比赛赔率"""
        url = f"{self.api_url}/event/{match_id}/odds"
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            return resp.json() if resp.status_code == 200 else {}
        except:
            return {}
