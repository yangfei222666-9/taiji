"""Episodic memory retrieval for task_executor (v1, local JSONL, no external deps).

API contract (used by aios/agent_system/task_executor.py):
- query(task_desc, top_k=3, task_type=None) -> list of hits
    each hit: {"id", "text", "outcome", "_score"}  # _score = Jaccard keyword overlap
- feedback(memory_id, helpful=True) -> appends to the feedback log
- record(task_id, task_desc, task_type, outcome, text) -> idempotent store upsert

Scoring: CJK bigrams + ASCII word tokens, Jaccard overlap. This is a deterministic
keyword retrieval baseline, NOT vector search; the vector layer is the separate
Local KB (Product Spine). Honest limits are documented, not hidden.
"""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STORE_PATH = BASE_DIR / "memory_retrieval_store.jsonl"
FEEDBACK_PATH = BASE_DIR / "memory_retrieval_log.jsonl"

_lock = threading.Lock()


def _tokenize(text: str) -> set:
    """CJK bigrams + single CJK chars + lowercase ASCII words."""
    text = (text or "").lower()
    toks = set()
    for m in re.findall(r"[a-z0-9_]+", text):
        toks.add(m)
    cjk = re.sub(r"[^\u4e00-\u9fa5]", "", text)
    for i in range(len(cjk) - 1):
        toks.add(cjk[i : i + 2])
    toks.update(cjk)
    return toks


def _load() -> list:
    if not STORE_PATH.exists():
        return []
    rows = []
    for line in STORE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def record(task_id: str, task_desc: str = "", task_type: str = "",
           outcome: str = "unknown", text: str = "") -> None:
    """Idempotently upsert one episodic memory (same task_id replaces)."""
    with _lock:
        rows = [r for r in _load() if r.get("id") != task_id]
        rows.append({
            "id": task_id,
            "task_type": task_type or "",
            "desc": task_desc or "",
            "outcome": outcome or "unknown",
            "text": text or "",
        })
        STORE_PATH.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8",
        )


def query(task_desc: str, top_k: int = 3, task_type: str = None) -> list:
    """Return top_k hits scored by Jaccard token overlap; empty on no store."""
    q = _tokenize(task_desc)
    if not q:
        return []
    scored = []
    for r in _load():
        if task_type and r.get("task_type") and r["task_type"] != task_type:
            continue
        t = _tokenize((r.get("desc") or "") + " " + (r.get("text") or ""))
        if not t:
            continue
        score = len(q & t) / max(1, len(q | t))
        if score <= 0:
            continue
        scored.append({
            "id": r.get("id", ""),
            "text": r.get("text") or r.get("desc") or "",
            "outcome": r.get("outcome", "?"),
            "_score": round(score, 4),
        })
    scored.sort(key=lambda h: h["_score"], reverse=True)
    return scored[: max(0, top_k)]


def feedback(memory_id: str, helpful: bool = True) -> None:
    """Append one feedback record to the shared feedback log (append-only)."""
    with _lock:
        with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "id": memory_id,
                "helpful": bool(helpful),
                "ts": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False) + "\n")
