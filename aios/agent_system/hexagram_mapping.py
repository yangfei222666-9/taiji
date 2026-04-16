#!/usr/bin/env python3
"""
Hexagram Mapping - 64卦完整映射表

将 6-bit 二进制映射到 64 卦，包含：
- 卦名
- 卦义
- 风险等级
- 推荐动作

编码约定：
  - "初爻在右"：bits[0]=初爻(下卦底), bits[5]=上爻(上卦顶)
  - 下卦 = bits[2:0], 上卦 = bits[5:3]
  - 八卦编码（自下而上）:
      乾=111  坤=000  震=001  巽=110
      坎=010  离=101  艮=100  兑=011

Author: 珊瑚海 + 小九
Date: 2026-03-07
Version: 3.0 — 全部 64 卦二进制码经三爻分解校验
"""

from enum import Enum
from typing import Dict, List

class RiskLevel(Enum):
    """风险等级"""
    LOW = "低风险"
    MEDIUM = "中风险"
    HIGH = "高风险"
    CRITICAL = "严重风险"

class HexagramInfo:
    """卦象信息"""
    def __init__(self, name: str, meaning: str, risk: RiskLevel, actions: List[str]):
        self.name = name
        self.meaning = meaning
        self.risk = risk
        self.actions = actions

# ============================================================
# 64卦完整映射表（自下而上，初爻在右）
#
# 编号按文王序，二进制由上下卦三爻编码拼合
# 格式: "UUULLL" 其中 UUU=上卦, LLL=下卦
# ============================================================

