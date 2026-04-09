"""核心分析服务：调 adapter → 组装 MatchCard"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..adapters.base import FootballDataAdapter
from ..adapters.the_odds_api import TheOddsApiClient
from ..config import settings
from ..models import MatchCard, MatchContext, OddsCard, OddsCrossValidation


class MatchAnalyzer:

    def __init__(self, adapter: FootballDataAdapter):
        self._adapter = adapter

    async def analyze(self, fixture_id: int) -> MatchCard:
        ctx = await self._adapter.get_match_context(fixture_id)

        home_id = ctx.home_team_id or 0
        away_id = ctx.away_team_id or 0
        league_id = ctx.league_id or 0
        season = ctx.season

        home_profile, away_profile, home_form, away_form, h2h, home_avail, away_avail = (
            await self._adapter.get_team_profile(home_id, league_id, season),
            await self._adapter.get_team_profile(away_id, league_id, season),
            await self._adapter.get_recent_form(home_id),
            await self._adapter.get_recent_form(away_id),
            await self._adapter.get_head_to_head(home_id, away_id),
            await self._adapter.get_availability(home_id, fixture_id),
            await self._adapter.get_availability(away_id, fixture_id),
        )

        odds = await self._adapter.get_odds(fixture_id)

        # 赔率交叉验证（可选增强层）
        cross = await self._try_cross_validation(ctx, odds)
        if cross:
            odds.cross_validation = cross

        missing = _collect_missing([
            ("match_context", ctx.meta),
            ("home_profile", home_profile.meta),
            ("away_profile", away_profile.meta),
            ("home_form", home_form.meta),
            ("away_form", away_form.meta),
            ("head_to_head", h2h.meta),
            ("home_availability", home_avail.meta),
            ("away_availability", away_avail.meta),
            ("odds", odds.meta),
        ])

        return MatchCard(
            match_context=ctx,
            home_profile=home_profile,
            away_profile=away_profile,
            home_form=home_form,
            away_form=away_form,
            head_to_head=h2h,
            home_availability=home_avail,
            away_availability=away_avail,
            odds=odds,
            missing_fields=missing,
            generated_at=datetime.now(),
        )

    async def _try_cross_validation(
        self, ctx: MatchContext, odds: OddsCard
    ) -> Optional[OddsCrossValidation]:
        if not settings.THE_ODDS_API_KEY:
            return None
        try:
            client = TheOddsApiClient()
            cross = await client.get_cross_odds(
                ctx.home_team, ctx.away_team, ctx.match_date, ctx.league_id,
            )
            if not cross.meta.data_missing and cross.cross_bookmakers:
                cross = _compute_agreement(odds, cross)
            return cross
        except Exception:
            return None


def _compute_agreement(
    primary: OddsCard, cross: OddsCrossValidation
) -> OddsCrossValidation:
    p_home, p_draw, p_away, p_n = 0.0, 0.0, 0.0, 0
    for bk in primary.match_winner:
        if bk.home and bk.draw and bk.away:
            p_home += bk.home; p_draw += bk.draw; p_away += bk.away
            p_n += 1

    c_home, c_draw, c_away, c_n = 0.0, 0.0, 0.0, 0
    for bk in cross.cross_bookmakers:
        if bk.home and bk.draw and bk.away:
            c_home += bk.home; c_draw += bk.draw; c_away += bk.away
            c_n += 1

    if p_n == 0 or c_n == 0:
        return cross

    dh = abs(p_home / p_n - c_home / c_n)
    dd = abs(p_draw / p_n - c_draw / c_n)
    da = abs(p_away / p_n - c_away / c_n)
    mx = max(dh, dd, da)

    cross.avg_home_diff = round(dh, 3)
    cross.avg_draw_diff = round(dd, 3)
    cross.avg_away_diff = round(da, 3)
    cross.max_diff = round(mx, 3)

    if mx < 0.15:
        cross.agreement_level = "一致"
    elif mx < 0.40:
        cross.agreement_level = "轻微分歧"
    else:
        cross.agreement_level = "显著分歧"

    return cross


def _collect_missing(sections: list[tuple[str, object]]) -> list[str]:
    out = []
    for name, meta in sections:
        if getattr(meta, "data_missing", False):
            reason = getattr(meta, "missing_reason", "unknown")
            out.append(f"{name}: {reason}")
    return out
