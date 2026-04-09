#!/usr/bin/env python3
"""
Experience Learner v4.0 - Phase 3 生产版（含灰度 + 幂等 + 版本归因）

核心接口（最小）：
  - recommend(context) → 推荐历史成功策略
  - save_success(record) → 保存成功轨迹

关键特性：
  1. 幂等键：task_type + strategy_hash，避免经验重复污染
  2. 版本字段：strategy_version，便于 48h 复盘按版本归因
  3. 灰度控制：GRAYSCALE_RATIO（默认 10%），先灰度再全量
  4. 回滚开关：ENABLE_RECOMMENDATION（默认 True），一键关闭推荐
  5. 验收指标：recommend_hit_rate / regen_success_rate / manual_intervention_rate
  6. "推荐后失败"分桶：track_recommendation_outcome()
"""

import json
import hashlib
import random
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ── 配置 ──────────────────────────────────────────────────────────────────────
# Import unified paths
from paths import EXPERIENCE_DB_V4, RECOMMENDATION_LOG

AIOS_DIR = Path(__file__).resolve().parent
EXPERIENCE_DB_FILE = EXPERIENCE_DB_V4
RECOMMENDATION_LOG_FILE = RECOMMENDATION_LOG
LEARNER_CONFIG_FILE = AIOS_DIR / "learner_v4_config.json"
LEARNER_METRICS_FILE = AIOS_DIR / "learner_v4_metrics.json"

# 策略版本（每次修改推荐逻辑时递增）
STRATEGY_VERSION = "v4.0.0"

# ── 默认配置（可通过 config 文件覆盖）────────────────────────────────────────
DEFAULT_CONFIG = {
    "enable_recommendation": True,     # 回滚开关：False 则所有推荐退化为 default
    "grayscale_ratio": 0.10,           # 灰度比例：10% 任务使用推荐策略
    "min_confidence": 0.60,            # 最低置信度：低于此值不推荐
    "max_experience_age_days": 30,     # 经验最大有效期（天）
    "strategy_version": STRATEGY_VERSION,
}


def _load_config() -> dict:
    """加载配置（文件覆盖默认值）"""
    config = DEFAULT_CONFIG.copy()
    if LEARNER_CONFIG_FILE.exists():
        try:
            override = json.loads(LEARNER_CONFIG_FILE.read_text(encoding="utf-8"))
            config.update(override)
        except Exception:
            pass
    return config


def _save_config(config: dict):
    """保存配置"""
    LEARNER_CONFIG_FILE.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 幂等键 ───────────────────────────────────────────────────────────────────
def _idem_key(error_type: str, strategy: str) -> str:
    """
    生成幂等键：task_type + strategy_hash
    避免同一 error_type + strategy 组合重复写入
    """
    raw = f"{error_type}:{strategy}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── 指标 ──────────────────────────────────────────────────────────────────────
class LearnerMetrics:
    """验收指标追踪器"""

    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        if LEARNER_METRICS_FILE.exists():
            try:
                return json.loads(LEARNER_METRICS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "recommend_total": 0,
            "recommend_hit": 0,          # 非 default 推荐
            "recommend_default": 0,      # 退化为 default
            "recommend_skipped_grayscale": 0,  # 灰度跳过
            "recommend_skipped_disabled": 0,   # 开关关闭跳过
            "regen_total": 0,
            "regen_success": 0,
            "regen_failed": 0,
            "manual_intervention": 0,
            # 推荐后失败分桶
            "post_recommend_success": 0,
            "post_recommend_failed": 0,
            "post_default_success": 0,
            "post_default_failed": 0,
        }

    def _save(self):
        LEARNER_METRICS_FILE.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def inc(self, key: str, n: int = 1):
        self._data[key] = self._data.get(key, 0) + n
        self._save()

    def get_report(self) -> dict:
        d = self._data
        total = d["recommend_total"] or 1
        regen_total = d["regen_total"] or 1
        post_rec_total = (d["post_recommend_success"] + d["post_recommend_failed"]) or 1

        return {
            "recommend_hit_rate": round(d["recommend_hit"] / total, 4),
            "regen_success_rate": round(d["regen_success"] / regen_total, 4),
            "manual_intervention_rate": round(d["manual_intervention"] / regen_total, 4),
            "post_recommend_failure_rate": round(
                d["post_recommend_failed"] / post_rec_total, 4
            ),
            "grayscale_skip_rate": round(d["recommend_skipped_grayscale"] / total, 4),
            "raw": d,
        }


