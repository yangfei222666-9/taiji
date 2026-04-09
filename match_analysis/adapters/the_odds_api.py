"""The Odds API 赔率交叉验证客户端"""
from __future__ import annotations

import time
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

import httpx

from ..config import settings
from ..models import (
    DataSource, OddsCrossSource, OddsCrossValidation,
)

ODDS_CACHE_TTL = 1800  # 30 分钟
_odds_cache: dict[str, tuple[float, list]] = {}  # sport_key -> (timestamp, events)

# API-Football league_id → The Odds API sport_key
SPORT_KEY_MAP: dict[int, str] = {
    39: "soccer_epl",
    140: "soccer_spain_la_liga",
    135: "soccer_italy_serie_a",
    78: "soccer_germany_bundesliga",
    61: "soccer_france_ligue_one",
    2: "soccer_uefa_champs_league",
    3: "soccer_uefa_europa_league",
    848: "soccer_uefa_europa_conference_league",
}


def _src() -> DataSource:
    return DataSource(source="the-odds-api", fetched_at=datetime.now())


def _missing(reason: str) -> DataSource:
    return DataSource(
        source="the-odds-api", fetched_at=datetime.now(),
        data_missing=True, missing_reason=reason,
    )


class TheOddsApiClient:

    def __init__(self, api_key: str = ""):
        self._key = api_key or settings.THE_ODDS_API_KEY
        self._base = settings.THE_ODDS_API_BASE

    async def _get(self, endpoint: str, params: dict) -> dict | list:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base}/{endpoint}",
                    params={**params, "apiKey": self._key},
                    timeout=15,
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
            return {"_error": str(e)}

    async def get_cross_odds(
        self,
        home_team: str,
        away_team: str,
        match_date: str,
        league_id: Optional[int] = None,
    ) -> OddsCrossValidation:
        if not self._key:
            return OddsCrossValidation(meta=_missing("THE_ODDS_API_KEY not set"))

        sport_key = SPORT_KEY_MAP.get(league_id) if league_id else None
        if not sport_key:
            return OddsCrossValidation(
                meta=_missing(f"league {league_id} not supported by The Odds API"),
            )

        events = await self._get_events(sport_key)
        if isinstance(events, dict) and events.get("_error"):
            return OddsCrossValidation(
                meta=_missing(f"request failed: {events['_error']}"),
            )

        matched = self._match_fixture(events, home_team, away_team, match_date)
        if not matched:
            return OddsCrossValidation(
                meta=_missing(
                    f"no matching fixture for {home_team} vs {away_team} "
                    f"in {sport_key}"
                ),
            )

        bookmakers = []
        for bk in matched.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                home_odd = outcomes.get(matched["home_team"])
                away_odd = outcomes.get(matched["away_team"])
                draw_odd = outcomes.get("Draw")
                bookmakers.append(OddsCrossSource(
                    bookmaker=bk.get("title", bk.get("key", "?")),
                    home=home_odd,
                    draw=draw_odd,
                    away=away_odd,
                ))

        if not bookmakers:
            return OddsCrossValidation(
                meta=_missing("no h2h market data in matched fixture"),
            )

        return OddsCrossValidation(
            cross_source="the-odds-api",
            cross_bookmakers=bookmakers,
            cross_bookmaker_count=len(bookmakers),
            meta=_src(),
        )

    async def _get_events(self, sport_key: str) -> list | dict:
        now = time.time()
        if sport_key in _odds_cache:
            ts, data = _odds_cache[sport_key]
            if now - ts < ODDS_CACHE_TTL:
                return data

        data = await self._get(
            f"sports/{sport_key}/odds",
            {"regions": "eu,uk", "markets": "h2h"},
        )
        if isinstance(data, list):
            _odds_cache[sport_key] = (now, data)
        return data

    @staticmethod
    def _match_fixture(
        events: list, home_team: str, away_team: str, match_date: str
    ) -> Optional[dict]:
        target_date = match_date[:10]
        best_match = None
        best_score = 0.0

        for ev in events:
            ev_date = ev.get("commence_time", "")[:10]
            if abs(_date_diff(target_date, ev_date)) > 1:
                continue

            h_score = _name_similarity(home_team, ev.get("home_team", ""))
            a_score = _name_similarity(away_team, ev.get("away_team", ""))
            avg = (h_score + a_score) / 2

            if avg > best_score and h_score >= 0.5 and a_score >= 0.5:
                best_score = avg
                best_match = ev

        return best_match