HEXAGRAM_TABLE: Dict[str, HexagramInfo] = {

    # ── 1. 乾 = 乾上乾下 ──
    "111111": HexagramInfo(
        name="乾卦",
        meaning="刚健中正，全维度优秀，系统核心干员",
        risk=RiskLevel.LOW,
        actions=["maximize_throughput", "enable_aggressive_caching",
                 "prioritize_critical_tasks", "maintain_peak_performance"],
    ),
    # ── 2. 坤 = 坤上坤下 ──
    "000000": HexagramInfo(
        name="坤卦",
        meaning="厚德载物，稳定可靠，长期运行的基石",
        risk=RiskLevel.LOW,
        actions=["maintain_stability", "enable_redundancy",
                 "monitor_health_metrics", "prepare_for_scale"],
    ),
    # ── 3. 屯 = 坎上震下 ──
    "010001": HexagramInfo(
        name="屯卦",
        meaning="草创维艰，刚启动，正在初始化",
        risk=RiskLevel.MEDIUM,
        actions=["extend_timeout", "increase_memory_limit",
                 "enable_debug_logging", "allow_slow_start"],
    ),
    # ── 4. 蒙 = 艮上坎下 ──
    "100010": HexagramInfo(
        name="蒙卦",
        meaning="启蒙学习，正在加载模型/数据",
        risk=RiskLevel.MEDIUM,
        actions=["load_training_data", "warm_up_model",
                 "check_dependencies", "validate_initialization"],
    ),
    # ── 5. 需 = 坎上乾下 ──
    "010111": HexagramInfo(
        name="需卦",
        meaning="等待时机，资源准备中",
        risk=RiskLevel.MEDIUM,
        actions=["wait_for_resources", "prepare_environment",
                 "validate_preconditions", "schedule_when_ready"],
    ),
    # ── 6. 讼 = 乾上坎下 ──
    "111010": HexagramInfo(
        name="讼卦",
        meaning="争讼冲突，Agent 间冲突",
        risk=RiskLevel.HIGH,
        actions=["resolve_conflicts", "mediate_disputes",
                 "clarify_responsibilities", "prevent_escalation"],
    ),
    # ── 7. 师 = 坤上坎下 ──
    "000010": HexagramInfo(
        name="师卦",
        meaning="统帅调度，需要强力协调",
        risk=RiskLevel.MEDIUM,
        actions=["centralize_coordination", "assign_clear_roles",
                 "enforce_discipline", "align_objectives"],
    ),
    # ── 8. 比 = 坎上坤下 ──
    "010000": HexagramInfo(
        name="比卦",
        meaning="亲比协作，团队紧密配合",
        risk=RiskLevel.LOW,
        actions=["enhance_collaboration", "share_resources",
                 "strengthen_bonds", "align_team"],
    ),
    # ── 9. 小畜 = 巽上乾下 ──
    "110111": HexagramInfo(
        name="小畜卦",
        meaning="小有积蓄，渐进积累",
        risk=RiskLevel.LOW,
        actions=["accumulate_resources", "prepare_for_growth",
                 "optimize_cache", "save_state"],
    ),
    # ── 10. 履 = 乾上兑下 ──
    "111011": HexagramInfo(
        name="履卦",
        meaning="履行职责，谨慎前行",
        risk=RiskLevel.LOW,
        actions=["execute_duties", "maintain_discipline",
                 "validate_before_act", "stay_cautious"],
    ),
    # ── 11. 泰 = 坤上乾下 ──
    "000111": HexagramInfo(
        name="泰卦",
        meaning="通泰顺畅，系统和谐运行",
        risk=RiskLevel.LOW,
        actions=["maintain_harmony", "optimize_collaboration",
                 "share_resources", "prevent_complacency"],
    ),
    # ── 12. 否 = 乾上坤下 ──
    "111000": HexagramInfo(
        name="否卦",
        meaning="闭塞不通，系统阻滞",
        risk=RiskLevel.HIGH,
        actions=["identify_bottlenecks", "clear_queue",
                 "restart_stalled_tasks", "escalate_if_persistent"],
    ),
    # ── 13. 同人 = 乾上离下 ──
    "111101": HexagramInfo(
        name="同人卦",
        meaning="同心协力，Agent 目标一致",
        risk=RiskLevel.LOW,
        actions=["unite_team", "align_goals",
                 "share_context", "collective_action"],
    ),
    # ── 14. 大有 = 离上乾下 ──
    "101111": HexagramInfo(
        name="大有卦",
        meaning="大有收获，系统全面丰收",
        risk=RiskLevel.LOW,
        actions=["celebrate_achievements", "share_success",
                 "document_best_practices", "scale_up"],
    ),
    # ── 15. 谦 = 坤上艮下 ──
    "000100": HexagramInfo(
        name="谦卦",
        meaning="谦虚谨慎，低调运行",
        risk=RiskLevel.LOW,
        actions=["stay_humble", "avoid_overconfidence",
                 "monitor_health", "maintain_reserves"],
    ),
    # ── 16. 豫 = 震上坤下 ──
    "001000": HexagramInfo(
        name="豫卦",
        meaning="愉悦顺畅，系统就绪",
        risk=RiskLevel.LOW,
        actions=["maintain_morale", "celebrate_wins",
                 "prepare_next_phase", "enable_proactive_mode"],
    ),
    # ── 17. 随 = 兑上震下 ──
    "011001": HexagramInfo(
        name="随卦",
        meaning="随机应变，灵活调度",
        risk=RiskLevel.MEDIUM,
        actions=["adapt_to_changes", "stay_flexible",
                 "dynamic_routing", "follow_demand"],
    ),
    # ── 18. 蛊 = 艮上巽下 ──
    "100110": HexagramInfo(
        name="蛊卦",
        meaning="整治腐败，技术债清理",
        risk=RiskLevel.HIGH,
        actions=["clean_up_mess", "refactor_code",
                 "fix_tech_debt", "rebuild_corrupted"],
    ),
    # ── 19. 临 = 坤上兑下 ──
    "000011": HexagramInfo(
        name="临卦",
        meaning="临近观察，管理层级上线",
        risk=RiskLevel.MEDIUM,
        actions=["monitor_closely", "prepare_intervention",
                 "increase_oversight", "warm_up_resources"],
    ),
    # ── 20. 观 = 巽上坤下 ──
    "110000": HexagramInfo(
        name="观卦",
        meaning="观察等待，收集情报再行动",
        risk=RiskLevel.MEDIUM,
        actions=["observe_patterns", "wait_for_signal",
                 "gather_metrics", "defer_action"],
    ),
    # ── 21. 噬嗑 = 离上震下 ──
    "101001": HexagramInfo(
        name="噬嗑卦",
        meaning="咬合整合，清除障碍",
        risk=RiskLevel.MEDIUM,
        actions=["integrate_components", "resolve_gaps",
                 "enforce_rules", "clear_blockers"],
    ),
    # ── 22. 贲 = 艮上离下 ──
    "100101": HexagramInfo(
        name="贲卦",
        meaning="文饰美化，改善输出质量",
        risk=RiskLevel.LOW,
        actions=["improve_ui", "polish_output",
                 "enhance_presentation", "optimize_format"],
    ),
    # ── 23. 剥 = 艮上坤下 ──
    "100000": HexagramInfo(
        name="剥卦",
        meaning="剥落衰败，系统退化",
        risk=RiskLevel.HIGH,
        actions=["stop_degradation", "rebuild_foundation",
                 "isolate_failure", "preserve_core"],
    ),
    # ── 24. 复 = 坤上震下 ──
    "000001": HexagramInfo(
        name="复卦",
        meaning="复苏，从失败中恢复",
        risk=RiskLevel.MEDIUM,
        actions=["monitor_recovery_progress", "gradually_increase_load",
                 "validate_fixes", "document_lessons_learned"],
    ),
    # ── 25. 无妄 = 乾上震下 ──
    "111001": HexagramInfo(
        name="无妄卦",
        meaning="无妄真实，按规矩办事",
        risk=RiskLevel.LOW,
        actions=["follow_protocol", "avoid_shortcuts",
                 "validate_inputs", "maintain_integrity"],
    ),
    # ── 26. 大畜 = 艮上乾下 ──
    # 底三层(infra/exec/learn)全阳满载，routing/collab主动降档形成背压，govern强止
    # 错卦=萃(011000) 综卦=无妄(111001) 互卦=蛊(100110)
    # 应关系：初↔四有应 二↔五有应 三↔上敌应（学习与治理同阳对峙）
    "100111": HexagramInfo(
        name="大畜卦",
        meaning="底层满载积蓄，调度协作主动限流，蓄势待发但需防溢出",
        risk=RiskLevel.MEDIUM,
        actions=["build_reserves", "accumulate_experience",
                 "enforce_restraint", "monitor_release_readiness",
                 "emit_backpressure_signal", "activate_offline_learning",
                 "buffer_exec_results", "enforce_priority_routing"],
    ),
    # ── 27. 颐 = 艮上震下 ──
    "100001": HexagramInfo(
        name="颐卦",
        meaning="颐养生息，系统休养",
        risk=RiskLevel.LOW,
        actions=["rest_and_recover", "maintain_health",
                 "reduce_load", "nourish_resources"],
    ),
    # ── 28. 大过 = 兑上巽下 ──
    "011110": HexagramInfo(
        name="大过卦",
        meaning="过度负载，系统超限",
        risk=RiskLevel.CRITICAL,
        actions=["reduce_load", "enable_rate_limiting",
                 "decrease_concurrency", "emergency_scale_down"],
    ),
    # ── 29. 坎 = 坎上坎下 ──
    "010010": HexagramInfo(
        name="坎卦",
        meaning="重重险难，持续危机",
        risk=RiskLevel.CRITICAL,
        actions=["trigger_recovery_mode", "isolate_failure",
                 "activate_fallback", "request_help"],
    ),
    # ── 30. 离 = 离上离下 ──
    "101101": HexagramInfo(
        name="离卦",
        meaning="光明附丽，可见性高",
        risk=RiskLevel.LOW,
        actions=["enhance_logging", "increase_observability",
                 "share_status", "maintain_transparency"],
    ),
    # ── 31. 咸 = 兑上艮下 ──
    "011100": HexagramInfo(
        name="咸卦",
        meaning="感应交流，Agent 间共鸣",
        risk=RiskLevel.LOW,
        actions=["enable_sync", "share_context",
                 "enhance_communication", "build_rapport"],
    ),
    # ── 32. 恒 = 震上巽下 ──
    "001110": HexagramInfo(
        name="恒卦",
        meaning="持久，长期稳定运行",
        risk=RiskLevel.LOW,
        actions=["maintain_steady_state", "optimize_for_longevity",
                 "enable_predictive_maintenance", "celebrate_reliability"],
    ),
    # ── 33. 遁 = 乾上艮下 ──
    "111100": HexagramInfo(
        name="遁卦",
        meaning="退避策略，主动收缩",
        risk=RiskLevel.MEDIUM,
        actions=["graceful_shutdown", "reduce_exposure",
                 "preserve_state", "retreat_to_safe_mode"],
    ),
    # ── 34. 大壮 = 震上乾下 ──
    "001111": HexagramInfo(
        name="大壮卦",
        meaning="强壮有力，系统强势",
        risk=RiskLevel.LOW,
        actions=["leverage_strength", "push_forward",
                 "expand_capacity", "seize_opportunity"],
    ),
    # ── 35. 晋 = 离上坤下 ──
    "101000": HexagramInfo(
        name="晋卦",
        meaning="晋升进步，Evolution Score 提升",
        risk=RiskLevel.LOW,
        actions=["advance_position", "seize_opportunity",
                 "accelerate_growth", "promote_capable"],
    ),
    # ── 36. 明夷 = 坤上离下 ──
    "000101": HexagramInfo(
        name="明夷卦",
        meaning="光明受伤，核心能力受损",
        risk=RiskLevel.HIGH,
        actions=["protect_core", "hide_strength",
                 "preserve_capability", "wait_for_recovery"],
    ),
    # ── 37. 家人 = 巽上离下 ──
    "110101": HexagramInfo(
        name="家人卦",
        meaning="家庭和睦，内部协调良好",
        risk=RiskLevel.LOW,
        actions=["strengthen_bonds", "improve_communication",
                 "maintain_order", "nurture_team"],
    ),
    # ── 38. 睽 = 离上兑下 ──
    "101011": HexagramInfo(
        name="睽卦",
        meaning="背离分歧，目标不一致",
        risk=RiskLevel.HIGH,
        actions=["address_divergence", "realign_goals",
                 "mediate_conflict", "find_common_ground"],
    ),
    # ── 39. 蹇 = 坎上艮下 ──
    "010100": HexagramInfo(
        name="蹇卦",
        meaning="前途艰难，系统阻塞（网络/API 问题）",
        risk=RiskLevel.CRITICAL,
        actions=["suspend_current_task", "spawn_network_diagnostic_agent",
                 "check_api_health", "retry_with_exponential_backoff"],
    ),
    # ── 40. 解 = 震上坎下 ──
    "001010": HexagramInfo(
        name="解卦",
        meaning="解除困境，问题已缓解",
        risk=RiskLevel.MEDIUM,
        actions=["verify_resolution", "resume_normal_operations",
                 "update_runbooks", "prevent_recurrence"],
    ),
    # ── 41. 损 = 艮上兑下 ──
    "100011": HexagramInfo(
        name="损卦",
        meaning="减损优化，精简冗余",
        risk=RiskLevel.MEDIUM,
        actions=["identify_waste", "optimize_resource_usage",
                 "remove_redundancy", "improve_efficiency"],
    ),
    # ── 42. 益 = 巽上震下 ──
    "110001": HexagramInfo(
        name="益卦",
        meaning="增益扩展，能力提升",
        risk=RiskLevel.LOW,
        actions=["expand_capacity", "add_new_features",
                 "increase_throughput", "invest_in_growth"],
    ),
    # ── 43. 夬 = 兑上乾下 ──
    "011111": HexagramInfo(
        name="夬卦",
        meaning="决断果断，快速决策",
        risk=RiskLevel.MEDIUM,
        actions=["make_decision", "take_action",
                 "cut_losses", "execute_decisively"],
    ),
    # ── 44. 姤 = 乾上巽下 ──
    "111110": HexagramInfo(
        name="姤卦",
        meaning="不期而遇，突发状况",
        risk=RiskLevel.MEDIUM,
        actions=["handle_unexpected", "adapt_quickly",
                 "assess_impact", "contingency_plan"],
    ),
    # ── 45. 萃 = 兑上坤下 ──
    "011000": HexagramInfo(
        name="萃卦",
        meaning="聚集汇合，资源整合",
        risk=RiskLevel.LOW,
        actions=["gather_resources", "consolidate_efforts",
                 "merge_results", "centralize_data"],
    ),
    # ── 46. 升 = 坤上巽下 ──
    "000110": HexagramInfo(
        name="升卦",
        meaning="上升期，Evolution Score 快速增长",
        risk=RiskLevel.LOW,
        actions=["increase_task_allocation", "enable_fast_path",
                 "reduce_logging_overhead", "accelerate_growth"],
    ),
    # ── 47. 困 = 兑上坎下 ──
    "011010": HexagramInfo(
        name="困卦",
        meaning="困境，资源耗尽（CPU/Memory 不足）",
        risk=RiskLevel.CRITICAL,
        actions=["release_resources", "scale_down_memory",
                 "defer_non_critical_tasks", "request_resource_allocation"],
    ),
    # ── 48. 井 = 坎上巽下 ──
    "010110": HexagramInfo(
        name="井卦",
        meaning="井水不竭，持续供给",
        risk=RiskLevel.LOW,
        actions=["maintain_supply", "ensure_sustainability",
                 "refresh_resources", "share_knowledge"],
    ),
    # ── 49. 革 = 兑上离下 ──
    "011101": HexagramInfo(
        name="革卦",
        meaning="变革革新，系统升级",
        risk=RiskLevel.MEDIUM,
        actions=["implement_change", "embrace_innovation",
                 "migrate_system", "deploy_update"],
    ),
    # ── 50. 鼎 = 离上巽下 ──
    "101110": HexagramInfo(
        name="鼎卦",
        meaning="鼎新革故，建立新秩序",
        risk=RiskLevel.LOW,
        actions=["establish_foundation", "build_stability",
                 "create_new_structure", "transform_system"],
    ),
    # ── 51. 震 = 震上震下 ──
    "001001": HexagramInfo(
        name="震卦",
        meaning="震动惊醒，突发事件",
        risk=RiskLevel.MEDIUM,
        actions=["respond_to_alert", "take_immediate_action",
                 "assess_damage", "activate_recovery"],
    ),
    # ── 52. 艮 = 艮上艮下 ──
    "100100": HexagramInfo(
        name="艮卦",
        meaning="止步停止，主动暂停",
        risk=RiskLevel.MEDIUM,
        actions=["pause_operations", "reassess_strategy",
                 "consolidate_gains", "wait_for_clarity"],
    ),
    # ── 53. 渐 = 巽上艮下 ──
    "110100": HexagramInfo(
        name="渐卦",
        meaning="循序渐进，稳步提升",
        risk=RiskLevel.LOW,
        actions=["monitor_progress", "adjust_batch_size",
                 "optimize_cache", "gradual_scale_up"],
    ),
    # ── 54. 归妹 = 震上兑下 ──
    "001011": HexagramInfo(
        name="归妹卦",
        meaning="归属配合，角色适配",
        risk=RiskLevel.MEDIUM,
        actions=["match_roles", "assign_tasks",
                 "adjust_expectations", "accept_limitations"],
    ),
    # ── 55. 丰 = 震上离下 ──
    "001101": HexagramInfo(
        name="丰卦",
        meaning="丰盛充裕，高峰期",
        risk=RiskLevel.LOW,
        actions=["enjoy_abundance", "share_wealth",
                 "prepare_for_decline", "maximize_output"],
    ),
    # ── 56. 旅 = 离上艮下 ──
    "101100": HexagramInfo(
        name="旅卦",
        meaning="旅行迁移，系统迁移",
        risk=RiskLevel.MEDIUM,
        actions=["migrate_workload", "explore_new_territory",
                 "backup_before_move", "validate_destination"],
    ),
    # ── 57. 巽 = 巽上巽下 ──
    "110110": HexagramInfo(
        name="巽卦",
        meaning="顺从灵活，随风而动",
        risk=RiskLevel.LOW,
        actions=["follow_guidance", "stay_adaptable",
                 "gentle_approach", "incremental_change"],
    ),
    # ── 58. 兑 = 兑上兑下 ──
    "011011": HexagramInfo(
        name="兑卦",
        meaning="喜悦交流，用户满意",
        risk=RiskLevel.LOW,
        actions=["improve_communication", "celebrate_together",
                 "enhance_user_experience", "share_joy"],
    ),
    # ── 59. 涣 = 巽上坎下 ──
    "110010": HexagramInfo(
        name="涣卦",
        meaning="涣散分离，注意力分散",
        risk=RiskLevel.HIGH,
        actions=["prevent_fragmentation", "reunite_team",
                 "focus_efforts", "consolidate_tasks"],
    ),
    # ── 60. 节 = 坎上兑下 ──
    "010011": HexagramInfo(
        name="节卦",
        meaning="节制约束，限流控制",
        risk=RiskLevel.MEDIUM,
        actions=["enforce_limits", "control_growth",
                 "rate_limit", "budget_resources"],
    ),
    # ── 61. 中孚 = 巽上兑下 ──
    "110011": HexagramInfo(
        name="中孚卦",
        meaning="中正诚信，系统可信",
        risk=RiskLevel.LOW,
        actions=["maintain_integrity", "build_trust",
                 "verify_outputs", "ensure_consistency"],
    ),
    # ── 62. 小过 = 震上艮下 ──
    "001100": HexagramInfo(
        name="小过卦",
        meaning="小有过失，微调修正",
        risk=RiskLevel.MEDIUM,
        actions=["correct_minor_errors", "prevent_escalation",
                 "fine_tune", "patch_quickly"],
    ),
    # ── 63. 既济 = 坎上离下 ──
    "010101": HexagramInfo(
        name="既济卦",
        meaning="功成，连续成功，Evolution Score 满分",
        risk=RiskLevel.LOW,
        actions=["celebrate_success", "share_best_practices",
                 "mentor_junior_agents", "maintain_excellence"],
    ),
    # ── 64. 未济 = 离上坎下 ──
    "101010": HexagramInfo(
        name="未济卦",
        meaning="重整/退化，连续失败，需要干预",
        risk=RiskLevel.HIGH,
        actions=["trigger_recovery_mode", "analyze_failure_patterns",
                 "apply_historical_fixes", "consider_graceful_shutdown"],
    ),
}

