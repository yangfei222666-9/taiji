"""
TaijiOS 实时数据接入层
天气 / 新闻 / 股价汇率 / 体育赛事

所有 API 均为免费或免费额度足够的方案，不引入新依赖（只用 requests）。
bot_core 通过 model_router 的 realtime 意图触发调用。
"""

import os
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger("realtime_data")

# ── 天气（OpenWeatherMap 免费版）──────────────────────────────

OWM_BASE = "https://api.openweathermap.org/data/2.5"


def _key(name: str) -> str:
    """延迟读取环境变量（确保 dotenv 已加载）"""
    return os.getenv(name, "")


def get_weather(city: str = "Kuala Lumpur", lang: str = "zh_cn") -> Optional[str]:
    """获取指定城市天气

    免费 API: https://openweathermap.org/api (60次/分钟)
    需要环境变量 OPENWEATHER_API_KEY
    """
    if not _key("OPENWEATHER_API_KEY"):
        return None
    try:
        r = requests.get(f"{OWM_BASE}/weather", params={
            "q": city, "appid": _key("OPENWEATHER_API_KEY"), "units": "metric", "lang": lang
        }, timeout=10)
        r.raise_for_status()
        d = r.json()
        desc = d["weather"][0]["description"]
        temp = d["main"]["temp"]
        feels = d["main"]["feels_like"]
        humidity = d["main"]["humidity"]
        wind = d["wind"]["speed"]
        return (f"📍 {city} 天气\n"
                f"  {desc}，{temp}°C（体感{feels}°C）\n"
                f"  湿度{humidity}% | 风速{wind}m/s\n"
                f"  更新时间：{datetime.now().strftime('%H:%M')}")
    except Exception as e:
        logger.warning(f"[天气] 获取失败: {e}")
        return None


# ── 新闻热搜（NewsAPI 免费版）────────────────────────────────

NEWS_BASE = "https://newsapi.org/v2"


def get_top_news(country: str = "cn", count: int = 5) -> Optional[str]:
    """获取热门新闻

    免费 API: https://newsapi.org (100次/天)
    需要环境变量 NEWSAPI_KEY
    """
    if not _key("NEWSAPI_KEY"):
        return None
    try:
        r = requests.get(f"{NEWS_BASE}/top-headlines", params={
            "country": country, "pageSize": count, "apiKey": _key("NEWSAPI_KEY")
        }, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        if not articles:
            return "暂无热门新闻"
        lines = [f"📰 {country.upper()} 热门新闻 ({datetime.now().strftime('%H:%M')})"]
        for i, a in enumerate(articles[:count], 1):
            title = a.get("title", "")
            source = a.get("source", {}).get("name", "")
            lines.append(f"  {i}. {title} — {source}")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"[新闻] 获取失败: {e}")
        return None


# ── 股价/汇率（Alpha Vantage 免费版）────────────────────────

AV_BASE = "https://www.alphavantage.co/query"


def get_exchange_rate(from_currency: str = "USD", to_currency: str = "CNY") -> Optional[str]:
    """获取汇率

    免费 API: https://www.alphavantage.co (25次/天)
    需要环境变量 ALPHAVANTAGE_API_KEY
    """
    if not _key("ALPHAVANTAGE_API_KEY"):
        return None
    try:
        r = requests.get(AV_BASE, params={
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "apikey": _key("ALPHAVANTAGE_API_KEY"),
        }, timeout=10)
        r.raise_for_status()
        data = r.json().get("Realtime Currency Exchange Rate", {})
        if not data:
            return None
        rate = data.get("5. Exchange Rate", "?")
        time_str = data.get("6. Last Refreshed", "?")
        return f"💱 {from_currency}/{to_currency}: {float(rate):.4f}\n  更新：{time_str}"
    except Exception as e:
        logger.warning(f"[汇率] 获取失败: {e}")
        return None


def get_stock_quote(symbol: str = "AAPL") -> Optional[str]:
    """获取股票报价

    免费 API: Alpha Vantage (25次/天)
    """
    if not _key("ALPHAVANTAGE_API_KEY"):
        return None
    try:
        r = requests.get(AV_BASE, params={
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": _key("ALPHAVANTAGE_API_KEY"),
        }, timeout=10)
        r.raise_for_status()
        quote = r.json().get("Global Quote", {})
        if not quote:
            return None
        price = quote.get("05. price", "?")
        change = quote.get("09. change", "?")
        pct = quote.get("10. change percent", "?")
        return f"📈 {symbol}: ${float(price):.2f} ({change} / {pct})"
    except Exception as e:
        logger.warning(f"[股票] 获取失败: {e}")
        return None


