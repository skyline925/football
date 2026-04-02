"""
OddsPortal 爬虫
抓取全球赔率数据
"""
from .base_scraper import BaseScraper
import re
from datetime import datetime

class OddsPortalScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.oddsportal.com/matches/football/"
    
    def get_today_matches(self):
        """获取今日比赛列表"""
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"{self.base_url}{today}/"
        
        html = self.fetch_page(url, use_playwright=True)
        if not html:
            return []
        
        soup = self.parse_html(html)
        matches = []
        
        # 解析比赛列表（需要根据实际页面结构调整选择器）
        match_elements = soup.select('div.match-item')
        
        for match_el in match_elements:
            try:
                league = match_el.select_one('.league-name').text.strip()
                home_team = match_el.select_one('.home-team').text.strip()
                away_team = match_el.select_one('.away-team').text.strip()
                match_time_str = match_el.select_one('.match-time').text.strip()
                
                # 解析时间
                match_time = self.parse_match_time(match_time_str)
                
                match_id = f"op_{home_team}_{away_team}_{match_time.strftime('%Y%m%d%H%M')}"
                
                matches.append({
                    'match_id': match_id,
                    'league': league,
                    'home_team': home_team,
                    'away_team': away_team,
                    'match_time': match_time,
                    'status': 'SCHEDULED',
                    'source': 'oddsportal'
                })
                
            except Exception as e:
                print(f"解析比赛失败：{str(e)}")
                continue
        
        return matches
    
    def get_match_odds(self, match_url):
        """获取单场比赛的赔率"""
        html = self.fetch_page(match_url, use_playwright=True)
        if not html:
            return None
        
        soup = self.parse_html(html)
        
        odds_data = {
            'source': 'oddsportal',
            'home_win': None,
            'draw': None,
            'away_win': None,
            'home_handicap': None,
            'away_handicap': None,
            'handicap_value': None,
            'over_under': None,
            'over_odds': None,
            'under_odds': None
        }
        
        # 解析 1X2 赔率
        try:
            odds_1x2 = soup.select('.odds-1x2 .bookmaker-odd')
            if len(odds_1x2) >= 3:
                odds_data['home_win'] = self.safe_float(odds_1x2[0].text)
                odds_data['draw'] = self.safe_float(odds_1x2[1].text)
                odds_data['away_win'] = self.safe_float(odds_1x2[2].text)
        except:
            pass
        
        # 解析亚盘赔率
        try:
            asian_odds = soup.select('.asian-handicap .odd-item')
            if len(asian_odds) >= 2:
                odds_data['home_handicap'] = self.safe_float(asian_odds[0].text)
                odds_data['away_handicap'] = self.safe_float(asian_odds[1].text)
                # 获取盘口值
                handicap_val = soup.select_one('.asian-handicap .handicap-value')
                if handicap_val:
                    odds_data['handicap_value'] = handicap_val.text.strip()
        except:
            pass
        
        # 解析大小球赔率
        try:
            ou_odds = soup.select('.over-under .odd-item')
            if len(ou_odds) >= 2:
                odds_data['over_odds'] = self.safe_float(ou_odds[0].text)
                odds_data['under_odds'] = self.safe_float(ou_odds[1].text)
                # 获取大小球盘口值
                ou_val = soup.select_one('.over-under .total-value')
                if ou_val:
                    odds_data['over_under'] = self.safe_float(ou_val.text)
        except:
            pass
        
        return odds_data
    
    def parse_match_time(self, time_str):
        """解析比赛时间字符串"""
        try:
            # 根据实际格式调整
            if 'Today' in time_str:
                time_only = time_str.replace('Today', '').strip()
                return datetime.now().replace(
                    hour=int(time_only.split(':')[0]),
                    minute=int(time_only.split(':')[1])
                )
            else:
                return datetime.strptime(time_str, "%d.%m.%Y %H:%M")
        except:
            return datetime.now()
