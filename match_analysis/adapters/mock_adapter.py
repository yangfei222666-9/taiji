"""Mock 数据适配器 — 从本地 JSON 读取"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import FootballDataAdapter
from ..models import (
    MatchContext, TeamProfile, RecentForm,
    HeadToHead, AvailabilitySnapshot, DataSource,
    TeamStats, MatchResult, H2HRecord, PlayerAbsence,
    OddsCard, BookmakerOdds, AsianHandicapLine, OverUnderLine,
)

MOCK_DIR = Path(__file__).resolve().parent.parent / "mock_data"


def _src() -> DataSource:
    return DataSource(source="mock", fetched_at=datetime.now())


class MockAdapter(FootballDataAdapter):

    def __init__(self):
        with open(MOCK_DIR / "sample_match.json", encoding="utf-8") as f:
            self._data = json.load(f)

    async def get_match_context(self, fixture_id: int) -> MatchContext:
        d = self._data["fixture"]
        return MatchContext(**d, meta=_src())

    async def get_team_profile(
        self, team_id: int, league_id: int, season: str
    ) -> TeamProfile:
        key = "home_profile" if team_id == self._data["fixture"]["home_team_id"] else "away_profile"
        d = self._data[key]
        return TeamProfile(
            team_name=d["team_name"],
            team_id=d["team_id"],
            league_rank=d.get("league_rank"),
            points=d.get("points"),
            overall=TeamStats(**d["overall"]),
            home=TeamStats(**d["home"]),
            away=TeamStats(**d["away"]),
            goal_diff=d.get("goal_diff", 0),
            clean_sheets=d.get("clean_sheets"),
            meta=_src(),
        )

    async def get_recent_form(
        self, team_id: int, last_n: int = 10
    ) -> RecentForm:
        key = "home_form" if team_id == self._data["fixture"]["home_team_id"] else "away_form"
        d = self._data[key]
        return RecentForm(
            team_name=d["team_name"],
            last_n=d["last_n"],
            matches=[MatchResult(**m) for m in d["matches"]],
            wins=d["wins"],
            draws=d["draws"],
            losses=d["losses"],
            goals_for=d["goals_for"],
            goals_against=d["goals_against"],
            form_string=d["form_string"],
            trend=d["trend"],
            meta=_src(),
        )

    async def get_head_to_head(
        self, team1_id: int, team2_id: int, last_n: int = 5
    ) -> HeadToHead:
        d = self._data["head_to_head"]
        return HeadToHead(
            team1=d["team1"],
            team2=d["team2"],
            total_matches=d["total_matches"],
            team1_wins=d["team1_wins"],
            team2_wins=d["team2_wins"],
            draws=d["draws"],
            matches=[H2HRecord(**m) for m in d["matches"]],
            meta=_src(),
        )

    async def get_availability(
        self, team_id: int, fixture_id: Optional[int] = None
    ) -> AvailabilitySnapshot:
        key = "home_availability" if team_id == self._data["fixture"]["home_team_id"] else "away_availability"
        d = self._data[key]
        return AvailabilitySnapshot(
            team_name=d["team_name"],
            absences=[PlayerAbsence(**a) for a in d["absences"]],
            total_absent=d["total_absent"],
            meta=_src(),
        )

    async def get_odds(self, fixture_id: int) -> OddsCard:
        return OddsCard(
            fixture_id=fixture_id,
            match_winner=[
                BookmakerOdds(bookmaker="MockBet", home=2.50, draw=3.20, away=2.80),
            ],
            asian_handicap=[
                AsianHandicapLine(bookmaker="MockBet", line="-0.5", home=1.85, away=2.00),
            ],
            over_under=[
                OverUnderLine(bookmaker="MockBet", line=2.5, over=1.90, under=1.90),
            ],
            bookmaker_count=1,
            meta=_src(),
        )
    """故意缺失部分数据，用于验证缺失门禁机制"""


class PartialMockAdapter(MockAdapter):

    def _missing(self, reason: str) -> DataSource:
        return DataSource(
            source="mock", fetched_at=datetime.now(),
            data_missing=True, missing_reason=reason,
        )

    async def get_head_to_head(
        self, team1_id: int, team2_id: int, last_n: int = 5
    ) -> HeadToHead:
        return HeadToHead(
            team1="Arsenal", team2="Chelsea",
            meta=self._missing("API 未返回历史交锋数据"),
        )

    async def get_availability(
        self, team_id: int, fixture_id: Optional[int] = None
    ) -> AvailabilitySnapshot:
        if team_id != self._data["fixture"]["home_team_id"]:
            return AvailabilitySnapshot(
                team_name="Chelsea",
                meta=self._missing("客队伤停数据暂不可用"),
            )
        return await super().get_availability(team_id, fixture_id)
