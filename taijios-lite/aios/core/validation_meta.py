"""
TaijiOS 验证元信息 — ValidationMeta dataclass
统一 validated_call() 的返回结构，供状态行、日志、Ising心跳消费。

依赖方向：validation_meta ← multi_llm ← bot_core
validation_meta 不 import 任何 TaijiOS 模块，纯数据结构。
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal


@dataclass
class ValidationMeta:
    # 最终内容
    final_content: str = ""

    # 模型链
    primary_model: str = ""                # 生成模型 (deepseek / gpt_direct / error)
    validator_model: Optional[str] = None  # 验证模型 (gpt / claude / gemini / None)
    model_chain: str = ""                  # 如 "deepseek→gpt"

    # 验证结果
    verification_status: Literal[
        "passed",       # 验证通过（主验证器确认）
        "modified",     # 验证通过但有修正
        "degraded",     # 降级到备用验证器
        "skipped",      # 验证跳过（验证器不可用）
        "failed",       # 验证失败（全部验证器不可用，返回未验证原文）
        "error",        # 生成阶段就失败了
    ] = "skipped"

    modified: bool = False                 # GPT 是否修正了内容

    # 延迟归因（P3 对接）
    generation_ms: float = 0.0
    verification_ms: float = 0.0
    degradation_ms: float = 0.0
    total_ms: float = 0.0

    # 降级追踪
    degraded: bool = False
    degradation_reason: Optional[str] = None  # timeout / block_fallback / all_failed

    # 失败样本库联动
    triggered_rules: List[dict] = field(default_factory=list)
    active_l3_count_at_call: int = 0
    block_fallback: bool = False

    # 向后兼容：支持 meta["step1"] 下标访问
    def __getitem__(self, key):
        """兼容 dict 下标访问，过渡期使用"""
        _compat = self._to_compat_dict()
        return _compat[key]

    def get(self, key, default=None):
        """兼容 dict.get() 访问"""
        _compat = self._to_compat_dict()
        return _compat.get(key, default)

    def _to_compat_dict(self) -> dict:
        """生成兼容旧 meta dict 的映射"""
        return {
            "step1": self.primary_model,
            "step2": self.validator_model or ("skipped" if self.verification_status == "skipped" else "all_failed"),
            "modified": self.modified,
            "triggered_rules": self.triggered_rules,
        }

    def to_dict(self) -> dict:
        """完整序列化，用于 latency_breakdown.jsonl"""
        return asdict(self)

    def format_status_line(self, show_internal: bool = False) -> str:
        """生成状态行文本，供 bot_core.py 消费

        Args:
            show_internal: True 显示具体模型名（调试用），False 隐藏（面向用户）
        """
        if show_internal:
            parts = [f"[{self.model_chain}]"]
        else:
            # 用户友好：不暴露具体模型名
            parts = ["[小九]"]

        if self.modified:
            parts.append("已校验修正")
        elif self.verification_status == "passed":
            parts.append("已校验")
        elif self.verification_status == "degraded":
            parts.append("已校验(备用)")
        elif self.verification_status == "skipped":
            parts.append("快速回复")
        elif self.verification_status == "failed":
            parts.append("⚠未校验")
        elif self.verification_status == "error":
            parts.append("⚠回复异常")

        # 延迟归因
        if self.generation_ms > 0 and self.verification_ms > 0:
            parts.append(f"生成{self.generation_ms/1000:.1f}s+验证{self.verification_ms/1000:.1f}s={self.total_ms/1000:.1f}s")
        elif self.total_ms > 0:
            parts.append(f"{self.total_ms/1000:.1f}s")

        # 规则触发
        if self.triggered_rules:
            rule_names = [r["rule"] if isinstance(r, dict) else r for r in self.triggered_rules]
            parts.append(f"规则:{','.join(rule_names)}")

        return "｜".join(parts)
