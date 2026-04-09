"""
Gateway auth — API key verification + audit trail.
Supports two caller classes:
  - service_token: internal TaijiOS services use TAIJIOS_API_TOKEN
  - api_key: external callers use gateway-specific keys (hashed in api_keys.json)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Request

log = logging.getLogger("gateway.auth")

GATEWAY_DIR = Path(__file__).resolve().parent
API_KEYS_PATH = GATEWAY_DIR / "config" / "api_keys.json"
AUDIT_PATH = GATEWAY_DIR / "data" / "gateway_audit.jsonl"

# Also try to use existing TaijiOS auth
WORKSPACE = GATEWAY_DIR.parent.parent
sys.path.insert(0, str(WORKSPACE / "aios" / "agent_system"))


@dataclass
class CallerIdentity:
    caller_id: str
    caller_class: str  # "service_token" | "api_key"
    role: str  # "admin" | "operator" | "viewer"


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _hash_prefix(key: str) -> str:
    return _hash_key(key)[:16]


def _load_api_keys() -> dict:
    """Load gateway API keys from config. Format: {"keys": [{"hash": "...", "caller_id": "...", "role": "..."}]}"""
    if not API_KEYS_PATH.exists():
        return {}
    try:
        with open(API_KEYS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k["hash"]: k for k in data.get("keys", [])}
    except Exception:
        return {}


def _get_service_token() -> str:
    """Get the internal TaijiOS service token."""
    token = os.getenv("TAIJIOS_API_TOKEN", "")
    if not token:
        try:
            auth_cfg = WORKSPACE / "aios" / "agent_system" / "config" / "auth.json"
            if auth_cfg.exists():
                with open(auth_cfg, "r", encoding="utf-8") as f:
                    token = json.load(f).get("api_token", "")
        except Exception:
            pass
    return token


def _write_audit(request_id: str, caller_id: str, caller_class: str,
                 action: str, result: str, reason: str = "", ip: str = ""):
    """Write auth event to gateway audit log. Never log plaintext keys."""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "request_id": request_id,
        "caller_id": caller_id,
        "caller_class": caller_class,
        "action": action,
        "result": result,
        "reason": reason,
        "ip": ip,
    }
    try:
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning(f"Audit write failed: {e}")


def extract_key(request: Request) -> str:
    """Extract API key from Authorization header or X-API-Key header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.headers.get("X-API-Key", "").strip()


def verify_request(request: Request) -> Optional[CallerIdentity]:
    """
    Verify the request's API key. Returns CallerIdentity or None.
    Writes audit trail for all attempts.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    ip = request.client.host if request.client else ""
    key = extract_key(request)

    if not key:
        _write_audit(request_id, "", "", "auth", "rejected", "missing_key", ip)
        return None

    key_hash = _hash_key(key)

    # Check 1: Is it the internal service token?
    service_token = _get_service_token()
    if service_token and key == service_token:
        identity = CallerIdentity(
            caller_id="taijios_service",
            caller_class="service_token",
            role="admin",
        )
        _write_audit(request_id, identity.caller_id, identity.caller_class,
                     "auth", "authorized", "", ip)
        return identity

    # Check 2: Is it a gateway API key?
    api_keys = _load_api_keys()
    if key_hash in api_keys:
        entry = api_keys[key_hash]
        identity = CallerIdentity(
            caller_id=entry.get("caller_id", "unknown"),
            caller_class="api_key",
            role=entry.get("role", "viewer"),
        )
        _write_audit(request_id, identity.caller_id, identity.caller_class,
                     "auth", "authorized", "", ip)
        return identity

    # Rejected — log hash prefix only, never the key itself
    _write_audit(request_id, f"hash:{_hash_prefix(key)}", "", "auth",
                 "rejected", "invalid_key", ip)
    return None