def _name_similarity(name1: str, name2: str) -> float:
    """队名相似度：别名归一化 + SequenceMatcher + 子串"""
    a = _normalize(name1)
    b = _normalize(name2)
    if a == b:
        return 1.0
    ratio = SequenceMatcher(None, a, b).ratio()
    if a in b or b in a:
        ratio = max(ratio, 0.75)
    a0 = a.split()[0] if a else ""
    b0 = b.split()[0] if b else ""
    if a0 and b0 and a0 == b0 and len(a0) >= 4:
        ratio = max(ratio, 0.6)
    return ratio


# 所有变体 → 统一标准名（小写）
# 标准名取 The Odds API 使用的全称
_ALIASES: dict[str, str] = {
    # ── 英超 ──
    "wolves": "wolverhampton wanderers",
    "wolverhampton": "wolverhampton wanderers",
    "west ham": "west ham united",
    "spurs": "tottenham hotspur",
    "tottenham": "tottenham hotspur",
    "man utd": "manchester united",
    "man united": "manchester united",
    "man city": "manchester city",
    "newcastle": "newcastle united",
    "leicester": "leicester city",
    "brighton": "brighton and hove albion",
    "nott'm forest": "nottingham forest",
    "nottm forest": "nottingham forest",
    "sheffield utd": "sheffield united",
    "ipswich": "ipswich town",
    "luton": "luton town",
    "palace": "crystal palace",
    "villa": "aston villa",
    "leeds": "leeds united",
    "sunderland afc": "sunderland",
    "burnley fc": "burnley",
    # ── 西甲 ──
    "athletic club": "athletic bilbao",
    "ath bilbao": "athletic bilbao",
    "atletico": "atletico madrid",
    "atletico de madrid": "atletico madrid",
    "atlético madrid": "atletico madrid",
    "atlético de madrid": "atletico madrid",
    "betis": "real betis",
    "real sociedad de futbol": "real sociedad",
    "celta": "celta vigo",
    "rc celta": "celta vigo",
    "osasuna": "ca osasuna",
    "alaves": "alavés",
    "rcd espanyol": "espanyol",
    "rcd mallorca": "mallorca",
    "real valladolid": "valladolid",
    "cadiz": "cadiz cf",
    "almeria": "ud almeria",
    "las palmas": "ud las palmas",
    "leganes": "cd leganes",
    "real oviedo": "oviedo",
    # ── 意甲 ──
    "inter": "inter milan",
    "internazionale": "inter milan",
    "fc internazionale": "inter milan",
    "milan": "ac milan",
    "napoli": "napoli",
    "ssc napoli": "napoli",
    "roma": "as roma",
    "atalanta": "atalanta bc",
    "verona": "hellas verona",
    "hellas": "hellas verona",
    "sampdoria": "sampdoria",
    "venezia fc": "venezia",
    "empoli fc": "empoli",
    "monza": "ac monza",
    "us cremonese": "cremonese",
    # ── 德甲 ──
    "gladbach": "borussia monchengladbach",
    "m'gladbach": "borussia monchengladbach",
    "monchengladbach": "borussia monchengladbach",
    "mönchengladbach": "borussia monchengladbach",
    "borussia mönchengladbach": "borussia monchengladbach",
    "dortmund": "borussia dortmund",
    "bvb": "borussia dortmund",
    "bayern": "bayern munich",
    "bayern munchen": "bayern munich",
    "bayern münchen": "bayern munich",
    "fc bayern münchen": "bayern munich",
    "leverkusen": "bayer leverkusen",
    "bayer 04 leverkusen": "bayer leverkusen",
    "leipzig": "rb leipzig",
    "rasenballsport leipzig": "rb leipzig",
    "wolfsburg": "vfl wolfsburg",
    "stuttgart": "vfb stuttgart",
    "hoffenheim": "tsg hoffenheim",
    "tsg 1899 hoffenheim": "tsg hoffenheim",
    "freiburg": "sc freiburg",
    "mainz": "fsv mainz 05",
    "mainz 05": "fsv mainz 05",
    "1. fsv mainz 05": "fsv mainz 05",
    "frankfurt": "eintracht frankfurt",
    "eintracht": "eintracht frankfurt",
    "bremen": "werder bremen",
    "sv werder bremen": "werder bremen",
    "augsburg": "augsburg",
    "fc augsburg": "augsburg",
    "union": "union berlin",
    "1. fc union berlin": "union berlin",
    "heidenheim": "1. fc heidenheim",
    "fc heidenheim": "1. fc heidenheim",
    "1.fc heidenheim 1846": "1. fc heidenheim",
    "st. pauli": "fc st. pauli",
    "fc st pauli": "fc st. pauli",
    "st pauli": "fc st. pauli",
    "koln": "1. fc köln",
    "köln": "1. fc köln",
    "fc koln": "1. fc köln",
    "1. fc koln": "1. fc köln",
    "hsv": "hamburger sv",
    "hamburg": "hamburger sv",
    # ── 法甲 ──
    "psg": "paris saint germain",
    "paris saint-germain": "paris saint germain",
    "paris sg": "paris saint germain",
    "marseille": "marseille",
    "olympique marseille": "marseille",
    "olympique de marseille": "marseille",
    "om": "marseille",
    "lyon": "lyon",
    "olympique lyonnais": "lyon",
    "ol": "lyon",
    "monaco": "as monaco",
    "fc monaco": "as monaco",
    "lille": "lille",
    "losc": "lille",
    "losc lille": "lille",
    "lens": "rc lens",
    "racing lens": "rc lens",
    "rennes": "rennes",
    "stade rennais": "rennes",
    "stade rennais fc": "rennes",
    "nice": "nice",
    "ogc nice": "nice",
    "nantes": "nantes",
    "fc nantes": "nantes",
    "strasbourg": "strasbourg",
    "rc strasbourg": "strasbourg",
    "rc strasbourg alsace": "strasbourg",
    "toulouse": "toulouse",
    "toulouse fc": "toulouse",
    "brest": "brest",
    "stade brestois": "brest",
    "stade brestois 29": "brest",
    "reims": "stade de reims",
    "stade reims": "stade de reims",
    "montpellier": "montpellier",
    "montpellier hsc": "montpellier",
    "le havre": "le havre",
    "le havre ac": "le havre",
    "angers": "angers",
    "angers sco": "angers",
    "auxerre": "auxerre",
    "aj auxerre": "auxerre",
    "metz": "metz",
    "fc metz": "metz",
    "lorient": "lorient",
    "fc lorient": "lorient",
    "paris fc": "paris fc",
    "st etienne": "saint etienne",
    "as saint-etienne": "saint etienne",
    "as saint-étienne": "saint etienne",
    # ── 欧战常客 ──
    "sporting": "sporting lisbon",
    "sporting cp": "sporting lisbon",
    "sporting clube de portugal": "sporting lisbon",
    "porto": "porto",
    "fc porto": "porto",
    "benfica": "benfica",
    "sl benfica": "benfica",
    "braga": "sc braga",
    "sporting braga": "sc braga",
    "ajax": "ajax",
    "afc ajax": "ajax",
    "ajax amsterdam": "ajax",
    "psv": "psv eindhoven",
    "psv": "psv eindhoven",
    "feyenoord": "feyenoord",
    "feyenoord rotterdam": "feyenoord",
    "galatasaray": "galatasaray",
    "galatasaray sk": "galatasaray",
    "fenerbahce": "fenerbahce",
    "fenerbahçe": "fenerbahce",
    "besiktas": "besiktas",
    "beşiktaş": "besiktas",
    "celtic": "celtic",
    "celtic fc": "celtic",
    "rangers": "rangers",
    "rangers fc": "rangers",
    "red bull salzburg": "rb salzburg",
    "fc salzburg": "rb salzburg",
    "salzburg": "rb salzburg",
    "shakhtar": "shakhtar donetsk",
    "fc shakhtar donetsk": "shakhtar donetsk",
    "dynamo kyiv": "dynamo kiev",
    "dynamo": "dynamo kiev",
    "club brugge": "club brugge kv",
    "bruges": "club brugge kv",
}


def _normalize(name: str) -> str:
    low = name.lower().strip()
    return _ALIASES.get(low, low)


def _date_diff(d1: str, d2: str) -> int:
    try:
        dt1 = datetime.strptime(d1, "%Y-%m-%d")
        dt2 = datetime.strptime(d2, "%Y-%m-%d")
        return abs((dt1 - dt2).days)
    except (ValueError, TypeError):
        return 999
