from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


AUDIT_LOG_PATH = Path(
    os.getenv("TAIJI_AUDIT_LOG", "examples/quickstart_output/demo_audit_log.jsonl")
)
ENABLE_EXTERNAL_API = os.getenv("TAIJI_ENABLE_EXTERNAL_API", "false").lower() == "true"


@dataclass
class Event:
    tenant_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: float


@dataclass
class PipelineResult:
    status: str
    mode: str
    decision: str
    reason: str
    degraded: bool


def write_audit_log(event: Event, result: PipelineResult) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": asdict(event),
        "result": asdict(result),
        "logged_at": time.time(),
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def hard_gate(event: Event) -> tuple[bool, str]:
    if not event.tenant_id.strip():
        return False, "tenant_id is required"
    if event.event_type not in {"learning_event", "feedback_event"}:
        return False, "only learning-only event types are enabled in this demo"
    if event.payload.get("requires_judgment") is True:
        return False, "judgment path is intentionally stubbed"
    return True, "accepted"


def process_learning_only(event: Event) -> PipelineResult:
    allowed, reason = hard_gate(event)
    if not allowed:
        result = PipelineResult(
            status="blocked",
            mode="learning-only",
            decision="degrade",
            reason=reason,
            degraded=True,
        )
        write_audit_log(event, result)
        return result

    result = PipelineResult(
        status="ok",
        mode="learning-only",
        decision="learn",
        reason=(
            "external API flag enabled, but provider call is stubbed"
            if ENABLE_EXTERNAL_API
            else "external APIs disabled"
        ),
        degraded=False,
    )
    write_audit_log(event, result)
    return result


def run_cli_demo() -> None:
    event = Event(
        tenant_id=os.getenv("TAIJI_TENANT_ID", "demo-tenant"),
        event_type=os.getenv("TAIJI_EVENT_TYPE", "learning_event"),
        payload={
            "message": os.getenv("TAIJI_EVENT_MESSAGE", "hello taiji"),
            "requires_judgment": os.getenv("TAIJI_REQUIRES_JUDGMENT", "false").lower()
            == "true",
        },
        created_at=time.time(),
    )
    result = process_learning_only(event)
    print(json.dumps({"event": asdict(event), "result": asdict(result)}, indent=2))
    print(f"audit_log={AUDIT_LOG_PATH}")


if __name__ == "__main__":
    run_cli_demo()
