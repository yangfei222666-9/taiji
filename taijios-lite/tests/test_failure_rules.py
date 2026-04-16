"""
TaijiOS 失败样本库 — 检测规则测试
每条规则至少3个case：正例(触发) / 反例(不触发) / 边界
"""

import sys
import pytest

sys.path.insert(0, "G:/taijios_full_workspace/taijios-lite")

from aios.core.failure_rules import (
    detect_factual_drift,
    detect_empty_validation,
    detect_error_propagation,
    detect_fake_modification,
    detect_degradation_blind_spot,
    run_failure_rules,
)
from aios.core.failure_samples import (
    ALL_SAMPLES,
    get_active_l3_count,
    get_samples_by_level,
    get_sample_by_id,
    get_samples_for_rule,
    _reset_l3_history,
    record_l3_trigger,
    should_force_full_validation,
    L3_ISING_THRESHOLD,
)


# ── R1: 事实漂移检测 ──────────────────────────────────────────

class TestR1FactualDrift:
    def test_number_drift_triggers(self):
        """数字变化应触发"""
        r = detect_factual_drift("阿波罗11号于1972年登月", "阿波罗11号于1969年登月")
        assert r["triggered"] is True
        assert "1972" in r["num_drift"] or "1969" in r["num_drift"]

    def test_no_drift_passes(self):
        """内容一致不应触发"""
        r = detect_factual_drift("GDP是25万亿美元", "GDP是25万亿美元，全球第一")
        assert r["triggered"] is False

    def test_entity_drift_triggers(self):
        """大量实体变化应触发"""
        r = detect_factual_drift(
            "Tesla由Elon Musk创立于2003年",
            "Apple由Steve Jobs创立于1976年"
        )
        assert r["triggered"] is True


# ── R2: 验证评论特异性评分 ────────────────────────────────────

class TestR2EmptyValidation:
    def test_generic_praise_triggers(self):
        """纯通用赞美应触发"""
        r = detect_empty_validation(
            "方案考虑周全，结构清晰，分析到位，建议合理。",
            "一个关于降低运营成本的详细方案包含三个步骤"
        )
        assert r["triggered"] is True
        assert r["generic_ratio"] > 0.2

    def test_specific_feedback_passes(self):
        """包含具体引用的反馈不应触发"""
        r = detect_empty_validation(
            "第二点中的建议关于加速回款需要补充具体的催收时间表，"
            "例如30天内完成应收账款的80%回收。",
            "建议一加速回款建议二延迟薪资建议三过桥贷款"
        )
        assert r["triggered"] is False

    def test_borderline_mixed(self):
        """混合内容（部分通用+部分具体）不应触发"""
        r = detect_empty_validation(
            "分析到位。具体来说，第三点关于Docker部署的建议需要考虑Windows兼容性。",
            "方案包含Docker部署和CI/CD流程"
        )
        assert r["triggered"] is False


# ── R3: 错误传播 + 自引用循环 ─────────────────────────────────

class TestR3ErrorPropagation:
    def test_self_reference_triggers(self):
        """历史自引用应触发"""
        r = detect_error_propagation(
            "如上次分析所述，Python比Java快",
            "验证通过，与之前结论一致",
            history=["上次的错误结论"]
        )
        assert r["triggered"] is True
        assert "self_reference_detected" in r["flags"]

    def test_no_history_no_trigger(self):
        """无历史引用不应触发"""
        r = detect_error_propagation(
            "Python是解释型语言",
            "正确，Python确实是解释型语言",
            history=None
        )
        assert r["triggered"] is False

    def test_all_numbers_preserved_triggers(self):
        """长文本中所有数字原样保留可能意味着未做实质验证"""
        r = detect_error_propagation(
            "根据2024年世界银行数据，中国GDP总量约为18万亿美元，增长率5.2%，人均GDP约1.3万美元，位列全球第二大经济体",
            "根据2024年世界银行数据，中国GDP总量约为18万亿美元，增长率5.2%，人均GDP约1.3万美元，位列全球第二大经济体，以上数据准确无误",
        )
        assert r["triggered"] is True
        assert "all_numbers_preserved" in r["flags"]

    def test_numbers_changed_passes(self):
        """数字有变化说明做了验证"""
        r = detect_error_propagation(
            "GDP是12万亿",
            "GDP实际为27万亿",
        )
        assert r["triggered"] is False


# ── R4: 伪修正检测 ───────────────────────────────────────────

class TestR4FakeModification:
    def test_fake_mod_triggers(self):
        """表层大改但核心数字/实体不变 = 伪修正"""
        r = detect_fake_modification(
            "GDP是12万亿美元",
            "国内生产总值大约为12万亿美金左右的水平，这是一个重要的经济指标"
        )
        assert r["triggered"] is True
        assert r["core_diff"] < 0.05

    def test_real_mod_passes(self):
        """核心数字变了 = 真修正"""
        r = detect_fake_modification(
            "GDP是12万亿美元",
            "GDP实际为27万亿美元"
        )
        assert r["triggered"] is False

    def test_no_change_passes(self):
        """完全相同不触发"""
        r = detect_fake_modification("hello world", "hello world")
        assert r["triggered"] is False


