"""
TaijiOS 智能模型路由器
根据用户意图、消息复杂度、场景自动选择最优模型。

路由逻辑：
┌─────────────────┬──────────────────┬────────────────────────┐
│ 场景            │ 主模型           │ 降级链                 │
├─────────────────┼──────────────────┼────────────────────────┤
│ 日常闲聊        │ DeepSeek         │ GPT → Gemini           │
│ 比赛/实时信息   │ Gemini(grounding)│ GPT → DeepSeek         │
│ 深度分析/推演   │ GPT-5.4          │ Gemini Pro → DeepSeek  │
│ 算卦/卦象诊断   │ DeepSeek         │ GPT → Gemini           │
│ 人物/决策分析   │ GPT-5.4          │ DeepSeek → Gemini      │
│ 情绪支持        │ DeepSeek         │ GPT → Gemini           │
│ 卦变投票/交叉验证│ 全部模型并行    │ -  (Claude 仅此场景)   │
│ 架构级决策      │ Claude Opus 4.6  │ GPT → DeepSeek         │
└─────────────────┴──────────────────┴────────────────────────┘

成本分级（Claude 中转计费，严格管控）：
- DeepSeek  → 日常主力，极便宜，扛 90% 流量
- Gemini    → 实时信息，免费额度大
- GPT-5.4   → 复杂推理，中转计费可控
- Claude    → 仅卦变投票 + 架构决策，中转计费，每天 < ¥1
- 全部失败才报错，用户无感知切换
"""

import logging
from typing import Optional

logger = logging.getLogger("model_router")

# ── 意图 → 模型映射 ──────────────────────────────────────────────────────────

# 意图关键词 → 路由规则
INTENT_ROUTES = {
    # 需要实时数据的场景 → Gemini (Google Search grounding)
    "realtime": {
        "keywords": ["比赛", "赛事", "比分", "今天", "现在", "最新", "实时",
                     "新闻", "热搜", "刚刚", "今晚", "昨天", "明天",
                     "天气", "股价", "汇率", "联赛", "NBA", "英超", "西甲",
                     "世界杯", "欧冠", "积分榜", "排名"],
        "primary": "gemini",
        "fallbacks": ["gpt", "deepseek"],
    },
    # 深度分析/推演 → GPT-5.4
    "deep_analysis": {
        "keywords": ["推演", "深度分析", "战略", "全面分析", "系统分析",
                     "对手", "竞品", "商业模式", "盈利", "变现",
                     "怎么看", "什么人", "能不能信", "靠不靠谱",
                     "合伙人", "投资人"],
        "primary": "gpt",
        "fallbacks": ["gemini_pro", "deepseek"],
    },
    # 决策分析 → GPT-5.4
    "decision": {
        "keywords": ["要不要", "该不该", "选哪个", "怎么选", "纠结",
                     "两难", "做决定", "选择"],
        "primary": "gpt",
        "fallbacks": ["deepseek", "gemini"],
    },
    # 算卦/易经相关 → DeepSeek (训练数据中文强)
    "divination": {
        "keywords": ["算一卦", "算卦", "占卜", "运势", "卦象", "易经",
                     "八字", "风水", "吉凶", "求签"],
        "primary": "deepseek",
        "fallbacks": ["gpt", "gemini"],
    },
    # 情绪支持 → DeepSeek (便宜+中文自然)
    "emotional": {
        "keywords": ["焦虑", "失眠", "崩溃", "不想干了", "放弃", "太累",
                     "没意义", "迷茫", "绝望", "痛苦", "撑不住"],
        "primary": "deepseek",
        "fallbacks": ["gpt", "gemini"],
    },
    # 架构级决策 → Claude（仅此场景走 Claude，中转计费严格管控）
    "architecture": {
        "keywords": ["架构设计", "系统设计", "重构", "技术选型", "架构评审",
                     "引擎设计", "模块设计", "整体规划"],
        "primary": "claude",
        "fallbacks": ["gpt", "deepseek"],
    },
}

# 默认路由（日常闲聊）
DEFAULT_ROUTE = {
    "primary": "deepseek",
    "fallbacks": ["gpt", "gemini"],
}

# Claude 保留场景（不经过 ModelRouter，直接调用）：
# 1. ising_core._validate_transition() → cross_validate(models=["claude","deepseek","gemini"])
# 2. 架构级决策 → 上方 architecture 路由
# 其他场景 Claude 不参与，确保中转费用可控


class ModelRouter:
    """智能模型路由器"""

    def __init__(self, available_models: list[str]):
        """
        available_models: multi_llm 中已初始化的模型名列表
        """
        self.available = set(available_models)
        self._stats = {}  # 模型调用统计

    def route(self, user_input: str, intent_name: str = "") -> tuple[str, list[str]]:
        """
        根据用户输入决定使用哪个模型。
        返回 (primary_model, fallback_chain)
        """
        # 1. 检测意图匹配路由规则
        best_route = None
        best_hits = 0

        for route_name, config in INTENT_ROUTES.items():
            hits = sum(1 for kw in config["keywords"] if kw in user_input)
            if hits > best_hits:
                best_hits = hits
                best_route = config

        # 2. 没有匹配就用默认路由
        if not best_route:
            best_route = DEFAULT_ROUTE

        # 3. 过滤掉不可用的模型
        primary = best_route["primary"]
        fallbacks = best_route["fallbacks"]

        if primary not in self.available:
            # 主模型不可用，从降级链中找第一个可用的
            for fb in fallbacks:
                if fb in self.available:
                    primary = fb
                    fallbacks = [f for f in fallbacks if f != fb]
                    break
            else:
                # 所有都不可用，取任意一个可用模型
                if self.available:
                    primary = next(iter(self.available))
                    fallbacks = []

        # 只保留可用的降级模型
        fallbacks = [f for f in fallbacks if f in self.available and f != primary]

        # 4. 记录路由决策
        self._stats[primary] = self._stats.get(primary, 0) + 1
        logger.debug(f"Route: '{user_input[:30]}...' → {primary} (fallbacks: {fallbacks})")

        return primary, fallbacks

    def get_stats(self) -> dict:
        """获取模型调用统计"""
        return dict(self._stats)

    def get_status(self) -> str:
        """状态展示"""
        lines = ["[多模型路由]"]
        lines.append(f"  可用模型: {', '.join(sorted(self.available))}")
        if self._stats:
            lines.append("  调用统计:")
            for model, count in sorted(self._stats.items(), key=lambda x: -x[1]):
                lines.append(f"    {model}: {count}次")
        return "\n".join(lines)
