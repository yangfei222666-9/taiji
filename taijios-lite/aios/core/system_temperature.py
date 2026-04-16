"""
TaijiOS Ising 系统温度计 — 静默观察版
Week 1-2 只记录，不触发任何动作。两周后根据实际数据回调权重。

温度 T ∈ [0, 1]：
  T < 0.3  → 低温（系统健康）
  0.3-0.7  → 中温（需关注）
  T > 0.7  → 高温（系统异常）

依赖方向：system_temperature ← multi_llm（观察点）
system_temperature 读取 failure_samples 和 validation_health，不写入。
"""

from __future__ import annotations

import json
import time
import logging
import threading
from collections import deque
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aios.core.validation_meta import ValidationMeta

logger = logging.getLogger("system_temperature")


class SystemTemperature:
    """Ising 系统温度计。只计算，只记录，不决策。"""

    def __init__(self, log_dir: Path | str = None):
        self.history: deque = deque(maxlen=100)
        self._lock = threading.Lock()

        # 温度区间
        self.T_low = 0.3
        self.T_critical = 0.7

        # 权重（初值，静默观察期不生效于决策）
        self.weights = {
            "failure_rate": 0.4,      # 近10轮失败率
            "l3_active": 0.3,         # L3 活跃触发数 / 5
            "timeout_freq": 0.2,      # 超时事件频率
            "verify_variance": 0.1,   # 多模型答案方差（预留）
        }

        # 最近 N 次调用的结果记录
        self._recent_calls: deque = deque(maxlen=50)

        # 日志
        if log_dir is None:
            log_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "temperature"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def record_call(self, meta: "ValidationMeta | dict") -> None:
        """记录一次 validated_call 的结果，用于温度计算"""
        if hasattr(meta, "verification_status"):
            status = meta.verification_status
            total_ms = meta.total_ms
            triggered = [r["rule"] if isinstance(r, dict) else r
                         for r in (meta.triggered_rules or [])]
            degraded = meta.degraded
        elif isinstance(meta, dict):
            status = meta.get("verification_status", meta.get("step2", "unknown"))
            total_ms = meta.get("total_ms", 0)
            triggered = meta.get("triggered_rules", [])
            degraded = meta.get("degraded", False)
        else:
            return

        with self._lock:
            self._recent_calls.append({
                "ts": time.time(),
                "status": status,
                "total_ms": total_ms,
                "triggered": triggered,
                "degraded": degraded,
            })

    def _recent_failure_rate(self) -> float:
        """近10轮中 failed/error/degraded 的比率"""
        recent = list(self._recent_calls)[-10:]
        if not recent:
            return 0.0
        fails = sum(1 for c in recent
                    if c["status"] in ("failed", "error", "degraded"))
        return fails / len(recent)

    def _l3_active_ratio(self) -> float:
        """L3 活跃触发数 / 5（归一化到 0-1）"""
        try:
            from aios.core.failure_samples import get_active_l3_count
            count = get_active_l3_count()
            return min(count / 5.0, 1.0)
        except ImportError:
            return 0.0

    def _timeout_frequency(self) -> float:
        """近20次调用中超时（>30s）的比率"""
        recent = list(self._recent_calls)[-20:]
        if not recent:
            return 0.0
        timeouts = sum(1 for c in recent if c["total_ms"] > 30000)
        return timeouts / len(recent)

    def _verify_variance(self) -> float:
        """多模型答案方差（预留，当前返回0）"""
        return 0.0

    def compute(self) -> float:
        """计算当前系统温度 T ∈ [0, 1]"""
        signals = {
            "failure_rate": self._recent_failure_rate(),
            "l3_active": self._l3_active_ratio(),
            "timeout_freq": self._timeout_frequency(),
            "verify_variance": self._verify_variance(),
        }
        T = sum(self.weights[k] * signals[k] for k in self.weights)
        T = min(max(T, 0.0), 1.0)  # clamp

        with self._lock:
            self.history.append((time.time(), T, signals))

        return T

    def observation_only(self) -> dict:
        """静默观察接口，返回温度但不影响决策"""
        T = self.compute()
        return {
            "T": round(T, 4),
            "zone": "low" if T < self.T_low else ("critical" if T > self.T_critical else "mid"),
            "would_be_policy": self._would_policy(T),
            "signals": self.history[-1][2] if self.history else {},
        }

    def _would_policy(self, T: float) -> str:
        """假设温度生效时的策略（仅参考，不执行）"""
        if T < self.T_low:
            return "normal: 标准两阶段验证"
        elif T < self.T_critical:
            return "cautious: 建议增加验证轮次"
        else:
            return "emergency: 建议强制4模型+暂停降级"

    def log_observation(self, meta: "ValidationMeta | dict" = None) -> dict:
        """记录调用 + 计算温度 + 写日志，一步到位"""
        if meta:
            self.record_call(meta)
        obs = self.observation_only()

        # 写 jsonl
        try:
            record = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                **obs,
            }
            path = self.log_dir / f"temperature_{date.today():%Y%m%d}.jsonl"
            line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
            with self._lock:
                with path.open("a", encoding="utf-8") as f:
                    f.write(line)
        except Exception as e:
            logger.warning(f"[temperature] 日志写入失败: {e}")

        return obs


# ── 模块级单例 ────────────────────────────────────────────────

_instance: SystemTemperature | None = None


def get_temperature() -> SystemTemperature:
    """获取全局温度计单例"""
    global _instance
    if _instance is None:
        _instance = SystemTemperature()
    return _instance


def observe(meta: "ValidationMeta | dict" = None) -> dict:
    """快捷入口：记录 + 观察"""
    return get_temperature().log_observation(meta)
