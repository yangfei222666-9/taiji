"""API-Football 真实数据适配器"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import httpx

from .base import FootballDataAdapter
from ..config import settings
from ..models import (
    MatchContext, TeamProfile, RecentForm, HeadToHead,
    AvailabilitySnapshot, DataSource, TeamStats,
    MatchResult, H2HRecord, PlayerAbsence,
    OddsCard, BookmakerOdds, AsianHandicapLine, OverUnderLine,
)

STANDINGS_TTL = 3600  # 1 小时缓存
_standings_cache: dict[str, tuple[float, dict]] = {}  # key -> (timestamp, data)


def _src() -> DataSource:
    return DataSource(source="api-football", fetched_at=datetime.now())


def _missing(reason: str) -> DataSource:
    return DataSource(
        source="api-football", fetched_at=datetime.now(),
        data_missing=True, missing_reason=reason,
    )


class ApiFootballAdapter(FootballDataAdapter):

    def __init__(self, api_key: str = ""):
        self._key = api_key or settings.API_FOOTBALL_KEY
        self._base = settings.API_FOOTBALL_BASE
        self._headers = {"x-apisports-key": self._key}
        self._fixture_cache: dict = {}

    async def _get(self, endpoint: str, params: dict) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base}/{endpoint}",
                    headers=self._headers,
                    params=params,
                    timeout=15,
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
            return {"response": [], "_error": str(e)}

    # ── 1. MatchContext ──────────────────────────────────────────

    async def get_match_context(self, fixture_id: int) -> MatchContext:
        data = await self._get("fixtures", {"id": fixture_id})
        err = data.get("_error")
        items = data.get("response", [])
        if err or not items:
            reason = f"request failed: {err}" if err else f"fixture {fixture_id} not found"
            return MatchContext(
                league_name="", home_team="", away_team="",
                match_date="", meta=_missing(reason),
            )
        fix = items[0]
        self._fixture_cache = fix
        f = fix["fixture"]
        lg = fix["league"]
        tm = fix["teams"]
        venue = f.get("venue") or {}
        return MatchContext(
            fixture_id=f["id"],
            league_name=lg["name"],
            league_id=lg["id"],
            league_type="cup" if lg.get("round") and "finals" in lg.get("round", "").lower() else "league",
            country=lg.get("country", ""),
            season=str(lg.get("season", "")),
            round=lg.get("round", ""),
            stage=lg.get("round", ""),
            home_team=tm["home"]["name"],
            home_team_id=tm["home"]["id"],
            away_team=tm["away"]["name"],
            away_team_id=tm["away"]["id"],
            match_date=f["date"],
            venue=venue.get("name") or venue.get("city") or "",
            referee=f.get("referee") or "",
            meta=_src(),
        )

    async def _get_standings(self, league_id: int, season: str) -> dict:
        """standings 带缓存，同联赛同赛季 1 小时内复用"""
        cache_key = f"{league_id}:{season}"
        now = time.time()
        if cache_key in _standings_cache:
            ts, data = _standings_cache[cache_key]
            if now - ts < STANDINGS_TTL:
                return data
        data = await self._get("standings", {"league": league_id, "season": season})
        if not data.get("_error"):
            _standings_cache[cache_key] = (now, data)
        return data

    async def get_team_profile(
        self, team_id: int, league_id: int, season: str
    ) -> TeamProfile:
        st_data = await self._get_standings(league_id, season)
        err = st_data.get("_error")
        if err:
            return TeamProfile(
                team_name=str(team_id), team_id=team_id,
                meta=_missing(f"request failed: {err}"),
            )
        rank, points = None, None
        team_name = ""
        for lg in st_data.get("response", []):
            for group in lg.get("league", {}).get("standings", []):
                for row in group:
                    if row["team"]["id"] == team_id:
                        rank = row["rank"]
                        points = row["points"]
                        team_name = row["team"]["name"]
                        overall = TeamStats(
                            played=row["all"]["played"],
                            wins=row["all"]["win"],
                            draws=row["all"]["draw"],
                            losses=row["all"]["lose"],
                            goals_for=row["all"]["goals"]["for"],
                            goals_against=row["all"]["goals"]["against"],
                        )
                        home = TeamStats(
                            played=row["home"]["played"],
                            wins=row["home"]["win"],
                            draws=row["home"]["draw"],
                            losses=row["home"]["lose"],
                            goals_for=row["home"]["goals"]["for"],
                            goals_against=row["home"]["goals"]["against"],
                        )
                        away = TeamStats(
                            played=row["away"]["played"],
                            wins=row["away"]["win"],
                            draws=row["away"]["draw"],
                            losses=row["away"]["lose"],
                            goals_for=row["away"]["goals"]["for"],
                            goals_against=row["away"]["goals"]["against"],
                        )
                        return TeamProfile(
                            team_name=team_name, team_id=team_id,
                            league_rank=rank, points=points,
                            overall=overall, home=home, away=away,
                            goal_diff=row.get("goalsDiff", 0),
                            meta=_src(),
                        )
        return TeamProfile(
            team_name=str(team_id), team_id=team_id,
            meta=_missing(f"standings not found for team {team_id} in league {league_id}"),
        )

    # ── 3. RecentForm ───────────────────────────────────────────

    async def get_recent_form(
        self, team_id: int, last_n: int = 10
    ) -> RecentForm:
        data = await self._get("fixtures", {"team": team_id, "last": last_n, "status": "FT"})
        err = data.get("_error")
        items = data.get("response", [])
        if err:
            return RecentForm(
                team_name=str(team_id),
                meta=_missing(f"request failed: {err}"),
            )
        if not items:
            # API 成功但无已完赛比赛 — 有效的空，不是缺失
            return RecentForm(team_name=str(team_id), meta=_src())
        matches = []
        wins = draws = losses = gf = ga = 0
        team_name = ""
        for fix in items:
            tm = fix["teams"]
            goals = fix["goals"]
            is_home = tm["home"]["id"] == team_id
            team_name = tm["home"]["name"] if is_home else tm["away"]["name"]
            opponent = tm["away"]["name"] if is_home else tm["home"]["name"]
            h_goals = goals["home"] if goals["home"] is not None else 0
            a_goals = goals["away"] if goals["away"] is not None else 0
            my_goals = h_goals if is_home else a_goals
            opp_goals = a_goals if is_home else h_goals
            if my_goals > opp_goals:
                result = "W"; wins += 1
            elif my_goals == opp_goals:
                result = "D"; draws += 1
            else:
                result = "L"; losses += 1
            gf += my_goals; ga += opp_goals
            matches.append(MatchResult(
                date=fix["fixture"]["date"][:10],
                opponent=opponent,
                home_away="H" if is_home else "A",
                score=f"{goals['home']}-{goals['away']}",
                result=result,
                league=fix["league"]["name"],
            ))
        form_str = "".join(m.result for m in matches)
        if wins >= last_n * 0.6:
            trend = "上升"
        elif losses >= last_n * 0.4:
            trend = "下滑"
        else:
            trend = "波动"
        return RecentForm(
            team_name=team_name, last_n=len(matches), matches=matches,
            wins=wins, draws=draws, losses=losses,
            goals_for=gf, goals_against=ga,
            form_string=form_str, trend=trend, meta=_src(),
        )

    async def get_head_to_head(
        self, team1_id: int, team2_id: int, last_n: int = 5
    ) -> HeadToHead:
        data = await self._get("fixtures/headtohead", {
            "h2h": f"{team1_id}-{team2_id}", "last": last_n,
        })
        err = data.get("_error")
        items = data.get("response", [])
        if err:
            return HeadToHead(
                team1=str(team1_id), team2=str(team2_id),
                meta=_missing(f"request failed: {err}"),
            )
        if not items:
            # API 成功但无历史交锋 — 这是有效的"没有"，不是缺失
            return HeadToHead(
                team1=str(team1_id), team2=str(team2_id),
                meta=_src(),
            )
        t1_wins = t2_wins = draws = 0
        matches = []
        t1_name = t2_name = ""
        for fix in items:
            tm = fix["teams"]
            goals = fix["goals"]
            home_id = tm["home"]["id"]
            h_goals = goals["home"] if goals["home"] is not None else 0
            a_goals = goals["away"] if goals["away"] is not None else 0
            if not t1_name:
                t1_name = tm["home"]["name"] if home_id == team1_id else tm["away"]["name"]
                t2_name = tm["away"]["name"] if home_id == team1_id else tm["home"]["name"]
            if home_id == team1_id:
                if h_goals > a_goals: t1_wins += 1
                elif h_goals < a_goals: t2_wins += 1
                else: draws += 1
            else:
                if a_goals > h_goals: t1_wins += 1
                elif a_goals < h_goals: t2_wins += 1
                else: draws += 1
            matches.append(H2HRecord(
                date=fix["fixture"]["date"][:10],
                home_team=tm["home"]["name"],
                away_team=tm["away"]["name"],
                score=f"{goals['home']}-{goals['away']}",
                league=fix["league"]["name"],
            ))
        return HeadToHead(
            team1=t1_name, team2=t2_name,
            total_matches=len(matches),
            team1_wins=t1_wins, team2_wins=t2_wins, draws=draws,
            matches=matches, meta=_src(),
        )

    # ── 5. Availability ─────────────────────────────────────────

    async def get_availability(
        self, team_id: int, fixture_id: Optional[int] = None
    ) -> AvailabilitySnapshot:
        params: dict = {"team": team_id}
        if fixture_id:
            params["fixture"] = fixture_id
        data = await self._get("injuries", params)
        err = data.get("_error")
        items = data.get("response", [])
        if err:
            return AvailabilitySnapshot(
                team_name=str(team_id),
                meta=_missing(f"request failed: {err}"),
            )
        if not items:
            # API 成功但无伤停 — 全员健康，不是缺失
            return AvailabilitySnapshot(
                team_name=str(team_id),
                meta=_src(),
            )
        team_name = ""
        absences = []
        for item in items:
            player = item.get("player", {})
            team_name = team_name or item.get("team", {}).get("name", str(team_id))
            absences.append(PlayerAbsence(
                player_name=player.get("name", "Unknown"),
                reason=player.get("type", "injury").lower(),
                detail=player.get("reason") or "",
            ))
        return AvailabilitySnapshot(
            team_name=team_name,
            absences=absences,
            total_absent=len(absences),
            meta=_src(),
        )

    # ── 6. Odds ─────────────────────────────────────────────────

    async def get_odds(self, fixture_id: int) -> OddsCard:
        data = await self._get("odds", {"fixture": fixture_id})
        err = data.get("_error")
        items = data.get("response", [])
        if err:
            return OddsCard(
                fixture_id=fixture_id,
                meta=_missing(f"request failed: {err}"),
            )
        if not items:
            return OddsCard(fixture_id=fixture_id, meta=_src())

        bookmakers = items[0].get("bookmakers", [])
        match_winner = []
        asian_handicap = []
        over_under = []

        for bk in bookmakers:
            bk_name = bk["name"]
            for bet in bk.get("bets", []):
                bid = bet["id"]
                vals = {v["value"]: v["odd"] for v in bet.get("values", [])}

                if bid == 1:  # Match Winner (1X2)
                    match_winner.append(BookmakerOdds(
                        bookmaker=bk_name,
                        home=_to_float(vals.get("Home")),
                        draw=_to_float(vals.get("Draw")),
                        away=_to_float(vals.get("Away")),
                    ))
                elif bid == 4:  # Asian Handicap
                    pairs = bet.get("values", [])
                    seen: set[str] = set()
                    for i in range(0, len(pairs) - 1, 2):
                        h_val = pairs[i]
                        a_val = pairs[i + 1]
                        line = h_val["value"].replace("Home ", "").replace("Away ", "")
                        if line in seen:
                            continue
                        seen.add(line)
                        asian_handicap.append(AsianHandicapLine(
                            bookmaker=bk_name, line=line,
                            home=_to_float(h_val["odd"]) or 0,
                            away=_to_float(a_val["odd"]) or 0,
                        ))
                        if len(seen) >= 3:
                            break
                elif bid == 5:  # Goals Over/Under
                    seen_ou: set[float] = set()
                    for v in bet.get("values", []):
                        parts = v["value"].split(" ")
                        if len(parts) != 2:
                            continue
                        direction, line_str = parts
                        line_f = _to_float(line_str)
                        if line_f is None or line_f in seen_ou or direction != "Over":
                            continue
                        under_odd = vals.get(f"Under {line_str}")
                        over_under.append(OverUnderLine(
                            bookmaker=bk_name, line=line_f,
                            over=_to_float(v["odd"]) or 0,
                            under=_to_float(under_odd) or 0,
                        ))
                        seen_ou.add(line_f)
                    break  # 大小球只取第一家，避免数据爆炸

        return OddsCard(
            fixture_id=fixture_id,
            match_winner=match_winner,
            asian_handicap=asian_handicap,
            over_under=over_under,
            bookmaker_count=len(bookmakers),
            meta=_src(),
        )


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None