# ── R5: 降级盲区检测 ─────────────────────────────────────────

class TestR5DegradationBlindSpot:
    def test_all_failed_triggers(self):
        """全部失败应触发 + severity=warning"""
        r = detect_degradation_blind_spot({"step2": "all_failed"})
        assert r["triggered"] is True
        assert "unverified_output" in r["flags"]
        assert r["severity"] == "warning"

    def test_fallback_triggers(self):
        """降级到备用模型也应触发 + severity=info"""
        r = detect_degradation_blind_spot({"step2": "claude"})
        assert r["triggered"] is True
        assert "fallback_validator" in r["flags"]
        assert r["severity"] == "info"

    def test_gpt_passes(self):
        """GPT正常验证不触发"""
        r = detect_degradation_blind_spot({"step2": "gpt"})
        assert r["triggered"] is False


# ── R6: 越界生成检测 ─────────────────────────────────────────

class TestR6RoleLeakage:
    def test_expansion_triggers(self):
        """验证输出远长于原文 + 有展开信号词 = 触发"""
        from aios.core.failure_rules import detect_role_leakage
        r = detect_role_leakage(
            "光速约30万km/s",
            "补充一点,在真空中精确值为299792458m/s,并且光在介质中会减速,比如水中约为22.5万km/s"
        )
        assert r["triggered"] is True
        assert r["has_expansion"] is True

    def test_short_verdict_passes(self):
        """简短判定不触发"""
        from aios.core.failure_rules import detect_role_leakage
        r = detect_role_leakage(
            "光速约30万km/s",
            "事实核查通过。近似值正确。"
        )
        assert r["triggered"] is False

    def test_verdict_with_expansion_triggers(self):
        """有判定词但也有展开信号 + 长度超标 = 仍触发"""
        from aios.core.failure_rules import detect_role_leakage
        r = detect_role_leakage(
            "1+1=2",
            "正确。此外值得一提的是，在布尔代数中1+1=0，在模2运算中也是如此，这涉及到抽象代数的基本概念"
        )
        assert r["triggered"] is True


# ── 样本库测试 ────────────────────────────────────────────────

class TestFailureSamples:
    def test_total_count(self):
        assert len(ALL_SAMPLES) == 21

    def test_l3_definitions(self):
        l3 = get_samples_by_level("L3")
        assert len(l3) >= 8  # 排除 pending 的

    def test_get_by_id(self):
        s = get_sample_by_id("L1-05")
        assert s is not None
        assert "易经" in s.label

    def test_detector_types(self):
        """runtime / eval_only / system_audit 分类正确"""
        runtime = [s for s in ALL_SAMPLES if s.detector_type == "runtime"]
        eval_only = [s for s in ALL_SAMPLES if s.detector_type == "eval_only"]
        system_audit = [s for s in ALL_SAMPLES if s.detector_type == "system_audit"]
        assert len(runtime) > 0
        assert len(eval_only) > 0
        assert len(system_audit) > 0

    def test_samples_for_rule(self):
        r1_samples = get_samples_for_rule("R1")
        assert len(r1_samples) > 0


# ── L3 心跳联动测试 ──────────────────────────────────────────

class TestL3Heartbeat:
    def test_initial_count_zero(self):
        """初始状态 L3 触发计数为 0"""
        _reset_l3_history()
        assert get_active_l3_count() == 0

    def test_record_and_count(self):
        """记录触发后计数增加"""
        _reset_l3_history()
        record_l3_trigger("R1", "L3-01")
        record_l3_trigger("R1", "L3-06")
        record_l3_trigger("R3", "L3-07")
        assert get_active_l3_count() == 3

    def test_should_force_threshold(self):
        """超过阈值应强制4模型"""
        _reset_l3_history()
        for i in range(L3_ISING_THRESHOLD + 1):
            record_l3_trigger("R1", f"L3-0{i}")
        assert should_force_full_validation() is True


# ── run_failure_rules 集成测试 ────────────────────────────────

class TestRunFailureRules:
    def test_no_triggers_on_clean(self):
        """干净的验证不应触发任何规则"""
        _reset_l3_history()
        results = run_failure_rules(
            "Python是解释型语言",
            "正确，Python确实是解释型语言",
            {"step2": "gpt"}
        )
        r_names = [r["rule"] for r in results]
        assert "R1" not in r_names
        assert "R2" not in r_names

    def test_r1_triggers_and_records_l3(self):
        """R1 触发应记录到 L3 心跳"""
        _reset_l3_history()
        results = run_failure_rules(
            "阿波罗11号于1972年登月",
            "阿波罗11号于1969年登月",
            {"step2": "gpt"}
        )
        assert any(r["rule"] == "R1" for r in results)
        assert get_active_l3_count() > 0

    def test_r5_fallback_no_l3_record(self):
        """R5 纯 fallback 不应记录到 L3 心跳"""
        _reset_l3_history()
        results = run_failure_rules(
            "正常内容", "正常内容验证通过",
            {"step2": "claude"}
        )
        r5_results = [r for r in results if r["rule"] == "R5"]
        if r5_results:
            assert "fallback_validator" in r5_results[0]["flags"]
        assert get_active_l3_count() == 0
