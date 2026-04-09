"""
Gateway request-level audit — logs every completion request to three destinations:
  1. gateway_audit.jsonl (gateway-local, append-only)
  2. DataCollector api_call event (TaijiOS central events)
  3. Log line (structured, for stdout/file aggregation)
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .auth import CallerIdentity
from .reason_codes import GRC

log = logging.getLogger("gateway.audit")

GATEWAY_DIR = Path(__file__).resolve().parent
AUDIT_PATH = GATEWAY_DIR / "data" / "gateway_audit.jsonl"
AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_jsonl(entry: dict):
    """Append one JSON line to gateway_audit.jsonl."""
    try:
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning(f"Audit JSONL write failed: {e}")


def _emit_data_collector(entry: dict):
    """Best-effort push to TaijiOS DataCollector."""
    try:
        import sys
        ws = GATEWAY_DIR.parent.parent
        if str(ws) not in sys.path:
            sys.path.insert(0, str(ws))
        from aios.agent_system.data_collector import collect_api_call
        collect_api_call(
            endpoint="gateway:/v1/chat/completions",
            method="POST",
            status_code=entry.get("status_code", 200),
            latency_ms=entry.get("latency_ms", 0),
            model=entry.get("model", ""),
            trace_id=entry.get("request_id", ""),
        )
    except Exception:
        pass  # DataCollector is optional


def audit_request(
    request_id: str,
    identity: CallerIdentity,
    model: str,
    provider: str,
    stream: bool,
    status_code: int,
    reason_code: str,
    latency_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    error: str = "",
):
    """
    Record a completed (or failed) chat completion request.
    Writes to all three audit destinations.
    """
    entry = {
        "ts": _now_iso(),
        "request_id": request_id,
        "caller_id": identity.caller_id,
        "caller_class": identity.caller_class,
        "role": identity.role,
        "model": model,
        "provider": provider,
        "stream": stream,
        "status_code": status_code,
        "reason_code": reason_code,
        "latency_ms": round(latency_ms, 1),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    if error:
        entry["error"] = error[:500]

    # Destination 1: gateway_audit.jsonl
    _write_jsonl(entry)

    # Destination 2: DataCollector (best-effort)
    _emit_data_collector(entry)

    # Destination 3: structured log line
    log.info(
        f"[{request_id}] {identity.caller_id} {model}@{provider} "
        f"stream={stream} status={status_code} reason={reason_code} "
        f"latency={latency_ms:.0f}ms tokens={prompt_tokens}+{completion_tokens}"
    )


def audit_fallback(
    caller_type: str,
    model: str,
    provider: str,
    reason_code: str,
    request_id: str = "",
    error: str = "",
):
    """
    Record a direct-SDK fallback call that bypassed Gateway.
    Writes to the same gateway_audit.jsonl so all traffic is visible in one place.
    """
    import uuid
    rid = request_id or uuid.uuid4().hex[:12]
    entry = {
        "ts": _now_iso(),
        "request_id": rid,
        "caller_id": caller_type,
        "caller_class": "fallback_direct",
        "role": "",
        "model": model,
        "provider": provider,
        "stream": False,
        "status_code": 0,
        "reason_code": reason_code,
        "latency_ms": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "fallback_used": True,
        "fallback_mode": "direct_sdk",
    }
    if error:
        entry["error"] = error[:500]

    _write_jsonl(entry)
    log.warning(
        f"[{rid}] FALLBACK {caller_type} → {provider}/{model} reason={reason_code}"
    )


def daily_summary(date_str: str = "") -> dict:
    """
    Aggregate today's (or given date's) audit entries for daily report.
    Returns: {date, total_requests, total_errors, total_tokens, by_model, by_caller, avg_latency_ms}
    """
    from collections import defaultdict
    from datetime import date as _date

    target = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    total = 0
    errors = 0
    tokens = 0
    latency_sum = 0.0
    by_model = defaultdict(int)
    by_caller = defaultdict(int)
    by_reason = defaultdict(int)

    if not AUDIT_PATH.exists():
        return {"date": target, "total_requests": 0}

    try:
        with open(AUDIT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = entry.get("ts", "")
                if not ts.startswith(target):
                    continue
                total += 1
                sc = entry.get("status_code", 200)
                if sc >= 400:
                    errors += 1
                tokens += entry.get("total_tokens", 0)
                latency_sum += entry.get("latency_ms", 0)
                by_model[entry.get("model", "unknown")] += 1
                by_caller[entry.get("caller_id", "unknown")] += 1
                rc = entry.get("reason_code", "")
                if rc and rc != "OK.OK.OK":
                    by_reason[rc] += 1
    except Exception as e:
        log.warning(f"daily_summary read error: {e}")

    return {
        "date": target,
        "total_requests": total,
        "total_errors": errors,
        "total_tokens": tokens,
        "avg_latency_ms": round(latency_sum / total, 1) if total > 0 else 0,
        "by_model": dict(by_model),
        "by_caller": dict(by_caller),
        "by_reason": dict(by_reason),
    }
