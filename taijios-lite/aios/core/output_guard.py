"""
TaijiOS 输出守卫 — 象征化硬闸 + 信息稀疏反问
防止模型在信息不足时过度补全，防止象征化表达无事实锚点。

插入点：
- symbolic_output_guard(): bot_core.py 第14步，reply 组装前
- sparse_input_check(): bot_core.py 第8步，validated_call 前

依赖方向：output_guard ← bot_core
output_guard 不 import multi_llm / failure_rules，纯文本处理。
"""

import re
import logging
from typing import Optional

logger = logging.getLogger("output_guard")

# ── 象征化触发词（命中后进入锚点检查）──────────────────────────

SYMBOLIC_TRIGGERS = [
    "心肾不交", "水火失调", "水火未济", "阴阳失衡", "阴阳不调",
    "气血不足", "气血亏虚", "肝气郁结", "肝火旺", "心火旺",
    "五行相克", "五行相生", "金木水火土",
    "命理", "运势走低", "运势上扬", "运势偏弱",
    "煞气", "犯太岁", "冲克",
]

# 八卦名在解释性语境下的触发（"乾卦说明你..."这种）
TRIGRAM_EXPLAIN_PATTERN = re.compile(
    r'(?:乾|坤|震|巽|坎|离|艮|兑)(?:卦|为|象|主|代表|说明|提示|暗示|显示).*?(?:你|她|他|阿姨|妈妈|对方)'
)

# ── 事实锚点检测 ──────────────────────────────────────────────

FACT_ANCHOR_PATTERNS = [
    r'你(?:说|提到|告诉|讲)(?:过|了)?',          # 引用用户原话
    r'根据(?:你|检查|报告|数据|医生)',             # 引用具体来源
    r'(?:具体|实际|现实)(?:来看|情况|表现)',        # 具体事实
    r'\d{1,2}[点时]',                              # 具体时间
    r'\d+(?:天|周|月|年|次|岁)',                    # 具体数量
    r'(?:医院|医生|检查|报告|化验|片子|CT|B超)',    # 医疗事实
    r'(?:走路|散步|运动|吃饭|睡觉|起床).*?(?:多|少|疼|痛|累)', # 具体行为+症状
]


def _has_fact_anchor(text: str) -> bool:
    """检查文本中是否有至少一个事实锚点"""
    for pattern in FACT_ANCHOR_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def _count_symbolic_triggers(text: str) -> list[str]:
    """统计命中的象征化触发词"""
    hits = [t for t in SYMBOLIC_TRIGGERS if t in text]
    if TRIGRAM_EXPLAIN_PATTERN.search(text):
        hits.append("卦象解释性语境")
    return hits


def symbolic_output_guard(reply: str, user_input: str = "") -> tuple[str, list[str]]:
    """象征化输出硬闸

    检查 reply 中是否有无锚点的象征化表达。
    有象征词但无事实锚点 → 在末尾追加提醒。

    Args:
        reply: 模型生成的回复
        user_input: 用户原始输入（用于判断上下文）

    Returns:
        (处理后的reply, 触发的警告列表)
    """
    hits = _count_symbolic_triggers(reply)
    if not hits:
        return reply, []

    has_anchor = _has_fact_anchor(reply)
    if has_anchor:
        # 有象征词但也有事实锚点 → 放行
        return reply, []

    # 无锚点的象征漂移 → 追加提醒，不删原文
    warnings = [f"symbolic_no_anchor:{','.join(hits[:3])}"]
    disclaimer = "\n\n⚠ 以上分析基于有限信息，仅供参考。如需更准确的判断，请补充具体情况。"
    logger.info(f"[output_guard] 象征化无锚点，追加提醒。触发词: {hits[:3]}")

    return reply + disclaimer, warnings


# ── 信息稀疏反问 ──────────────────────────────────────────────

# 不需要反问的意图类型
SKIP_INTENTS = {"greeting", "small_talk", "闲聊", "你好", "谢谢"}

# 反问模板
PROBE_TEMPLATES = {
    "health": [
        "具体是哪里不舒服？",
        "这个情况持续多久了？",
        "有没有去看过医生？",
    ],
    "event": [
        "能说说具体发生了什么吗？",
        "这件事是什么时候的？",
        "涉及到哪些人？",
    ],
    "decision": [
        "你现在最纠结的点是什么？",
        "有哪些选项？各自的利弊你怎么看？",
    ],
    "general": [
        "能再多说一点吗？信息越具体，分析越准。",
    ],
}

# 健康相关关键词
HEALTH_KEYWORDS = ["睡眠", "失眠", "头疼", "头痛", "胃", "腰", "疼", "痛",
                   "不舒服", "难受", "生病", "身体", "血压", "血糖"]

# 决策相关关键词
DECISION_KEYWORDS = ["要不要", "该不该", "选哪个", "怎么选", "纠结", "犹豫"]


def _detect_probe_category(text: str) -> str:
    """判断应该用哪类反问模板"""
    if any(kw in text for kw in HEALTH_KEYWORDS):
        return "health"
    if any(kw in text for kw in DECISION_KEYWORDS):
        return "decision"
    return "general"


def sparse_input_check(message: str, char_threshold: int = 15) -> Optional[str]:
    """信息稀疏检查

    输入过短且不是闲聊 → 返回反问文本，不进入生成。
    输入足够 → 返回 None，正常进入生成。

    Args:
        message: 用户输入
        char_threshold: 字符数阈值（低于此值触发反问）

    Returns:
        反问文本 或 None
    """
    # 去掉空白后的有效长度
    clean = message.strip()
    if len(clean) >= char_threshold:
        return None

    # 闲聊类跳过
    if any(kw in clean for kw in SKIP_INTENTS):
        return None

    # 纯标点/表情/单字跳过
    if len(clean) <= 1:
        return None

    # 判断反问类别
    category = _detect_probe_category(clean)
    probes = PROBE_TEMPLATES.get(category, PROBE_TEMPLATES["general"])

    # 组装反问
    probe_text = probes[0]  # 取第一条
    logger.info(f"[output_guard] 信息稀疏（{len(clean)}字），触发反问: {probe_text}")

    return f"你说的「{clean}」我注意到了。{probe_text}"
