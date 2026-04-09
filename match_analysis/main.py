"""比赛分析 MVP — FastAPI 入口"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import settings
from .models import AnalyzeRequest, MatchCard
from .adapters.mock_adapter import MockAdapter, PartialMockAdapter
from .services.match_analyzer import MatchAnalyzer

app = FastAPI(title="Match Analysis MVP", version="0.1.0")


@app.on_event("startup")
async def startup():
    settings.validate()


def _get_adapter():
    if settings.DATA_SOURCE == "api-football":
        from .adapters.api_football import ApiFootballAdapter
        return ApiFootballAdapter(settings.API_FOOTBALL_KEY)
    return MockAdapter()


@app.get("/health")
async def health():
    has_key = bool(settings.API_FOOTBALL_KEY)
    return {"status": "ok", "source": settings.DATA_SOURCE, "api_key_set": has_key}


@app.get("/analyze/mock", response_model=MatchCard)
async def analyze_mock():
    adapter = MockAdapter()
    analyzer = MatchAnalyzer(adapter)
    card = await analyzer.analyze(fixture_id=1035000)
    return card


@app.get("/analyze/mock-partial", response_model=MatchCard)
async def analyze_mock_partial():
    """缺失门禁验证 — 故意缺 head_to_head + away_availability"""
    adapter = PartialMockAdapter()
    analyzer = MatchAnalyzer(adapter)
    card = await analyzer.analyze(fixture_id=1035000)
    return card


@app.post("/analyze", response_model=MatchCard)
async def analyze(req: AnalyzeRequest):
    adapter = _get_adapter()
    analyzer = MatchAnalyzer(adapter)
    fid = req.fixture_id or 1035000
    card = await analyzer.analyze(fixture_id=fid)
    return card