# ── 体育赛事（API-Football via RapidAPI）──────────────────────

APIFOOTBALL_BASE = "https://v3.football.api-sports.io"

# 联赛ID映射
LEAGUE_IDS = {
    "英超": 39, "PL": 39,
    "欧冠": 2, "CL": 2,
    "西甲": 140, "PD": 140,
    "德甲": 78, "BL1": 78,
    "意甲": 135, "SA": 135,
    "法甲": 61,
    "中超": 169,
    "世界杯": 1,
}


def get_football_matches(competition: str = "CL", status: str = "SCHEDULED",
                         limit: int = 5) -> Optional[str]:
    """获取足球赛事

    API-Football: https://www.api-football.com (100次/天免费)
    需要环境变量 API_FOOTBALL_KEY
    competition: PL=英超, CL=欧冠, PD=西甲, BL1=德甲, SA=意甲
    """
    fk = _key("API_FOOTBALL_KEY") or _key("FOOTBALL_DATA_API_KEY")
    if not fk:
        return None

    league_id = LEAGUE_IDS.get(competition, LEAGUE_IDS.get(competition.upper(), 2))
    # 足球赛季跨年：8月前用当前年份，8月后用当前年份（即赛季开始年）
    now = datetime.now()
    season = now.year if now.month >= 8 else now.year - 1

    # 根据 status 选择不同的查询
    try:
        headers = {"x-apisports-key": fk}

        if status == "LIVE":
            r = requests.get(f"{APIFOOTBALL_BASE}/fixtures",
                             headers=headers,
                             params={"league": league_id, "season": season, "live": "all"},
                             timeout=10)
        elif status == "FINISHED":
            r = requests.get(f"{APIFOOTBALL_BASE}/fixtures",
                             headers=headers,
                             params={"league": league_id, "season": season,
                                     "last": limit},
                             timeout=10)
        else:  # SCHEDULED
            r = requests.get(f"{APIFOOTBALL_BASE}/fixtures",
                             headers=headers,
                             params={"league": league_id, "season": season,
                                     "next": limit},
                             timeout=10)

        r.raise_for_status()
        data = r.json()
        fixtures = data.get("response", [])

        if not fixtures:
            return None

        comp_name = {v: k for k, v in LEAGUE_IDS.items() if isinstance(k, str) and len(k) > 1}
        display_name = comp_name.get(league_id, competition)
        lines = [f"⚽ {display_name} 赛事"]

        for f in fixtures[:limit]:
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            goals_h = f["goals"]["home"]
            goals_a = f["goals"]["away"]
            status_short = f["fixture"]["status"]["short"]
            date_str = f["fixture"]["date"][:16].replace("T", " ")

            if status_short in ("FT", "AET", "PEN"):
                lines.append(f"  ✅ {home} {goals_h}-{goals_a} {away} (完场)")
            elif status_short in ("1H", "2H", "HT", "ET", "LIVE"):
                elapsed = f["fixture"]["status"].get("elapsed", "?")
                lines.append(f"  🔴 {home} {goals_h}-{goals_a} {away} ({elapsed}')")
            else:
                lines.append(f"  📅 {home} vs {away} — {date_str}")

        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"[足球] 获取失败: {e}")
        return None


# ── 统一查询入口 ──────────────────────────────────────────────

# 关键词 → 数据源映射
REALTIME_KEYWORDS = {
    "weather": ["天气", "气温", "下雨", "晴天", "温度", "weather"],
    "news": ["新闻", "热搜", "头条", "时事", "news"],
    "forex": ["汇率", "美元", "人民币", "马币", "日元", "欧元", "exchange", "USD", "CNY", "MYR"],
    "stock": ["股价", "股票", "A股", "美股", "港股", "stock", "AAPL", "TSLA"],
    "football": ["比赛", "比分", "赛事", "英超", "欧冠", "西甲", "德甲", "意甲",
                 "NBA", "联赛", "积分榜", "排名", "football", "match"],
}

