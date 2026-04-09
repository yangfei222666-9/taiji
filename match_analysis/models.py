"""比赛分析资料卡数据模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── 通用 ─────────────────────────────────────────────────────────

class DataSource(BaseModel):
    source: str = "mock"  # "mock" | "api-football" | "football-data"
    fetched_at: Optional[datetime] = None
    data_missing: bool = False
    missing_reason: Optional[str] = None


# ── 1. MatchContext ──────────────────────────────────────────────

class MatchContext(BaseModel):
    fixture_id: Optional[int] = None
    league_name: str
    league_id: Optional[int] = None
    league_type: str = ""  # "league" | "cup"
    country: str = ""
    season: str = ""
    round: str = ""  # "Regular Season - 30" / "Round of 16"
    stage: str = ""  # "GROUP_STAGE" / "KNOCKOUT"
    home_team: str
    home_team_id: Optional[int] = None
    away_team: str
    away_team_id: Optional[int] = None
    match_date: str  # ISO format
    venue: str = ""
    referee: str = ""
    meta: DataSource = Field(default_factory=DataSource)


# ── 2. TeamProfile ──────────────────────────────────────────────

class TeamStats(BaseModel):
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0


class TeamProfile(BaseModel):
    team_name: str
    team_id: Optional[int] = None
    league_rank: Optional[int] = None
    points: Optional[int] = None
    overall: TeamStats = Field(default_factory=TeamStats)
    home: TeamStats = Field(default_factory=TeamStats)
    away: TeamStats = Field(default_factory=TeamStats)
    goal_diff: int = 0
    clean_sheets: Optional[int] = None
    meta: DataSource = Field(default_factory=DataSource)


# ── 3. RecentForm ───────────────────────────────────────────────

class MatchResult(BaseModel):
    date: str
    opponent: str
    home_away: str  # "H" | "A"
    score: str  # "2-1"
    result: str  # "W" | "D" | "L"
    league: str = ""


class RecentForm(BaseModel):
    team_name: str
    last_n: int = 10
    matches: list[MatchResult] = Field(default_factory=list)
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    form_string: str = ""  # "WWDLW"
    trend: str = ""  # "上升" | "下滑" | "波动" | "稳定"
    meta: DataSource = Field(default_factory=DataSource)


# ── 4. HeadToHead ───────────────────────────────────────────────

class H2HRecord(BaseModel):
    date: str
    home_team: str
    away_team: str
    score: str
    league: str = ""


class HeadToHead(BaseModel):
    team1: str
    team2: str
    total_matches: int = 0
    team1_wins: int = 0
    team2_wins: int = 0
    draws: int = 0
    matches: list[H2HRecord] = Field(default_factory=list)
    meta: DataSource = Field(default_factory=DataSource)


# ── 5. AvailabilitySnapshot ─────────────────────────────────────

class PlayerAbsence(BaseModel):
    player_name: str
    reason: str  # "injury" | "suspension" | "other"
    detail: str = ""  # "Hamstring Injury", "Red Card"
    expected_return: Optional[str] = None


class AvailabilitySnapshot(BaseModel):
    team_name: str
    absences: list[PlayerAbsence] = Field(default_factory=list)
    total_absent: int = 0
    meta: DataSource = Field(default_factory=DataSource)


# ── 6. OddsCard ─────────────────────────────────────────────────

class BookmakerOdds(BaseModel):
    bookmaker: str
    home: Optional[float] = None
    draw: Optional[float] = None
    away: Optional[float] = None


class AsianHandicapLine(BaseModel):
    bookmaker: str
    line: str  # "+0", "+0.5", "-0.5", "-1" etc
    home: float
    away: float


class OverUnderLine(BaseModel):
    bookmaker: str
    line: float  # 2.5, 1.5, 3.5 etc
    over: float
    under: float


class OddsCrossSource(BaseModel):
    """单个博彩公司的交叉源赔率"""
    bookmaker: str
    home: Optional[float] = None
    draw: Optional[float] = None
    away: Optional[float] = None


class OddsCrossValidation(BaseModel):
    """赔率交叉验证结果"""
    cross_source: str = ""
    cross_bookmakers: list[OddsCrossSource] = Field(default_factory=list)
    cross_bookmaker_count: int = 0
    avg_home_diff: Optional[float] = None
    avg_draw_diff: Optional[float] = None
    avg_away_diff: Optional[float] = None
    max_diff: Optional[float] = None
    agreement_level: str = ""  # "一致" | "轻微分歧" | "显著分歧"
    meta: DataSource = Field(default_factory=DataSource)


class OddsCard(BaseModel):
    fixture_id: Optional[int] = None
    match_winner: list[BookmakerOdds] = Field(default_factory=list)
    asian_handicap: list[AsianHandicapLine] = Field(default_factory=list)
    over_under: list[OverUnderLine] = Field(default_factory=list)
    bookmaker_count: int = 0
    cross_validation: Optional[OddsCrossValidation] = None
    meta: DataSource = Field(default_factory=DataSource)


# ── 7. MatchCard（总卡）─────────────────────────────────────────

class MatchCard(BaseModel):
    match_context: MatchContext
    home_profile: TeamProfile
    away_profile: TeamProfile
    home_form: RecentForm
    away_form: RecentForm
    head_to_head: HeadToHead
    home_availability: AvailabilitySnapshot
    away_availability: AvailabilitySnapshot
    odds: OddsCard = Field(default_factory=OddsCard)
    missing_fields: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


# ── 请求模型 ────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    fixture_id: Optional[int] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    league: Optional[str] = None
    date: Optional[str] = None
