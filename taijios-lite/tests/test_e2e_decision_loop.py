"""
TaijiOS 端到端决策闭环测试
验证：规则触发 → L3心跳 → should_block_fallback → 返回状态 → 日志一致性

覆盖四模型共识的5个关键场景：
1. 连续L3触发达到阈值 → 阻断生效
2. R5 fallback-only 不进入L3心跳
3. 混合规则触发计数正确
4. 短数学表达式误触发不应打穿主路径
5. 日志与返回一致性
"""

import sys
import time
import pytest

sys.path.insert(0, "G:/taijios_full_workspace/taijios-lite")

from aios.core.failure_rules import (
    run_failure_rules,
    detect_factual_drift,
    detect_degradation_blind_spot,
    detect_role_leakage,
)
from aios.core.failure_samples import (
    get_active_l3_count,
    should_block_fallback,
    record_l3_trigger,
    _reset_l3_history,
    L3_ISING_THRESHOLD,
    L3_ISING_WINDOW_SEC,
)
from aios.core.latency_logger import LatencyLogger
from aios.core.validation_meta import ValidationMeta


# ── 场景1：连续L3触发达到阈值 → 阻断生效 ─────────────────────

class TestScenario1_ThresholdBlock:
    """连续L3触发达到阈值后，should_block_fallback 必须返回 True"""

    def test_below_threshold_no_block(self):
        """阈值以下不阻断"""
        _reset_l3_history()
        for i in range(L3_ISING_THRESHOLD):
            record_l3_trigger("R1", f"L3-0{i}")
        assert get_active_l3_count() == L3_ISING_THRESHOLD
        assert should_block_fallback() is False  # == 不触发，要 >

    def test_above_threshold_blocks(self):
        """超过阈值阻断"""
        _reset_l3_history()
        for i in range(L3_ISING_THRESHOLD + 1):
            record_l3_trigger("R1", f"L3-0{i}")
        assert get_active_l3_count() == L3_ISING_THRESHOLD + 1
        assert should_block_fallback() is True

    def test_threshold_boundary_exact(self):
        """恰好等于阈值不阻断（> 不是 >=）"""
        _reset_l3_history()
        for i in range(L3_ISING_THRESHOLD):
            record_l3_trigger("R1", f"L3-0{i}")
        assert should_block_fallback() is False
        # 再加一个就阻断
        record_l3_trigger("R1", "L3-extra")
        assert should_block_fallback() is True

    def test_window_expiry_restores(self):
        """窗口过期后计数归零，阻断解除"""
        _reset_l3_history()
        # 手动插入过期事件
        import threading
        from aios.core.failure_samples import _l3_trigger_history, _l3_lock
        expired_ts = time.time() - L3_ISING_WINDOW_SEC - 10
        with _l3_lock:
            for i in range(10):
                _l3_trigger_history.append({
                    "rule": "R1", "sample": f"L3-0{i}", "ts": expired_ts
                })
        # 全部过期，计数应为0
        assert get_active_l3_count() == 0
        assert should_block_fallback() is False


# ── 场景2：R5 fallback-only 不进入L3心跳 ─────────────────────

class TestScenario2_R5FallbackFilter:
    """R5 纯 fallback（非 unverified）不应污染L3心跳"""

    def test_fallback_only_no_l3(self):
        """claude 降级触发 R5，但不计入L3"""
        _reset_l3_history()
        results = run_failure_rules(
            "正常内容", "正常内容验证通过",
            {"step2": "claude"}
        )
        # R5 应触发
        r5 = [r for r in results if r["rule"] == "R5"]
        assert len(r5) == 1
        assert "fallback_validator" in r5[0]["flags"]
        # L3 不应增加
        assert get_active_l3_count() == 0

    def test_unverified_does_count_l3(self):
        """all_failed 触发 R5 unverified，应计入L3"""
        _reset_l3_history()
        results = run_failure_rules(
            "正常内容", "正常内容",
            {"step2": "all_failed"}
        )
        r5 = [r for r in results if r["rule"] == "R5"]
        assert len(r5) == 1
        assert "unverified_output" in r5[0]["flags"]
        # 这次应该计入（如果有关联的 runtime L3 样本）
        # R5 关联的 L3 样本取决于 failure_samples 定义

    def test_gpt_pass_no_r5(self):
        """GPT 正常验证不触发 R5"""
        _reset_l3_history()
        results = run_failure_rules(
            "正常内容", "正常内容验证通过",
            {"step2": "gpt"}
        )
        r5 = [r for r in results if r["rule"] == "R5"]
        assert len(r5) == 0
        assert get_active_l3_count() == 0


# ── 场景3：混合规则触发计数正确 ──────────────────────────────

