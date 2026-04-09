"""
Gateway policy engine — RBAC + model allowlist + budget + rate limiting.
Checks run AFTER auth, BEFORE routing to provider.
Policy events logged to policy_events.jsonl for gate consumption.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .auth import CallerIdentity
from .errors import ForbiddenError, RateLimitError, BudgetExceededError
from .reason_codes import GRC

log = logging.getLogger("gateway.policy")

GATEWAY_DIR = Path(__file__).resolve().parent
POLICY_EVENTS_PATH = GATEWAY_DIR / "data" / "policy_events.jsonl"
POLICY_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── RBAC: role → allowed permissions ────────────────────────────
_ROLE_PERMISSIONS = {
    "admin":    {"llm:call", "llm:stream", "llm:list_models", "audit:read", "config:read", "config:write"},
    "operator": {"llm:call", "llm:stream", "llm:list_models", "audit:read"},
    "viewer":   {"llm:list_models", "audit:read"},
}

# ── Model allowlist per role (None = all allowed) ───────────────
_ROLE_MODEL_ALLOWLIST: dict[str, Optional[set[str]]] = {
    "admin": None,
    "operator": None,
    "viewer": None,
}


class RateLimiter:
    """Simple in-memory sliding-window rate limiter per caller_id."""

    def __init__(self, max_requests: int = 60, window_s: int = 60):
        self._max = max_requests
        self._window = window_s
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, caller_id: str) -> bool:
        now = time.time()
        bucket = self._buckets[caller_id]
        # Prune expired
        cutoff = now - self._window
        self._buckets[caller_id] = [t for t in bucket if t > cutoff]
        return len(self._buckets[caller_id]) < self._max

    def record(self, caller_id: str):
        self._buckets[caller_id].append(time.time())


# ── Singleton rate limiter ──────────────────────────────────────
_rate_limiter = RateLimiter(
    max_requests=int(os.environ.get("TAIJIOS_GATEWAY_RATE_LIMIT", "60")),
    window_s=int(os.environ.get("TAIJIOS_GATEWAY_RATE_WINDOW_S", "60")),
)


def _write_policy_event(caller_id: str, action: str, result: str, reason_code: str, model: str = ""):
    """Append policy decision to policy_events.jsonl."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "caller_id": caller_id,
        "action": action,
        "result": result,
        "reason_code": reason_code,
        "model": model,
    }
    try:
        with open(POLICY_EVENTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _check_budget() -> dict:
    """Check budget via CostGuardian. Returns {"status": "ok"|"warning"|"exceeded", ...}."""
    try:
        import sys
        from pathlib import Path
        ws = Path(__file__).resolve().parent.parent.parent
        if str(ws) not in sys.path:
            sys.path.insert(0, str(ws))
        from aios.agent_system.cost_guardian import CostGuardian
        return CostGuardian().check_budget()
    except Exception as e:
        log.warning(f"CostGuardian unavailable, skipping budget check: {e}")
        return {"status": "ok"}


def enforce_policy(identity: CallerIdentity, model: str, stream: bool = False):
    """
    Run all policy checks. Raises on violation.
    Call AFTER auth, BEFORE routing.
    """
    # 1. RBAC — does this role have llm:call?
    required_perm = "llm:stream" if stream else "llm:call"
    role_perms = _ROLE_PERMISSIONS.get(identity.role, set())
    if required_perm not in role_perms:
        _write_policy_event(identity.caller_id, "rbac_check", "denied", GRC.AUTH_RBAC_DENIED, model)
        raise ForbiddenError(
            f"Role '{identity.role}' lacks permission '{required_perm}'",
            reason_code=GRC.AUTH_RBAC_DENIED,
        )

    # 2. Model allowlist
    allowlist = _ROLE_MODEL_ALLOWLIST.get(identity.role)
    if allowlist is not None and model not in allowlist:
        _write_policy_event(identity.caller_id, "model_allowlist", "denied", GRC.POLICY_MODEL_DENIED, model)
        raise ForbiddenError(
            f"Model '{model}' not allowed for role '{identity.role}'",
            reason_code=GRC.POLICY_MODEL_DENIED,
        )

    # 3. Rate limit
    if not _rate_limiter.check(identity.caller_id):
        _write_policy_event(identity.caller_id, "rate_limit", "denied", GRC.POLICY_RATE_LIMITED, model)
        raise RateLimitError(
            f"Rate limit exceeded for {identity.caller_id}",
            reason_code=GRC.POLICY_RATE_LIMITED,
        )
    _rate_limiter.record(identity.caller_id)

    # 4. Budget check (via CostGuardian)
    budget = _check_budget()
    if budget.get("status") == "exceeded":
        _write_policy_event(identity.caller_id, "budget_check", "denied", GRC.POLICY_BUDGET_EXCEEDED, model)
        raise BudgetExceededError(
            f"Daily budget exceeded (${budget.get('used', 0):.3f}/${budget.get('budget_daily', 0):.2f})",
            reason_code=GRC.POLICY_BUDGET_EXCEEDED,
        )

    # All checks passed
    _write_policy_event(identity.caller_id, "policy_check", "allowed", "OK.OK.OK", model)