# ── 经验库（本地 JSONL，向量检索可选）────────────────────────────────────────
class ExperienceStore:
    """
    本地 JSONL 经验库（幂等写入 + 版本字段）
    后续可替换为 LanceDB 向量检索
    """

    def __init__(self):
        self._entries = self._load()
        self._idem_keys = {e.get("idem_key") for e in self._entries if e.get("idem_key")}

    def _load(self) -> list:
        if not EXPERIENCE_DB_FILE.exists():
            return []
        entries = []
        with open(EXPERIENCE_DB_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        continue
        return entries

    def save(self, record: dict) -> bool:
        """
        幂等写入：同一 error_type + strategy 组合只写一次
        返回 True 表示新写入，False 表示幂等跳过
        """
        error_type = record.get("error_type", "unknown")
        strategy = record.get("strategy", "default_recovery")
        key = _idem_key(error_type, strategy)

        if key in self._idem_keys:
            return False  # 幂等命中，跳过

        entry = {
            "idem_key": key,
            "error_type": error_type,
            "strategy": strategy,
            "strategy_version": record.get("strategy_version", STRATEGY_VERSION),
            "task_id": record.get("task_id", "unknown"),
            "confidence": record.get("confidence", 0.80),
            "recovery_time": record.get("recovery_time", 0.0),
            "timestamp": datetime.now().isoformat(),
            "success": record.get("success", True),
        }

        with open(EXPERIENCE_DB_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._entries.append(entry)
        self._idem_keys.add(key)
        return True

    def query(self, error_type: str, limit: int = 3) -> list:
        """按 error_type 查询历史成功策略（按 confidence 降序）"""
        matches = [
            e for e in self._entries
            if e.get("error_type") == error_type and e.get("success", False)
        ]
        matches.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return matches[:limit]

    def stats(self) -> dict:
        total = len(self._entries)
        success = sum(1 for e in self._entries if e.get("success"))
        error_types = set(e.get("error_type") for e in self._entries)
        strategies = set(e.get("strategy") for e in self._entries)
        return {
            "total_entries": total,
            "success_entries": success,
            "unique_error_types": len(error_types),
            "unique_strategies": len(strategies),
        }


# ── 核心类 ────────────────────────────────────────────────────────────────────
class ExperienceLearnerV4:
    """
    Phase 3 生产版经验学习器

    接口最小：
      - recommend(context) → dict（含 recommended_strategy / strategy_version / grayscale）
      - save_success(record) → bool
      - track_outcome(task_id, strategy, success) → None
    """

    def __init__(self):
        self.config = _load_config()
        self.store = ExperienceStore()
        self.metrics = LearnerMetrics()

    def recommend(self, context: dict) -> dict:
        """
        推荐历史成功策略

        Args:
            context: {"error_type": str, "task_id": str, "prompt": str, ...}

        Returns:
            {
                "recommended_strategy": str,
                "strategy_version": str,
                "source": "experience" | "default" | "disabled" | "grayscale_skip",
                "confidence": float,
                "grayscale": bool,  # 是否在灰度范围内
            }
        """
        error_type = context.get("error_type", "unknown")
        task_id = context.get("task_id", "unknown")
        self.metrics.inc("recommend_total")

        # 1. 回滚开关检查
        if not self.config.get("enable_recommendation", True):
            self.metrics.inc("recommend_skipped_disabled")
            result = self._default_result(error_type, "disabled")
            self._log_recommendation(task_id, error_type, result)
            return result

        # 2. 灰度门控
        in_grayscale = random.random() < self.config.get("grayscale_ratio", 0.10)
        if not in_grayscale:
            self.metrics.inc("recommend_skipped_grayscale")
            result = self._default_result(error_type, "grayscale_skip")
            result["grayscale"] = False
            self._log_recommendation(task_id, error_type, result)
            return result

        # 3. 查询经验库
        matches = self.store.query(error_type, limit=3)
        if not matches:
            self.metrics.inc("recommend_default")
            result = self._default_result(error_type, "default")
            result["grayscale"] = True
            self._log_recommendation(task_id, error_type, result)
            return result

        # 4. 选最优（confidence 最高）
        best = matches[0]
        confidence = best.get("confidence", 0.0)
        min_conf = self.config.get("min_confidence", 0.60)

        if confidence < min_conf:
            self.metrics.inc("recommend_default")
            result = self._default_result(error_type, "default")
            result["grayscale"] = True
            self._log_recommendation(task_id, error_type, result)
            return result

        # 5. 推荐成功
        self.metrics.inc("recommend_hit")
        result = {
            "recommended_strategy": best["strategy"],
            "strategy_version": best.get("strategy_version", STRATEGY_VERSION),
            "source": "experience",
            "confidence": confidence,
            "grayscale": True,
        }
        self._log_recommendation(task_id, error_type, result)
        return result

    def save_success(self, record: dict) -> bool:
        """
        保存成功轨迹（幂等写入）

        Args:
            record: {
                "task_id": str,
                "error_type": str,
                "strategy": str,
                "confidence": float,
                "recovery_time": float,
                "strategy_version": str (optional, defaults to current)
            }

        Returns:
            True = 新写入, False = 幂等跳过
        """
        record.setdefault("strategy_version", STRATEGY_VERSION)
        written = self.store.save(record)
        if written:
            print(f"[LEARNER_V4] Saved: {record.get('error_type')} → {record.get('strategy')} (v={record.get('strategy_version')})")
        else:
            print(f"[LEARNER_V4] Idempotent skip: {record.get('error_type')} → {record.get('strategy')}")
        return written

    def track_outcome(self, task_id: str, strategy: str, source: str, success: bool):
        """
        追踪推荐后的实际结果（"推荐后失败"分桶）

        Args:
            task_id: 任务 ID
            strategy: 使用的策略
            source: "experience" | "default" | ...
            success: 实际执行是否成功
        """
        self.metrics.inc("regen_total")

        if success:
            self.metrics.inc("regen_success")
        else:
            self.metrics.inc("regen_failed")

        # 分桶：推荐策略 vs 默认策略的成功/失败
        if source == "experience":
            if success:
                self.metrics.inc("post_recommend_success")
            else:
                self.metrics.inc("post_recommend_failed")
        else:
            if success:
                self.metrics.inc("post_default_success")
            else:
                self.metrics.inc("post_default_failed")

        # 记录到日志
        outcome = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "strategy": strategy,
            "source": source,
            "success": success,
            "strategy_version": STRATEGY_VERSION,
        }
        with open(RECOMMENDATION_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(outcome, ensure_ascii=False) + "\n")

    def get_metrics(self) -> dict:
        """获取验收指标报告"""
        report = self.metrics.get_report()
        report["store_stats"] = self.store.stats()
        report["config"] = {
            "enable_recommendation": self.config.get("enable_recommendation"),
            "grayscale_ratio": self.config.get("grayscale_ratio"),
            "strategy_version": STRATEGY_VERSION,
        }
        return report

    def set_grayscale_ratio(self, ratio: float):
        """动态调整灰度比例（0.0 ~ 1.0）"""
        self.config["grayscale_ratio"] = max(0.0, min(1.0, ratio))
        _save_config(self.config)
        print(f"[LEARNER_V4] Grayscale ratio updated: {self.config['grayscale_ratio']:.0%}")

    def set_enabled(self, enabled: bool):
        """回滚开关"""
        self.config["enable_recommendation"] = enabled
        _save_config(self.config)
        print(f"[LEARNER_V4] Recommendation {'ENABLED' if enabled else 'DISABLED'}")

    # ── internal ──────────────────────────────────────────────────────────────

    def _default_result(self, error_type: str, source: str) -> dict:
        return {
            "recommended_strategy": "default_recovery",
            "strategy_version": STRATEGY_VERSION,
            "source": source,
            "confidence": 0.0,
            "grayscale": False,
        }

    def _log_recommendation(self, task_id: str, error_type: str, result: dict):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "error_type": error_type,
            **result,
        }
        with open(RECOMMENDATION_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 全局单例 ──────────────────────────────────────────────────────────────────
learner_v4 = ExperienceLearnerV4()


# ── CLI 测试 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Experience Learner v4.0 - Self Test ===\n")

    learner = ExperienceLearnerV4()

    # Test 1: 空库推荐
    print("[Test 1] Empty store recommendation")
    # 临时设灰度 100% 以确保测试命中
    learner.set_grayscale_ratio(1.0)
    rec = learner.recommend({"error_type": "timeout", "task_id": "test-001"})
    print(f"  Strategy: {rec['recommended_strategy']}")
    print(f"  Source: {rec['source']}")
    print(f"  Version: {rec['strategy_version']}")
    assert rec["source"] == "default", f"Expected default, got {rec['source']}"
    print("  OK\n")

    # Test 2: 保存成功轨迹
    print("[Test 2] Save success trajectory")
    saved = learner.save_success({
        "task_id": "test-001",
        "error_type": "timeout",
        "strategy": "increase_timeout_and_retry",
        "confidence": 0.95,
        "recovery_time": 12.5,
    })
    assert saved, "Should save new entry"
    print(f"  Saved: {saved}")

    # Test 2b: 幂等写入
    saved2 = learner.save_success({
        "task_id": "test-002",
        "error_type": "timeout",
        "strategy": "increase_timeout_and_retry",
        "confidence": 0.90,
        "recovery_time": 8.0,
    })
    assert not saved2, "Should be idempotent skip"
    print(f"  Idempotent skip: {not saved2}")
    print("  OK\n")

    # Test 3: 有经验后推荐
    print("[Test 3] Recommendation with experience")
    rec2 = learner.recommend({"error_type": "timeout", "task_id": "test-003"})
    print(f"  Strategy: {rec2['recommended_strategy']}")
    print(f"  Source: {rec2['source']}")
    print(f"  Confidence: {rec2['confidence']}")
    assert rec2["source"] == "experience", f"Expected experience, got {rec2['source']}"
    assert rec2["recommended_strategy"] == "increase_timeout_and_retry"
    print("  OK\n")

    # Test 4: 追踪结果
    print("[Test 4] Track outcome")
    learner.track_outcome("test-003", "increase_timeout_and_retry", "experience", True)
    learner.track_outcome("test-004", "default_recovery", "default", False)
    print("  OK\n")

    # Test 5: 回滚开关
    print("[Test 5] Kill switch")
    learner.set_enabled(False)
    rec3 = learner.recommend({"error_type": "timeout", "task_id": "test-005"})
    assert rec3["source"] == "disabled"
    print(f"  Source: {rec3['source']} (expected: disabled)")
    learner.set_enabled(True)
    print("  OK\n")

    # Test 6: 灰度门控
    print("[Test 6] Grayscale gate")
    learner.set_grayscale_ratio(0.0)  # 0% = 全部跳过
    rec4 = learner.recommend({"error_type": "timeout", "task_id": "test-006"})
    assert rec4["source"] == "grayscale_skip"
    print(f"  Source: {rec4['source']} (expected: grayscale_skip)")
    learner.set_grayscale_ratio(0.10)  # 恢复 10%
    print("  OK\n")

    # Metrics
    print("[Metrics]")
    metrics = learner.get_metrics()
    print(f"  recommend_hit_rate: {metrics['recommend_hit_rate']:.1%}")
    print(f"  regen_success_rate: {metrics['regen_success_rate']:.1%}")
    print(f"  manual_intervention_rate: {metrics['manual_intervention_rate']:.1%}")
    print(f"  post_recommend_failure_rate: {metrics['post_recommend_failure_rate']:.1%}")
    print(f"  store: {metrics['store_stats']}")
    print(f"  config: {metrics['config']}")

    print("\n=== All tests passed ===")