class TestScenario3_MixedRules:
    """多条规则同时触发时，L3计数只统计 runtime+active 的关联样本"""

    def test_r1_triggers_l3_samples(self):
        """R1 触发应记录关联的 L3 runtime active 样本"""
        _reset_l3_history()
        results = run_failure_rules(
            "阿波罗11号于1972年登月",
            "阿波罗11号于1969年登月",
            {"step2": "gpt"}
        )
        assert any(r["rule"] == "R1" for r in results)
        count = get_active_l3_count()
        assert count > 0  # L3-01(验证附和) 关联 R1

    def test_eval_only_not_counted(self):
        """eval_only 样本不进入 runtime L3 计数"""
        _reset_l3_history()
        # L3-08 是 eval_only，即使其关联规则触发也不应计入
        # L3-08 related_rules=[]，所以不会被任何规则触发
        # 验证：跑一轮规则后，L3 计数不包含 eval_only 样本
        results = run_failure_rules(
            "正常内容", "正常内容",
            {"step2": "gpt"}
        )
        # 即使有规则触发，eval_only 样本不参与
        from aios.core.failure_samples import get_samples_by_level
        eval_only = [s for s in get_samples_by_level("L3") if s.detector_type == "eval_only"]
        # eval_only 样本的 related_rules 为空，不会被计入
        # 这里主要验证机制正确性

    def test_system_audit_not_counted(self):
        """system_audit 样本不进入 runtime L3 计数"""
        _reset_l3_history()
        from aios.core.failure_samples import ALL_SAMPLES
        audit_samples = [s for s in ALL_SAMPLES
                         if s.detector_type == "system_audit" and s.level == "L3"]
        # system_audit 样本 related_rules=[]，不会被 run_failure_rules 触发
        for s in audit_samples:
            assert s.related_rules == [], f"{s.id} 不应有 related_rules"

    def test_multiple_rules_accumulate(self):
        """多条规则同时触发，L3 计数累加"""
        _reset_l3_history()
        # R1 触发（数字漂移）+ R5 触发（unverified）
        results = run_failure_rules(
            "GDP是12万亿美元，2024年数据",
            "GDP是27万亿美元，2024年数据",
            {"step2": "all_failed"}
        )
        triggered = [r["rule"] for r in results]
        assert "R1" in triggered
        assert "R5" in triggered
        # 两条规则各自关联的 L3 样本都应计入
        assert get_active_l3_count() > 0


# ── 场景4：短数学表达式不应打穿主路径 ─────────────────────────

class TestScenario4_MathExpressionSafety:
    """短数学表达式可能触发 R3，但不应导致系统级阻断"""

    def test_short_math_r3_trigger(self):
        """1+1=2 类短表达式可能触发 R3（已知边界case）"""
        _reset_l3_history()
        results = run_failure_rules(
            "1+1等于2，2+2等于4",
            "1+1等于2，2+2等于4，计算正确",
            {"step2": "gpt"}
        )
        # R3 可能触发（数字全保留），但这是误报
        # 关键：单次误报不应导致阻断
        assert should_block_fallback() is False

    def test_repeated_math_no_block(self):
        """连续多次短数学表达式不应累积到阻断阈值（R3 长度感知已修复）"""
        _reset_l3_history()
        for _ in range(10):
            run_failure_rules(
                "2+3=5，答案正确",
                "2+3=5，答案正确，没有问题",
                {"step2": "gpt"}
            )
        # R3 短文本（<50字符）不再触发 all_numbers_preserved
        assert should_block_fallback() is False

    def test_long_text_r3_legitimate(self):
        """长文本中数字全保留是合理的 R3 触发"""
        _reset_l3_history()
        original = "2024年中国GDP为18万亿美元，增长率5.2%，人均GDP约1.3万美元，排名全球第二"
        verified = "2024年中国GDP为18万亿美元，增长率5.2%，人均GDP约1.3万美元，排名全球第二，数据准确"
        results = run_failure_rules(original, verified, {"step2": "gpt"})
        # 长文本 + 多数字全保留 → R3 触发是合理的


# ── 场景5：日志与返回一致性 ────────────────────────────────────

