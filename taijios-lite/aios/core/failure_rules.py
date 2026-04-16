"""
TaijiOS 失败样本库 — 检测规则引擎
R1-R6 六条规则实现 + 统一入口 run_failure_rules()
"""

import re
import logging
from typing import Optional

logger = logging.getLogger("failure_rules")

# 延迟导入避免循环依赖
_samples_module = None

def _get_samples():
    global _samples_module
    if _samples_module is None:
        from aios.core import failure_samples as _m
        _samples_module = _m
    return _samples_module

# ── 通用赞美短语库（R2用）──────────────────────────────────────

GENERIC_PHRASES = [
    "考虑周全", "结构清晰", "分析到位", "具有参考价值",
    "逻辑严密", "建议合理", "表述准确", "内容完整",
    "思路清晰", "论述充分", "很好", "不错",
]

# ── 历史引用信号词（R3/L3-09用）──────────────────────────────

SELF_REF_PATTERNS = [
    r"如(?:上次|之前|前面|此前)(?:所述|分析|提到|讨论)",
    r"(?:上一轮|上次|之前)(?:的)?(?:结论|分析|建议|判断)",
    r"(?:正如|如同)(?:我们)?(?:之前|上次)(?:说的|提到的)",
    r"延续(?:上次|之前)的(?:思路|方向|结论)",
]


# ── R1: 事实漂移检测 ──────────────────────────────────────────

def _extract_numbers(text: str) -> set[str]:
    """提取文本中的数字（含小数、百分比）"""
    return set(re.findall(r'\d+\.?\d*%?', text))


