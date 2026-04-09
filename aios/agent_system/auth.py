"""
auth.py - 统一鉴权模块
- token 从环境变量 TAIJIOS_API_TOKEN 或配置文件读取
- 豁免列表：本机 Task Scheduler 触发的内部脚本
- 所有鉴权结果写入 audit.jsonl
"""
import hashlib
import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _audit_path() -> Path:
    try:
        from config_center import audit_jsonl_path
        return audit_jsonl_path()
    except Exception:
        return _repo_root() / "aios/agent_system/data/audit.jsonl"


def _write_audit(event: dict) -> None:
    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _load_token() -> Optional[str]:
    # 1. 环境变量优先
    token = os.environ.get("TAIJIOS_API_TOKEN", "").strip()
    if token:
        return token
    # 2. 配置文件
    cfg = _repo_root() / "aios/agent_system/config/auth.json"
    if cfg.exists():
        try:
            obj = json.loads(cfg.read_text(encoding="utf-8"))
            return obj.get("api_token", "").strip() or None
        except Exception:
            pass
    return None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def verify(token: str, caller: str = "", action: str = "", ip: str = "", request_id: str = "") -> dict:
    """
    验证 token，返回:
      {"ok": True,  "reason": "authorized"}
      {"ok": False, "reason": "missing_token" | "invalid_token"}
    同时写 audit.jsonl
    """
    import uuid
    expected = _load_token()
    host = socket.gethostname()

    if not token:
        result = {"ok": False, "reason": "missing_token"}
    elif not expected:
        result = {"ok": False, "reason": "token_not_configured"}
    elif token != expected:
        result = {"ok": False, "reason": "invalid_token"}
    else:
        result = {"ok": True, "reason": "authorized"}

    _write_audit({
        "ts": _now_iso(),
        "request_id": request_id or uuid.uuid4().hex[:12],
        "host": host,
        "ip": ip,
        "caller": caller,
        "action": action,
        "token_hash": _hash_token(token) if token else "",
        "result": result["reason"],
    })

    return result


def require(token: str, caller: str = "", action: str = "") -> None:
    """验证失败直接抛 PermissionError"""
    r = verify(token, caller=caller, action=action)
    if not r["ok"]:
        raise PermissionError(f"auth_failed: {r['reason']}")


def write_op_audit(
    *,
    caller: str = "",
    action: str = "",
    op_result: str,  # "success" | "failed"
    request_id: str = "",
    task_id: str = "",
    agent_id: str = "",
    fail_reason: str = "",
    duration_ms: int = 0,
    ip: str = "",
) -> None:
    """
    记录业务操作审计（鉴权通过后的操作结果）。
    字段：who(caller/ip) / what(action) / when(ts) / result(op_result) + 关联 ID
    """
    import uuid
    _write_audit({
        "ts": _now_iso(),
        "request_id": request_id or uuid.uuid4().hex[:12],
        "host": socket.gethostname(),
        "ip": ip,
        "caller": caller,
        "action": action,
        "op_result": op_result,
        "task_id": task_id,
        "agent_id": agent_id,
        "fail_reason": fail_reason,
        "duration_ms": duration_ms,
    })
