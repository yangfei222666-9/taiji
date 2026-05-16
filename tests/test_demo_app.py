from __future__ import annotations

import json

from examples.demo_app import Event, process_learning_only


def test_demo_learning_only_writes_audit_log(tmp_path, monkeypatch):
    audit_log = tmp_path / "audit_log.jsonl"
    monkeypatch.setattr("examples.demo_app.AUDIT_LOG_PATH", audit_log)
    event = Event(
        tenant_id="tenant-1",
        event_type="learning_event",
        payload={"requires_judgment": False},
        created_at=1.0,
    )

    result = process_learning_only(event)

    assert result.status == "ok"
    assert result.mode == "learning-only"
    assert result.decision == "learn"
    assert audit_log.exists()
    record = json.loads(audit_log.read_text(encoding="utf-8").strip())
    assert record["result"]["status"] == "ok"


def test_demo_blocks_judgment_path(tmp_path, monkeypatch):
    audit_log = tmp_path / "audit_log.jsonl"
    monkeypatch.setattr("examples.demo_app.AUDIT_LOG_PATH", audit_log)
    event = Event(
        tenant_id="tenant-1",
        event_type="learning_event",
        payload={"requires_judgment": True},
        created_at=1.0,
    )

    result = process_learning_only(event)

    assert result.status == "blocked"
    assert result.degraded is True
    assert "judgment path" in result.reason
