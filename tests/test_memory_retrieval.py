"""memory_retrieval v1 行为测试:record/query/feedback 真实闭环,非空跑。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "aios" / "agent_system"))

import memory_retrieval as mr  # noqa: E402


@pytest.fixture()
def clean_store(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "STORE_PATH", tmp_path / "store.jsonl")
    monkeypatch.setattr(mr, "FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    return tmp_path


def test_record_then_query_returns_scored_hit(clean_store):
    mr.record("t1", "修复登录超时 bug", "DEBUG", "success", "改超时参数为 30 秒")
    hits = mr.query("登录超时修复", top_k=3)
    assert len(hits) == 1
    assert hits[0]["id"] == "t1"
    assert hits[0]["outcome"] == "success"
    assert hits[0]["_score"] > 0


def test_query_respects_task_type_filter(clean_store):
    mr.record("t1", "登录超时", "DEBUG", "success", "x")
    mr.record("t2", "部署流程", "DEPLOY", "failed", "y")
    hits = mr.query("登录超时", task_type="DEBUG")
    assert [h["id"] for h in hits] == ["t1"]


def test_record_is_idempotent_by_task_id(clean_store):
    mr.record("t1", "旧描述", "DEBUG", "failed", "old")
    mr.record("t1", "新描述", "DEBUG", "success", "new")
    rows = mr._load()
    assert len(rows) == 1
    assert rows[0]["outcome"] == "success"


def test_feedback_appends_jsonl(clean_store):
    mr.feedback("t1", helpful=True)
    lines = (clean_store / "feedback.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["id"] == "t1" and rec["helpful"] is True and "ts" in rec


def test_query_empty_when_no_store(clean_store):
    assert mr.query("任意查询") == []