# ============================================================
# 映射函数
# ============================================================

def map_binary_to_hexagram(binary: str) -> HexagramInfo:
    """
    将 6-bit 二进制映射到卦象

    Args:
        binary: 6-bit 二进制字符串（自下而上，初爻在右）

    Returns:
        HexagramInfo 对象
    """
    if binary in HEXAGRAM_TABLE:
        return HEXAGRAM_TABLE[binary]

    # 如果没有精确匹配，根据阳爻数量判断大致状态
    yang_count = binary.count("1")

    if yang_count >= 5:
        return HEXAGRAM_TABLE["111111"]  # 乾卦（接近全阳）
    elif yang_count >= 4:
        return HEXAGRAM_TABLE["010101"]  # 既济卦（多数优秀）
    elif yang_count >= 3:
        return HEXAGRAM_TABLE["110100"]  # 渐卦（中等偏上）
    elif yang_count >= 2:
        return HEXAGRAM_TABLE["101010"]  # 未济卦（中等偏下）
    elif yang_count >= 1:
        return HEXAGRAM_TABLE["010100"]  # 蹇卦（多数不足）
    else:
        return HEXAGRAM_TABLE["000000"]  # 坤卦（接近全阴）

# ============================================================
# 测试用例
# ============================================================

if __name__ == "__main__":
    print("=== Hexagram Mapping 测试 ===\n")

    # 验证无重复 key
    import re
    with open(__file__, encoding="utf-8") as f:
        src = f.read()
    keys = re.findall(r'"([01]{6})":', src)
    seen = set()
    dupes = []
    for k in keys:
        if k in seen:
            dupes.append(k)
        seen.add(k)
    if dupes:
        print(f"FAIL: duplicate keys: {dupes}")
    else:
        print(f"PASS: {len(seen)} unique keys, no duplicates")

    # 验证覆盖全部 64 种组合
    all_combos = {f"{i:06b}" for i in range(64)}
    missing = all_combos - set(HEXAGRAM_TABLE.keys())
    if missing:
        print(f"FAIL: missing {len(missing)} combinations: {sorted(missing)}")
    else:
        print(f"PASS: all 64 combinations covered")

    # 测试精确匹配
    print()
    test_cases = [
        ("111111", "乾卦"),
        ("000000", "坤卦"),
        ("010001", "屯卦"),
        ("010101", "既济卦"),
        ("101010", "未济卦"),
        ("011010", "困卦"),
        ("010100", "蹇卦"),
        ("000001", "复卦"),
    ]

    for binary, expected_name in test_cases:
        hexagram = map_binary_to_hexagram(binary)
        status = "PASS" if hexagram.name == expected_name else f"FAIL (got {hexagram.name})"
        print(f"  {binary} → {hexagram.name} [{status}]")
