"""
澳客网(okooo.com) 足球竞彩爬虫 - Playwright版本
使用浏览器自动化获取动态加载的竞彩数据
"""
import asyncio
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Playwright
from playwright.async_api import async_playwright, Page

class OkoooScraperPlaywright:
    """使用 Playwright 的澳客网爬虫"""
    
    def __init__(self):
        self.base_url = "https://www.okooo.com"
        self.jingcai_url = "https://www.okooo.com/jingcai/"
    
    async def get_today_matches(self) -> List[Dict]:
        """获取今日所有竞彩比赛"""
        matches = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            try:
                await page.goto(self.jingcai_url, timeout=30000, wait_until="networkidle")
                
                # 等待比赛数据加载（等待表格出现）
                await page.wait_for_selector('table', timeout=15000)
                
                # 滚动页面让所有动态内容加载
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)
                
                # 获取页面文本内容
                content = await page.content()
                matches = self._parse_content(content)
                
                print(f"[澳客网 Playwright] 找到 {len(matches)} 场比赛")
                
            except Exception as e:
                print(f"[澳客网 Playwright] 错误: {e}")
            finally:
                await browser.close()
        
        return matches
    
    def _parse_content(self, html: str) -> List[Dict]:
        """从页面 HTML 中解析比赛数据"""
        import re
        
        matches = []
        
        # 比赛数据格式：
        # 日期时间 + 联赛 + 主队 + 客队 + 赔率
        # 示例: 2026-04-02 星期四 003 | 英甲 | 22:00 | 维冈竞技 2.15 3.07 2.95 | 莱顿东方
        
        # 1. 先找到所有日期分隔行（包含"星期"）
        date_pattern = r'(\d{4}-\d{2}-\d{2})\s*星期[一二三四五六日](?:上午|下午)?\s*(\d+)'
        dates = re.findall(date_pattern, html)
        
        # 2. 找所有比赛行（包含赔率数字）
        # 赔率格式: 主队名 数字 数字 数字 客队名
        # 例如: 维冈竞技 2.15 3.07 2.95 莱顿东方
        match_pattern = r'<td[^>]*>\s*(\d{2}:\d{2})\s*</td>.*?<a[^>]*title="([^"]+)"[^>]*>\s*([\u4e00-\u9fa5a-zA-Z\s\(\)·]+?)\s*</a>.*?<span[^>]*>\s*([\d.]+)\s*</span>.*?<span[^>]*>\s*([\d.]+)\s*</span>.*?<span[^>]*>\s*([\d.]+)\s*</span>.*?<a[^>]*title="([^"]+)"[^>]*>\s*([\u4e00-\u9fa5a-zA-Z\s\(\)·]+?)\s*</a>'
        
        raw_matches = re.findall(match_pattern, html, re.DOTALL)
        
        for rm in raw_matches:
            time_str, league1, home_team, odds1, odds2, odds3, league2, away_team = rm
            
            try:
                home_win = float(odds1) if odds1 else None
                draw = float(odds2) if odds2 else None
                away_win = float(odds3) if odds3 else None
                
                match = {
                    'match_id': f"okooo_{home_team.strip()}_{away_team.strip()}_{time_str}".replace(' ', '_'),
                    'league': league1.strip() if league1 else '',
                    'home_team': home_team.strip(),
                    'away_team': away_team.strip(),
                    'match_time': f"2026-04-02 {time_str}:00",
                    'home_win': home_win,
                    'draw': draw,
                    'away_win': away_win,
                    'source': 'okooo'
                }
                matches.append(match)
            except:
                continue
        
        # 备选：直接从文本提取
        if not matches:
            matches = self._parse_text_mode(html)
        
        return matches
    
    def _parse_text_mode(self, html: str) -> List[Dict]:
        """文本模式解析 - 直接搜索赔率数字"""
        import re
        matches = []
        
        # 找到所有 "联赛名 + 时间 + 赔率" 的组合
        # 例如: 英甲 22:00 维冈竞技 2.15 3.07 2.95 莱顿东方
        lines = re.findall(
            r'([\u4e00-\u9fa5]{2,8})\s*(\d{2}:\d{2})\s*([\u4e00-\u9fa5·\(\)a-zA-Z]+?)\s{1,3}([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\u4e00-\u9fa5·\(\)a-zA-Z]+?)(?=\s*<|$)',
            html
        )
        
        for line in lines:
            try:
                league, time_str, home, o1, o2, o3, away = line
                if float(o1) > 0.5 and float(o1) < 20:
                    match = {
                        'match_id': f"okooo_{home.strip()}_{away.strip()}_{time_str}".replace(' ', '_'),
                        'league': league.strip(),
                        'home_team': home.strip(),
                        'away_team': away.strip(),
                        'match_time': f"2026-04-02 {time_str}:00",
                        'home_win': float(o1),
                        'draw': float(o2),
                        'away_win': float(o3),
                        'source': 'okooo'
                    }
                    matches.append(match)
            except:
                continue
        
        return matches
    
    async def get_match_odds(self, match_id: str) -> Optional[Dict]:
        """获取单场比赛详细赔率"""
        # 从 match_id 解析出实际的 okooo match ID
        # match_id 格式: okooo_{home}_{away}_{time}
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # 搜索 match ID
                url = f"{self.base_url}/soccer/match/{match_id}/history/"
                await page.goto(url, timeout=20000)
                await page.wait_for_load_state('networkidle')
                
                content = await page.content()
                return self._parse_odds_detail(content)
                
            except Exception as e:
                print(f"[澳客网] 获取赔率详情失败: {e}")
                return None
            finally:
                await browser.close()


def run_async():
    """异步运行测试"""
    scraper = OkoooScraperPlaywright()
    matches = asyncio.run(scraper.get_today_matches())
    
    print(f"\n{'='*60}")
    print(f"澳客网今日竞彩比赛: {len(matches)} 场")
    print(f"{'='*60}")
    
    for i, m in enumerate(matches):
        print(f"\n[{i+1}] {m.get('league', '?')} | {m.get('match_time', '?')}")
        print(f"    {m.get('home_team', '?')} vs {m.get('away_team', '?')}")
        if m.get('home_win'):
            print(f"    赔率: {m['home_win']} | {m.get('draw','-')} | {m['away_win']}")
    
    return matches


if __name__ == "__main__":
    matches = run_async()