# 城市别名
CITY_ALIASES = {
    "吉隆坡": "Kuala Lumpur", "KL": "Kuala Lumpur",
    "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou",
    "深圳": "Shenzhen", "成都": "Chengdu", "杭州": "Hangzhou",
    "东京": "Tokyo", "新加坡": "Singapore",
}

# 赛事别名
COMPETITION_ALIASES = {
    "英超": "英超", "欧冠": "欧冠", "西甲": "西甲",
    "德甲": "德甲", "意甲": "意甲", "法甲": "法甲",
    "中超": "中超", "世界杯": "世界杯",
    "PL": "英超", "CL": "欧冠",
}

# 货币别名
CURRENCY_ALIASES = {
    "美元": "USD", "人民币": "CNY", "马币": "MYR", "日元": "JPY",
    "欧元": "EUR", "英镑": "GBP", "港币": "HKD",
}


def _detect_city(text: str) -> str:
    """从文本中提取城市名"""
    for alias, city in CITY_ALIASES.items():
        if alias in text:
            return city
    return "Kuala Lumpur"  # 默认吉隆坡


def _detect_competition(text: str) -> str:
    """从文本中提取赛事"""
    for alias, code in COMPETITION_ALIASES.items():
        if alias in text:
            return code
    return "CL"  # 默认欧冠


def _detect_currencies(text: str) -> tuple[str, str]:
    """从文本中提取货币对"""
    found = []
    for alias, code in CURRENCY_ALIASES.items():
        if alias in text or code in text.upper():
            if code not in found:
                found.append(code)
    if len(found) >= 2:
        return found[0], found[1]
    elif len(found) == 1:
        return "USD", found[0]
    return "USD", "CNY"


def _detect_stock(text: str) -> str:
    """从文本中提取股票代码"""
    import re
    # 匹配大写字母股票代码
    match = re.search(r'\b([A-Z]{1,5})\b', text)
    if match and match.group(1) not in ("USD", "CNY", "MYR", "API", "NBA", "CL", "PL"):
        return match.group(1)
    return ""


def query_realtime(user_input: str) -> Optional[str]:
    """根据用户输入自动判断需要什么实时数据，返回结果文本。

    返回 None 表示不需要实时数据或全部 API 不可用。
    """
    text = user_input.lower() if user_input else ""
    results = []

    # 检测需要哪些数据源
    need_weather = any(kw in user_input for kw in REALTIME_KEYWORDS["weather"])
    need_news = any(kw in user_input for kw in REALTIME_KEYWORDS["news"])
    need_forex = any(kw in user_input for kw in REALTIME_KEYWORDS["forex"])
    need_stock = any(kw in user_input for kw in REALTIME_KEYWORDS["stock"])
    need_football = any(kw in user_input for kw in REALTIME_KEYWORDS["football"])

    if need_weather:
        city = _detect_city(user_input)
        r = get_weather(city)
        if r:
            results.append(r)

    if need_news:
        r = get_top_news()
        if r:
            results.append(r)

    if need_forex:
        from_c, to_c = _detect_currencies(user_input)
        r = get_exchange_rate(from_c, to_c)
        if r:
            results.append(r)

    if need_stock:
        symbol = _detect_stock(user_input)
        if symbol:
            r = get_stock_quote(symbol)
            if r:
                results.append(r)

    if need_football:
        comp = _detect_competition(user_input)
        # 先查进行中，再查已结束，再查未开始
        for status in ["LIVE", "FINISHED", "SCHEDULED"]:
            r = get_football_matches(comp, status, limit=5)
            if r and "暂无" not in r:
                results.append(r)
                break
        else:
            # 全部状态都没有，返回赛程
            r = get_football_matches(comp, "SCHEDULED", limit=5)
            if r:
                results.append(r)

    if not results:
        return None

    return "\n\n".join(results)


def get_available_sources() -> list[str]:
    """返回当前可用的数据源列表"""
    sources = []
    if _key("OPENWEATHER_API_KEY"):
        sources.append("天气(OpenWeather)")
    if _key("NEWSAPI_KEY"):
        sources.append("新闻(NewsAPI)")
    if _key("ALPHAVANTAGE_API_KEY"):
        sources.append("股价汇率(AlphaVantage)")
    if _key("API_FOOTBALL_KEY") or _key("FOOTBALL_DATA_API_KEY"):
        sources.append("足球(API-Football)")
    return sources
