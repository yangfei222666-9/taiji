# aios/core/policies.py - 安全策略（锁死）
"""
系统可以进化，但不允许自毁。

✅ 允许自动应用: alias 追加（只 append，不覆盖、不删除）
❌ 禁止自动应用: 阈值变更、模型路由变更、删除已有 alias、修改 config.yaml
"""


def apply_alias_suggestion(
    alias_map: dict, item: dict, min_conf: float, no_overwrite: bool
) -> tuple:
    """
    单条 alias 建议应用逻辑。
    返回 (applied: bool, why: str)
    """
    inp = item.get("input", "")
    sug = item.get("suggested", "")
    conf = item.get("confidence", 0)

    if no_overwrite and inp in alias_map:
        return False, "skip_existing_key_no_overwrite"
    if conf < min_conf:
        return False, "skip_low_confidence"
    if inp not in alias_map:
        alias_map[inp] = sug
        return True, "applied_append_new_key"
    return False, "skip_existing_key_no_overwrite"
