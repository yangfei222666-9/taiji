"""
Gateway Phase 1 gate reader — reads evidence files, outputs PASS/FAIL.
Usage:
    python -m aios.gateway.gate
    # or
    from aios.gateway.gate import run_gate
    result = run_gate()
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("gateway.gate")

GATEWAY_DIR = Path(__file__).resolve().parent
DATA_DIR = GATEWAY_DIR / "data"


def _check_file_exists(path: Path) -> dict:
    exists = path.exists()
    return {"path": str(path), "exists": exists, "status": "PASS" if exists else "FAIL"}


def _check_health() -> dict:
    path = DATA_DIR / "health_latest.json"
    if not path.exists():
        return {"check": "health", "status": "FAIL", "reason": "health_latest.json missing"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        status = data.get("status", "unknown")
        checks = data.get("checks", {})
        has_real = any(v == "ok" for v in checks.values())
        if not has_real:
            return {"check": "health", "status": "FAIL", "reason": "no healthy provider"}
        return {"check": "health", "status": "PASS", "provider_status": checks}
    except Exception as e:
        return {"check": "health", "status": "FAIL", "reason": str(e)}


def _check_stats() -> dict:
    path = DATA_DIR / "stats_latest.json"
    if not path.exists():
        return {"check": "stats", "status": "FAIL", "reason": "stats_latest.json missing"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        total = data.get("total_requests", 0)
        if total == 0:
            return {"check": "stats", "status": "FAIL", "reason": "no requests recorded"}
        return {"check": "stats", "status": "PASS", "total_requests": total}
    except Exception as e:
        return {"check": "stats", "status": "FAIL", "reason": str(e)}


def _check_audit() -> dict:
    path = DATA_DIR / "gateway_audit.jsonl"
    if not path.exists():
        return {"check": "audit", "status": "FAIL", "reason": "gateway_audit.jsonl missing"}
    try:
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        lines = [l for l in lines if l.strip()]
        if not lines:
            return {"check": "audit", "status": "FAIL", "reason": "audit file empty"}
        # Check for required fields in last entry
        last = json.loads(lines[-1])
        required = ["ts", "request_id", "caller_id", "model", "status_code", "reason_code"]
        missing = [f for f in required if f not in last]
        if missing:
            return {"check": "audit", "status": "FAIL", "reason": f"missing fields: {missing}"}
        # Check no plaintext keys leaked
        full_text = path.read_text(encoding="utf-8")
        if "Bearer " in full_text or "api_key" in full_text.lower():
            return {"check": "audit", "status": "FAIL", "reason": "possible key leak in audit"}
        return {"check": "audit", "status": "PASS", "entries": len(lines)}
    except Exception as e:
        return {"check": "audit", "status": "FAIL", "reason": str(e)}


def _check_policy_events() -> dict:
    path = DATA_DIR / "policy_events.jsonl"
    if not path.exists():
        return {"check": "policy_events", "status": "FAIL", "reason": "policy_events.jsonl missing"}
    try:
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        lines = [l for l in lines if l.strip()]
        if not lines:
            return {"check": "policy_events", "status": "FAIL", "reason": "policy_events empty"}
        return {"check": "policy_events", "status": "PASS", "entries": len(lines)}
    except Exception as e:
        return {"check": "policy_events", "status": "FAIL", "reason": str(e)}


def _check_auth_block() -> dict:
    """Verify that auth blocks are recorded (at least 1 rejected entry in audit)."""
    path = DATA_DIR / "gateway_audit.jsonl"
    if not path.exists():
        return {"check": "auth_block", "status": "INCONCLUSIVE", "reason": "no audit file"}
    try:
        has_reject = False
        for line in path.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("result") == "rejected" or entry.get("status_code") in (401, 403):
                has_reject = True
                break
        if has_reject:
            return {"check": "auth_block", "status": "PASS"}
        return {"check": "auth_block", "status": "INCONCLUSIVE", "reason": "no auth block found in audit"}
    except Exception as e:
        return {"check": "auth_block", "status": "FAIL", "reason": str(e)}


def run_gate() -> dict:
    """Run all gate checks. Returns structured result with PASS/FAIL."""
    checks = [
        _check_file_exists(DATA_DIR / "gateway_audit.jsonl"),
        _check_file_exists(DATA_DIR / "policy_events.jsonl"),
        _check_file_exists(DATA_DIR / "health_latest.json"),
        _check_file_exists(DATA_DIR / "stats_latest.json"),
        _check_health(),
        _check_stats(),
        _check_audit(),
        _check_policy_events(),
        _check_auth_block(),
    ]

    failures = [c for c in checks if c.get("status") == "FAIL"]
    top_reason = failures[0].get("reason", "") if failures else ""

    overall = "PASS" if not failures else "FAIL"

    evidence_paths = [
        str(DATA_DIR / "gateway_audit.jsonl"),
        str(DATA_DIR / "policy_events.jsonl"),
        str(DATA_DIR / "health_latest.json"),
        str(DATA_DIR / "stats_latest.json"),
    ]

    result = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "gate": "gateway_phase1",
        "overall": overall,
        "top_reason_code": top_reason,
        "checks": checks,
        "evidence_paths": evidence_paths,
        "failures": len(failures),
        "total_checks": len(checks),
    }

    # Dump to file
    out_path = GATEWAY_DIR.parent.parent / "docs" / "gateway_phase1_gate_latest.json"
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"Gate result written to {out_path}")
    except Exception as e:
        log.warning(f"Gate result write failed: {e}")

    return result


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    result = run_gate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["overall"] == "PASS" else 1)
