"""数据适配器抽象基类"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models import (
    MatchContext, TeamProfile, RecentForm,
    HeadToHead, AvailabilitySnapshot, OddsCard,
)


class FootballDataAdapter(ABC):

    @abstractmethod
    async def get_match_context(self, fixture_id: int) -> MatchContext: ...

    @abstractmethod
    async def get_team_profile(
        self, team_id: int, league_id: int, season: str
    ) -> TeamProfile: ...

    @abstractmethod
    async def get_recent_form(
        self, team_id: int, last_n: int = 10
    ) -> RecentForm: ...

    @abstractmethod
    async def get_head_to_head(
        self, team1_id: int, team2_id: int, last_n: int = 5
    ) -> HeadToHead: ...

    @abstractmethod
    async def get_availability(
        self, team_id: int, fixture_id: Optional[int] = None
    ) -> AvailabilitySnapshot: ...

    @abstractmethod
    async def get_odds(self, fixture_id: int) -> OddsCard: ...