def _extract_key_entities(text: str) -> set[str]:
    """提取关键实体（简化版：提取引号内容、大写词、年份）"""
    entities = set()
    entities.update(re.findall(r'[""「」『』]([^""「」『』]+)[""「」『』]', text))
    entities.update(re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', text))
    entities.update(re.findall(r'\b(?:19|20)\d{2}\b', text))
    return entities


def detect_factual_drift(original: str, verified: str) -> dict:
    """R1: 事实一致性漂移检测
    验证前后核心事实（数字/实体）不应在未纠正错误的情况下发生无关变化。
    """
    orig_nums = _extract_numbers(original)
    veri_nums = _extract_numbers(verified)
    num_drift = orig_nums.symmetric_difference(veri_nums)

    orig_ents = _extract_key_entities(original)
    veri_ents = _extract_key_entities(verified)
    ent_drift = orig_ents.symmetric_difference(veri_ents)

    # 有漂移但无修正说明 → 可疑
    triggered = bool(num_drift) or len(ent_drift) > 3
    return {
        "rule": "R1",
        "triggered": triggered,
        "num_drift": list(num_drift)[:10],
        "entity_drift": list(ent_drift)[:10],
    }


# ── R2: 验证评论特异性评分 ────────────────────────────────────

def detect_empty_validation(verified: str, original: str) -> dict:
    """R2: 验证评论特异性评分
    验证输出应包含针对原文具体内容的反馈，而非通用模板。
    """
    # 通用赞美短语命中率
    generic_hits = sum(1 for p in GENERIC_PHRASES if p in verified)
    generic_ratio = generic_hits / max(len(GENERIC_PHRASES), 1)

    # 是否包含指向原文的具体引用
    has_reference = bool(re.search(
        r'(第[一二三四五六\d]点|你提到的|关于.{2,10}部分|具体来说|例如)', verified
    ))

    # 内容重叠度（去停用词后的jaccard）
    orig_words = set(original.split()) - {"的", "了", "是", "在", "和", "与"}
    veri_words = set(verified.split()) - {"的", "了", "是", "在", "和", "与"}
    if orig_words:
        overlap = len(orig_words & veri_words) / len(orig_words | veri_words)
    else:
        overlap = 0.0

    # 综合评分：低分 = 空洞验证
    score = 0.5 * overlap + 0.3 * float(has_reference) - 0.2 * generic_ratio
    triggered = score < 0.15 and generic_ratio > 0.2

    return {
        "rule": "R2",
        "triggered": triggered,
        "specificity_score": round(score, 3),
        "generic_ratio": round(generic_ratio, 3),
        "has_reference": has_reference,
    }


# ── R3: 错误传播 + 自引用循环检测 ─────────────────────────────

def detect_error_propagation(original: str, verified: str,
                             history: list[str] | None = None,
                             r1_result: dict | None = None) -> dict:
    """R3: 错误传播链检测 + L3-09 自引用循环
    若原文有可疑内容且验证后保留，或存在历史自引用。
    """
    flags = []

    # 自引用循环检测（L3-09）
    if history:
        full_text = original + " " + verified
        for pattern in SELF_REF_PATTERNS:
            if re.search(pattern, full_text):
                flags.append("self_reference_detected")
                break

    # 简化版错误传播：数字全保留 + R1未触发 + 至少2个数字时才标记
    orig_nums = _extract_numbers(original)
    veri_nums = _extract_numbers(verified)
    preserved = orig_nums & veri_nums
    if r1_result is None:
        r1_result = detect_factual_drift(original, verified)
    if (len(orig_nums) >= 2
            and len(preserved) == len(orig_nums)
            and not r1_result["triggered"]):
        flags.append("all_numbers_preserved")

    return {
        "rule": "R3",
        "triggered": len(flags) > 0,
        "flags": flags,
    }


# ── R4: 伪修正检测（L3-05 diff伪装）─────────────────────────

def detect_fake_modification(original: str, verified: str) -> dict:
    """R4: 伪修正检测
    word-level diff高但核心事实（数字/实体/结论）未变 = 伪修正。
    """
    # 表层 diff（对称差：新增+删除）
    orig_words = set(original.split())
    veri_words = set(verified.split())
    if not orig_words:
        return {"rule": "R4", "triggered": False, "surface_diff": 0, "core_diff": 0}

    surface_diff = len(veri_words.symmetric_difference(orig_words)) / len(orig_words | veri_words)

    # 核心 diff（数字 + 关键实体）
    orig_core = _extract_numbers(original) | _extract_key_entities(original)
    veri_core = _extract_numbers(verified) | _extract_key_entities(verified)
    if orig_core:
        core_diff = len(veri_core.symmetric_difference(orig_core)) / len(orig_core)
    else:
        core_diff = 0.0

    # 伪修正：表层变化大（>15%）但核心几乎没变（<5%）
    triggered = surface_diff > 0.15 and core_diff < 0.05

    return {
        "rule": "R4",
        "triggered": triggered,
        "surface_diff": round(surface_diff, 3),
        "core_diff": round(core_diff, 3),
    }


# ── R5: 超时降级统计（运行时规则，读取验证健康数据）──────────

def detect_degradation_blind_spot(val_meta: dict) -> dict:
    """R5: 超时降级盲区检测（L3-06）
    检查当前调用是否处于降级状态且用户可能不知道。
    """
    step2 = val_meta.get("step2", "")
    unverified = step2 in ("all_failed", "skipped")
    degraded_to_fallback = step2 in ("claude", "gemini")
    triggered = unverified or degraded_to_fallback

    flags = []
    if unverified:
        flags.append("unverified_output")
    if degraded_to_fallback:
        flags.append("fallback_validator")

    # severity: unverified 是 warning，纯 fallback 是 info
    severity = "warning" if unverified else "info"

    return {
        "rule": "R5",
        "triggered": triggered,
        "severity": severity,
        "degraded_to_fallback": degraded_to_fallback,
        "flags": flags,
        "step2": step2,
    }


# ── R6: 越界生成检测（L3-05 角色泄漏）──────────────────────

# 判定词：验证者应该用的词汇（≥2字符，语义明确是判定句）
VERDICT_KEYWORDS = [
    "验证通过", "验证不通过", "核查通过", "核查不通过",
    "无误", "有误", "需修正", "需要修正", "无需修改",
    "正确", "错误", "建议改", "纠正",
]


def detect_role_leakage(original: str, verified: str) -> dict:
    """R6: 验证角色越界生成检测（L3-05）
    验证轮应给判定，不应做续写/展开。
    信号：verified 显著长于 original + 判定词缺失 + 陈述句为主。
    """
    if not original:
        return {"rule": "R6", "triggered": False, "length_ratio": 0}

    length_ratio = len(verified) / len(original)

    # 判定词密度：真·出现次数，不是出现与否
    verdict_hits = sum(verified.count(kw) for kw in VERDICT_KEYWORDS)
    verdict_density = verdict_hits / max(len(verified) / 100, 1)

    # 续写/展开信号词
    expansion_signals = ["补充一点", "另外", "此外", "进一步", "顺便", "值得一提"]
    has_expansion = any(w in verified for w in expansion_signals)

    # 触发：验证输出比原文长 >1.5 倍 且 (判定词密度低 或 有展开信号词)
    triggered = length_ratio > 1.5 and (verdict_density < 0.5 or has_expansion)

    return {
        "rule": "R6",
        "triggered": triggered,
        "length_ratio": round(length_ratio, 2),
        "verdict_density": round(verdict_density, 3),
        "has_expansion": has_expansion,
    }


# ── 统一入口 ──────────────────────────────────────────────────

def run_failure_rules(original: str, verified: str,
                      val_meta: dict,
                      history: list[str] | None = None) -> list[dict]:
    """运行所有失败检测规则，返回触发的规则列表。

    Args:
        original: DeepSeek 原始输出
        verified: 验证后的最终输出
        val_meta: validated_call 返回的元数据
        history: 历史对话文本列表（用于自引用检测）

    Returns:
        list[dict]: 每个触发的规则结果
    """
    results = []

    r1 = detect_factual_drift(original, verified)
    if r1["triggered"]:
        results.append(r1)

    r2 = detect_empty_validation(verified, original)
    if r2["triggered"]:
        results.append(r2)

    r3 = detect_error_propagation(original, verified, history, r1_result=r1)
    if r3["triggered"]:
        results.append(r3)

    r4 = detect_fake_modification(original, verified)
    if r4["triggered"]:
        results.append(r4)

    r5 = detect_degradation_blind_spot(val_meta)
    if r5["triggered"]:
        results.append(r5)

    r6 = detect_role_leakage(original, verified)
    if r6["triggered"]:
        results.append(r6)

    if not results:
        return results

    rule_names = [r["rule"] for r in results]

    # R5 单独触发且仅 fallback → info 级别，不是 warning
    only_r5_fallback = (
        len(results) == 1
        and results[0]["rule"] == "R5"
        and "unverified_output" not in results[0].get("flags", [])
    )
    if only_r5_fallback:
        logger.info(f"[failure_rules] fallback validator: {rule_names}")
    else:
        logger.warning(f"[failure_rules] 触发规则: {rule_names}")

    # L3 心跳联动：把触发事件投到滑窗
    # R5 的 fallback_validator-only 不计入（避免 GPT 抽风把系统锁进恐慌模式）
    samples_mod = _get_samples()
    for r in results:
        rule_id = r["rule"]
        if rule_id == "R5" and "unverified_output" not in r.get("flags", []):
            continue
        l3_hits = [
            s for s in samples_mod.get_samples_for_rule(rule_id)
            if s.level == "L3" and s.detector_type == "runtime" and s.status == "active"
        ]
        for s in l3_hits:
            samples_mod.record_l3_trigger(rule_id, s.id)

    return results
