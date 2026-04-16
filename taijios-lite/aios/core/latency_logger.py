"""
TaijiOS 延迟归因日志 — latency_breakdown.jsonl

每次 validated_call 写一条记录，按天切文件。
用于事后分析：QPS 分布、延迟 p50/p95/p99、规则触发率、降级比例。

依赖方向：latency_logger ← multi_llm
latency_logger 只依赖 validation_meta，不 import failure_rules/failure_samples。
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aios.core.validation_meta import ValidationMeta

logger = logging.getLogger("latency_logger")


class LatencyLogger:
    """延迟归因日志写入器。

    WARNING: 使用 threading.Lock，仅保证单进程内线程安全。
    多进程并发写入同一日志文件可能导致行交叉损坏。
    如未来启用多进程 gateway，需要：
    (1) 每进程写不同文件名（如加 pid 后缀）或
    (2) 引入 filelock 依赖做跨进程锁。
    """

    def __init__(self, log_dir: Path | str = None):
        if log_dir is None:
            log_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "latency"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _current_path(self) -> Path:
        return self.log_dir / f"latency_{date.today():%Y%m%d}.jsonl"

    def log(self, meta: "ValidationMeta") -> None:
        """写入一条日志。失败不抛异常，只记 warning，不影响主流程。"""
        try:
            if hasattr(meta, 'to_dict'):
                record = meta.to_dict()
            elif isinstance(meta, dict):
                record = dict(meta)
            else:
                record = {"raw": str(meta)}

            record["ts"] = datetime.now().isoformat(timespec="seconds")

            # 去掉 final_content（太长，日志不需要正文）
            record.pop("final_content", None)

            # triggered_rules 精简：只保留 rule + severity
            if record.get("triggered_rules"):
                record["triggered_rules"] = [
                    {"rule": r["rule"], "severity": r.get("severity", "warning")}
                    if isinstance(r, dict) else r
                    for r in record["triggered_rules"]
                ]

            line = json.dumps(record, ensure_ascii=False, default=str) + "\n"

            with self._lock:
                with self._current_path().open("a", encoding="utf-8") as f:
                    f.write(line)

        except Exception as e:
            logger.warning(f"[latency_logger] 写入失败: {e}")

    def read_day(self, day: date = None) -> list[dict]:
        """读取某天的全部记录"""
        if day is None:
            day = date.today()
        path = self.log_dir / f"latency_{day:%Y%m%d}.jsonl"
        if not path.exists():
            return []
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records


# ── 模块级单例 ────────────────────────────────────────────────

_default_logger: LatencyLogger | None = None


def get_latency_logger(log_dir: Path | str = None) -> LatencyLogger:
    """获取默认 logger 实例，懒加载"""
    global _default_logger
    if _default_logger is None:
        _default_logger = LatencyLogger(log_dir)
    return _default_logger


def log_meta(meta: "ValidationMeta") -> None:
    """快捷入口，消费端只调这个"""
    get_latency_logger().log(meta)