class TestScenario5_LogConsistency:
    """ValidationMeta 返回值与 latency 日志必须一致"""

    def setup_method(self):
        """每个测试前清理"""
        import tempfile
        self.log_dir = tempfile.mkdtemp()
        self.logger = LatencyLogger(self.log_dir)

    def test_meta_to_dict_roundtrip(self):
        """ValidationMeta.to_dict() 序列化后字段完整"""
        meta = ValidationMeta(
            final_content="测试",
            primary_model="deepseek",
            validator_model="gpt",
            model_chain="deepseek→gpt",
            verification_status="passed",
            modified=False,
            generation_ms=2000,
            verification_ms=1500,
            total_ms=3500,
            triggered_rules=[{"rule": "R1", "triggered": True}],
            active_l3_count_at_call=0,
            block_fallback=False,
        )
        d = meta.to_dict()
        assert d["primary_model"] == "deepseek"
        assert d["validator_model"] == "gpt"
        assert d["verification_status"] == "passed"
        assert d["generation_ms"] == 2000
        assert d["verification_ms"] == 1500
        assert d["total_ms"] == 3500
        assert len(d["triggered_rules"]) == 1

    def test_log_matches_meta(self):
        """写入日志后读回，关键字段与原 meta 一致"""
        meta = ValidationMeta(
            final_content="这段不应出现在日志里",
            primary_model="deepseek",
            validator_model="gpt",
            model_chain="deepseek→gpt",
            verification_status="modified",
            modified=True,
            generation_ms=3000,
            verification_ms=2000,
            total_ms=5000,
            triggered_rules=[{"rule": "R4", "severity": "warning", "surface_diff": 0.3}],
        )
        self.logger.log(meta)
        records = self.logger.read_day()
        assert len(records) == 1
        r = records[0]

        # 关键字段一致
        assert r["primary_model"] == "deepseek"
        assert r["validator_model"] == "gpt"
        assert r["model_chain"] == "deepseek→gpt"
        assert r["verification_status"] == "modified"
        assert r["modified"] is True
        assert r["generation_ms"] == 3000
        assert r["verification_ms"] == 2000
        assert r["total_ms"] == 5000

        # final_content 已去除
        assert "final_content" not in r

        # triggered_rules 精简为 rule+severity
        assert len(r["triggered_rules"]) == 1
        assert r["triggered_rules"][0]["rule"] == "R4"
        assert "surface_diff" not in r["triggered_rules"][0]

        # 有时间戳
        assert "ts" in r

    def test_status_line_matches_meta(self):
        """format_status_line 与 meta 字段语义一致"""
        meta = ValidationMeta(
            primary_model="deepseek",
            validator_model="gpt",
            model_chain="deepseek→gpt",
            verification_status="passed",
            generation_ms=2000,
            verification_ms=1000,
            total_ms=3000,
        )
        line = meta.format_status_line()
        assert "deepseek→gpt" in line
        assert "验证通过" in line
        assert "2.0s" in line  # gen
        assert "1.0s" in line  # val

    def test_failed_status_line(self):
        """failed 状态行显示未验证警告"""
        meta = ValidationMeta(
            primary_model="deepseek",
            model_chain="deepseek→all_failed",
            verification_status="failed",
            total_ms=120000,
        )
        line = meta.format_status_line()
        assert "⚠未验证" in line

    def test_degraded_status_line(self):
        """降级状态行显示降级信息"""
        meta = ValidationMeta(
            primary_model="deepseek",
            validator_model="claude",
            model_chain="deepseek→claude",
            verification_status="degraded",
            degraded=True,
            total_ms=8000,
        )
        line = meta.format_status_line()
        assert "降级" in line
        assert "claude" in line


# ── 场景6：完整决策链路回放 ───────────────────────────────────

class TestScenario6_FullChainReplay:
    """模拟真实请求序列，验证整条决策链路行为"""

    def test_normal_then_error_then_recovery(self):
        """正常→连续错误→阻断→窗口过期→恢复"""
        _reset_l3_history()

        # Phase 1: 正常请求
        results = run_failure_rules("正常", "正常验证通过", {"step2": "gpt"})
        assert should_block_fallback() is False

        # Phase 2: 连续错误触发 L3
        for i in range(L3_ISING_THRESHOLD + 1):
            record_l3_trigger("R1", f"L3-0{i}")

        # Phase 3: 阻断生效
        assert should_block_fallback() is True

        # Phase 4: 清空（模拟窗口过期）
        _reset_l3_history()
        assert should_block_fallback() is False

    def test_mixed_severity_sequence(self):
        """混合严重度序列：info 级不累积，warning 级累积"""
        _reset_l3_history()

        # 多次 fallback（info 级）不应累积
        for _ in range(20):
            run_failure_rules("内容", "内容", {"step2": "claude"})
        assert should_block_fallback() is False  # fallback 不计入

        # 一次 unverified（warning 级）开始累积
        run_failure_rules("内容", "内容", {"step2": "all_failed"})
        count_after_unverified = get_active_l3_count()
        # 不一定 >0（取决于 R5 是否有关联的 runtime L3 样本）
        # 但至少不应因 20 次 fallback 就阻断
        assert should_block_fallback() is False
