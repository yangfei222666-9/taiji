"""
周末压力验证脚本

用法：
  export API_FOOTBALL_KEY="your_key"
  cd g:\taijios_full_workspace
  python -m match_analysis.stress_test

验收口径：
  PASS: 全部场次无500，standings缓存命中，429/timeout降级可归因
  WARN: 个别场次有缺失但可归因，响应偏慢
  FAIL: 出现未捕获异常/500，或缺失无法归因
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# ── 配置 ─────────────────────────────────────────────────────────

KEY = os.environ.get("API_FOOTBALL_KEY", "")
BASE = "https://v3.football.api-sports.io"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
TARGET_MATCHES = 12  # 目标分析场次


# ── 采集当天比赛 ─────────────────────────────────────────────────

async def fetch_fixtures(date: str) -> list[dict]:
    """拉指定日期的比赛，优先五大联赛+欧战"""
    headers = {"x-apisports-key": KEY}
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE}/fixtures", headers=headers,
            params={"date": date}, timeout=15,
        )
        data = r.json()

    priority_leagues = {
        39, 140, 135, 78, 61,  # 英超、西甲、意甲、德甲、法甲
        2, 3, 848,  # 欧冠、欧联、欧会杯
    }
    fixtures = data.get("response", [])

    # 分优先级
    tier1 = [f for f in fixtures if f["league"]["id"] in priority_leagues]
    tier2 = [f for f in fixtures if f["league"]["id"] not in priority_leagues]

    selected = tier1[:TARGET_MATCHES]
    if len(selected) < TARGET_MATCHES:
        selected += tier2[:TARGET_MATCHES - len(selected)]

    return selected[:TARGET_MATCHES]


# ── 核心测试 ─────────────────────────────────────────────────────

async def run_analysis(fixture_id: int, label: str) -> dict:
    """分析一场比赛，返回指标"""
    from match_analysis.adapters.api_football import ApiFootballAdapter, _standings_cache
    from match_analysis.services.match_analyzer import MatchAnalyzer

    cache_before = len(_standings_cache)
    adapter = ApiFootballAdapter()

    # 计数 API 调用
    call_log = []
    original_get = ApiFootballAdapter._get.__wrapped__ if hasattr(ApiFootballAdapter._get, '__wrapped__') else None

    async def counting_get(self, endpoint, params):
        call_log.append({"endpoint": endpoint, "params": str(params)})
        return await ApiFootballAdapter._get_original(self, endpoint, params)

    # monkey-patch
    if not hasattr(ApiFootballAdapter, '_get_original'):
        ApiFootballAdapter._get_original = ApiFootballAdapter._get
    ApiFootballAdapter._get = counting_get

    result = {
        "fixture_id": fixture_id,
        "label": label,
        "status": "PASS",
        "api_calls": 0,
        "standings_cache_hit": False,
        "response_time_ms": 0,
        "sections": {},
        "missing_fields": [],
        "cross_validation": None,
        "error": None,
    }

    t0 = time.time()
    try:
        analyzer = MatchAnalyzer(adapter)
        card = await analyzer.analyze(fixture_id=fixture_id)
        d = card.model_dump(mode="json")

        result["response_time_ms"] = round((time.time() - t0) * 1000)
        result["api_calls"] = len(call_log)
        result["standings_cache_hit"] = len(_standings_cache) == cache_before
        result["missing_fields"] = d.get("missing_fields", [])

        for key in ["match_context", "home_profile", "away_profile",
                     "home_form", "away_form", "head_to_head",
                     "home_availability", "away_availability", "odds"]:
            sec = d[key]
            meta = sec.get("meta", {})
            result["sections"][key] = {
                "source": meta.get("source", "?"),
                "data_missing": meta.get("data_missing", False),
                "missing_reason": meta.get("missing_reason"),
            }

        if result["missing_fields"]:
            result["status"] = "WARN"

        # 交叉验证指标
        odds_sec = d.get("odds", {})
        cv = odds_sec.get("cross_validation")
        if cv:
            cv_meta = cv.get("meta", {})
            result["cross_validation"] = {
                "source": cv.get("cross_source", ""),
                "bookmaker_count": cv.get("cross_bookmaker_count", 0),
                "agreement_level": cv.get("agreement_level", ""),
                "max_diff": cv.get("max_diff"),
                "data_missing": cv_meta.get("data_missing", False),
                "missing_reason": cv_meta.get("missing_reason"),
            }

    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = str(e)
        result["response_time_ms"] = round((time.time() - t0) * 1000)

    # restore
    ApiFootballAdapter._get = ApiFootballAdapter._get_original

    return result


# ── 报告 ─────────────────────────────────────────────────────────

def print_summary(results: list[dict]):
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    warned = sum(1 for r in results if r["status"] == "WARN")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    avg_time = sum(r["response_time_ms"] for r in results) / max(total, 1)
    total_calls = sum(r["api_calls"] for r in results)
    cache_hits = sum(1 for r in results if r["standings_cache_hit"])
    cv_ok = sum(1 for r in results if r["cross_validation"] and not r["cross_validation"].get("data_missing"))
    cv_miss = sum(1 for r in results if r["cross_validation"] and r["cross_validation"].get("data_missing"))
    cv_none = sum(1 for r in results if not r["cross_validation"])

    print("\n" + "=" * 60)
    print("  STRESS TEST REPORT")
    print("=" * 60)
    print(f"  Date:            {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Matches tested:  {total}")
    print(f"  PASS:            {passed}")
    print(f"  WARN:            {warned}")
    print(f"  FAIL:            {failed}")
    print(f"  Avg response:    {avg_time:.0f} ms")
    print(f"  Total API calls: {total_calls}")
    print(f"  Cache hits:      {cache_hits}/{total}")
    print(f"  Cross-validate:  {cv_ok} ok / {cv_miss} missing / {cv_none} skipped")
    print("=" * 60)

    # 逐场摘要
    for r in results:
        flag = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[r["status"]]
        miss = f" missing={r['missing_fields']}" if r["missing_fields"] else ""
        err = f" error={r['error']}" if r["error"] else ""
        cv = r.get("cross_validation")
        if cv and not cv.get("data_missing"):
            cv_tag = f" CV={cv['agreement_level']}({cv['max_diff']})"
        elif cv and cv.get("data_missing"):
            cv_tag = f" CV=N/A"
        else:
            cv_tag = ""
        print(f"  [{flag}] {r['label']} | {r['api_calls']} calls | {r['response_time_ms']}ms{cv_tag}{miss}{err}")

    # 判定
    print()
    if failed > 0:
        print("  VERDICT: FAIL")
    elif warned > total * 0.3:
        print("  VERDICT: WARN (>30% with missing fields)")
    else:
        print("  VERDICT: PASS")
    print()


def save_report(results: list[dict]):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"stress_test_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Report saved: {path}")


# ── 入口 ─────────────────────────────────────────────────────────

async def main():
    if not KEY:
        print("ERROR: API_FOOTBALL_KEY not set")
        sys.exit(1)

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"Fetching fixtures for {today}...")
    fixtures = await fetch_fixtures(today)
    print(f"Found {len(fixtures)} fixtures to test")

    if not fixtures:
        print("No fixtures found. Try on a match day.")
        sys.exit(0)

    results = []
    for i, fix in enumerate(fixtures):
        f = fix["fixture"]
        t = fix["teams"]
        lg = fix["league"]
        label = f"{t['home']['name']} vs {t['away']['name']} ({lg['name']})"
        print(f"\n[{i+1}/{len(fixtures)}] {label}...")
        result = await run_analysis(f["id"], label)
        results.append(result)
        print(f"  -> {result['status']} | {result['api_calls']} calls | {result['response_time_ms']}ms")

    print_summary(results)
    save_report(results)


if __name__ == "__main__":
    asyncio.run(main())
