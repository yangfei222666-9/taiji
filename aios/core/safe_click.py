# aios/core/safe_click.py - 安全点击执行器 v1.0
"""
Phase 1.5: 安全点击收口模块

四道安全闸门：
  闸门 1: 窗口绑定 — 点击前验证前台窗口归属
  闸门 2: 高风险区域禁点 — 顶部导航带、任务栏、关闭按钮等
  闸门 3: 低风险目标白名单 — 只允许点击安全类型的目标
  闸门 4: OCR 置信度下限 — confidence 低于阈值直接拒绝

设计原则：
  - 默认拒绝，只有四道闸门全部通过才执行真点击
  - 任何一道闸门失败 → dry-run（只记录，不执行）
  - 所有决策可追溯（写入 click_audit_log.jsonl）
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── 常量 ──────────────────────────────────────────────

AUDIT_LOG = Path(__file__).resolve().parent.parent / "events" / "click_audit_log.jsonl"

# 闸门 2: 高风险区域（基于屏幕绝对坐标）
# 这些区域默认禁止点击
UNSAFE_REGIONS = {
    "top_nav_bar": {
        "desc": "浏览器标签栏/标题栏/地址栏",
        "rule": lambda x, y, sw, sh: y < 80,
    },
    "taskbar": {
        "desc": "系统任务栏（底部）",
        "rule": lambda x, y, sw, sh: y > sh - 60,
    },
    "window_controls": {
        "desc": "窗口关闭/最小化/最大化按钮（右上角）",
        "rule": lambda x, y, sw, sh: x > sw - 160 and y < 40,
    },
}

# 闸门 3: 高风险文本关键词（OCR 识别出的文本包含这些词时拒绝点击）
UNSAFE_TEXT_KEYWORDS = [
    "关闭", "close", "删除", "delete", "remove",
    "发送", "send", "提交", "submit", "confirm",
    "确认", "购买", "buy", "pay", "支付",
    "退出", "exit", "quit", "注销", "logout",
    "格式化", "format", "清空", "clear all",
]

# 低风险目标类型白名单
SAFE_TARGET_TYPES = [
    "static_text",       # 纯文本标签
    "content_text",      # 内容区文字
    "menu_label",        # 无副作用的菜单标题
    "panel_label",       # 面板标签
    "status_text",       # 状态文本
]

# 闸门 4: OCR 置信度最低阈值
CONFIDENCE_THRESHOLD = 0.7


# ── 数据结构 ────────────────────────────────────────────

@dataclass
class ClickTarget:
    """点击目标描述"""
    text: str                          # OCR 识别的文本
    bbox: tuple                        # (x1, y1, x2, y2) 绝对坐标
    center_x: int = 0                  # 点击中心 x
    center_y: int = 0                  # 点击中心 y
    source_window: str = ""            # OCR 截图来源窗口标题
    target_type: str = "unknown"       # 目标类型
    confidence: float = 0.0            # OCR 置信度

    def __post_init__(self):
        if self.bbox and not self.center_x:
            x1, y1, x2, y2 = self.bbox
            self.center_x = (x1 + x2) // 2
            self.center_y = (y1 + y2) // 2


@dataclass
class ClickDecision:
    """点击决策结果"""
    allowed: bool = False
    dry_run: bool = True
    reason: str = ""
    gate_results: dict = field(default_factory=dict)
    target: Optional[dict] = None
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


# ── 闸门实现 ────────────────────────────────────────────

def _get_foreground_window_title() -> str:
    """获取当前前台窗口标题（Windows）"""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def _get_screen_size() -> tuple:
    """获取屏幕分辨率"""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        return (sw, sh)
    except Exception:
        return (1920, 1080)  # 默认值


def gate_1_window_binding(target: ClickTarget) -> dict:
    """闸门 1: 窗口绑定检查

    验证：
    - OCR 截图来源窗口 == 当前前台窗口
    - 如果不一致，拒绝执行
    """
    current_window = _get_foreground_window_title()
    source_window = target.source_window

    if not source_window:
        return {
            "gate": "window_binding",
            "passed": False,
            "reason": "目标缺少 source_window 信息，无法验证窗口归属",
            "current_window": current_window,
            "source_window": source_window,
        }

    # 窗口标题匹配（包含关系，因为标题可能有动态后缀）
    matched = (
        source_window in current_window
        or current_window in source_window
        or source_window.split(" - ")[0] == current_window.split(" - ")[0]
    )

    return {
        "gate": "window_binding",
        "passed": matched,
        "reason": "" if matched else f"窗口不匹配: 前台='{current_window}', 目标来源='{source_window}'",
        "current_window": current_window,
        "source_window": source_window,
    }


def gate_2_unsafe_regions(target: ClickTarget) -> dict:
    """闸门 2: 高风险区域禁点检查

    验证：
    - 点击坐标不在禁点区域内
    - y < 80 的顶部导航带
    - 底部任务栏
    - 右上角窗口控制按钮
    """
    sw, sh = _get_screen_size()
    x, y = target.center_x, target.center_y
    violations = []

    for region_name, region_def in UNSAFE_REGIONS.items():
        if region_def["rule"](x, y, sw, sh):
            violations.append(f"{region_name}: {region_def['desc']}")

    passed = len(violations) == 0

    return {
        "gate": "unsafe_regions",
        "passed": passed,
        "reason": "" if passed else f"目标位于禁点区域: {'; '.join(violations)}",
        "click_pos": (x, y),
        "screen_size": (sw, sh),
        "violations": violations,
    }


def gate_3_target_safety(target: ClickTarget) -> dict:
    """闸门 3: 目标安全性检查

    验证：
    - 目标类型在白名单内
    - 目标文本不包含高风险关键词
    """
    issues = []

    # 检查目标类型
    if target.target_type not in SAFE_TARGET_TYPES:
        issues.append(f"目标类型 '{target.target_type}' 不在安全白名单中")

    # 检查文本关键词
    text_lower = target.text.lower()
    for kw in UNSAFE_TEXT_KEYWORDS:
        if kw.lower() in text_lower:
            issues.append(f"目标文本包含高风险关键词: '{kw}'")
            break

    passed = len(issues) == 0

    return {
        "gate": "target_safety",
        "passed": passed,
        "reason": "" if passed else "; ".join(issues),
        "target_type": target.target_type,
        "target_text": target.text,
        "safe_types": SAFE_TARGET_TYPES,
    }


def gate_4_confidence(target: ClickTarget) -> dict:
    """闸门 4: OCR 置信度下限检查

    验证：
    - OCR 识别置信度 >= CONFIDENCE_THRESHOLD
    - 低于阈值直接拒绝，防止低质量识别结果触发真点击
    """
    passed = target.confidence >= CONFIDENCE_THRESHOLD

    return {
        "gate": "confidence",
        "passed": passed,
        "reason": "" if passed else (
            f"OCR 置信度 {target.confidence:.3f} 低于阈值 {CONFIDENCE_THRESHOLD}"
        ),
        "actual_confidence": target.confidence,
        "threshold": CONFIDENCE_THRESHOLD,
    }


# ── 主执行器 ────────────────────────────────────────────

def evaluate_click(target: ClickTarget) -> ClickDecision:
    """评估点击是否安全

    依次执行四道闸门，任何一道失败则 dry-run。

    Returns:
        ClickDecision 包含完整的决策信息
    """
    gates = {}

    # 闸门 1: 窗口绑定
    g1 = gate_1_window_binding(target)
    gates["window_binding"] = g1

    # 闸门 2: 高风险区域
    g2 = gate_2_unsafe_regions(target)
    gates["unsafe_regions"] = g2

    # 闸门 3: 目标安全性
    g3 = gate_3_target_safety(target)
    gates["target_safety"] = g3

    # 闸门 4: OCR 置信度
    g4 = gate_4_confidence(target)
    gates["confidence"] = g4

    # 综合判断
    all_gates = [g1, g2, g3, g4]
    all_passed = all(g["passed"] for g in all_gates)
    failed_gates = [g["gate"] for g in all_gates if not g["passed"]]

    if all_passed:
        reason = "四道闸门全部通过，允许执行真点击"
    else:
        reasons = [g["reason"] for g in all_gates if not g["passed"]]
        reason = f"闸门未通过 ({', '.join(failed_gates)}): {'; '.join(reasons)}"

    decision = ClickDecision(
        allowed=all_passed,
        dry_run=not all_passed,
        reason=reason,
        gate_results=gates,
        target=asdict(target),
    )

    # 写审计日志
    _write_audit_log(decision)

    return decision


def execute_safe_click(target: ClickTarget, force_dry_run: bool = False) -> dict:
    """安全点击执行入口

    Args:
        target: 点击目标
        force_dry_run: 强制 dry-run（用于测试）

    Returns:
        执行结果 dict
    """
    decision = evaluate_click(target)

    if force_dry_run:
        decision.allowed = False
        decision.dry_run = True
        decision.reason = f"[强制 dry-run] {decision.reason}"

    result = {
        "action": "click",
        "target_text": target.text,
        "target_pos": (target.center_x, target.center_y),
        "decision": asdict(decision),
        "executed": False,
        "timestamp": time.time(),
    }

    if decision.allowed:
        # 真点击
        try:
            import pyautogui
            pyautogui.click(target.center_x, target.center_y)
            result["executed"] = True
            result["status"] = "clicked"
        except Exception as e:
            result["executed"] = False
            result["status"] = f"click_failed: {e}"
            result["error"] = str(e)
    else:
        result["status"] = "dry_run"
        result["dry_run_reason"] = decision.reason

    return result


# ── 审计日志 ────────────────────────────────────────────

def _write_audit_log(decision: ClickDecision):
    """写入点击审计日志"""
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "allowed": decision.allowed,
            "dry_run": decision.dry_run,
            "reason": decision.reason,
            "gates": {
                k: {"passed": v["passed"], "reason": v.get("reason", "")}
                for k, v in decision.gate_results.items()
            },
            "confidence_detail": {
                "actual": decision.gate_results.get("confidence", {}).get("actual_confidence"),
                "threshold": decision.gate_results.get("confidence", {}).get("threshold"),
            },
            "target": decision.target,
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 审计日志写入失败不影响主流程


# ── 便捷函数 ────────────────────────────────────────────

def check_click_safety(
    text: str,
    bbox: tuple,
    source_window: str = "",
    target_type: str = "unknown",
    confidence: float = 0.0,
) -> dict:
    """便捷函数：快速检查一个点击目标是否安全

    Returns:
        {"safe": bool, "reason": str, "gates": {...}}
    """
    target = ClickTarget(
        text=text,
        bbox=bbox,
        source_window=source_window,
        target_type=target_type,
        confidence=confidence,
    )
    decision = evaluate_click(target)
    return {
        "safe": decision.allowed,
        "reason": decision.reason,
        "gates": {
            k: {"passed": v["passed"], "reason": v.get("reason", "")}
            for k, v in decision.gate_results.items()
        },
    }


# ── CLI 入口 ────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python safe_click.py check <text> <x1> <y1> <x2> <y2> [source_window] [target_type]")
        print("  python safe_click.py demo")
        print("  python safe_click.py audit")
        print()
        print("示例:")
        print('  python safe_click.py check "设置" 500 300 560 320 "Telegram" "static_text"')
        print('  python safe_click.py check "Close" 1880 10 1920 30 "Edge" "unknown"')
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "check" and len(sys.argv) >= 7:
        text = sys.argv[2]
        bbox = (int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))
        source_window = sys.argv[7] if len(sys.argv) > 7 else ""
        target_type = sys.argv[8] if len(sys.argv) > 8 else "unknown"

        result = check_click_safety(
            text=text,
            bbox=bbox,
            source_window=source_window,
            target_type=target_type,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "demo":
        print("=== 安全点击闸门 Demo ===\n")

        # 测试 1: 安全目标
        print("测试 1: 安全目标（内容区文字）")
        r1 = check_click_safety(
            text="项目概览",
            bbox=(200, 300, 280, 320),
            source_window="Telegram",
            target_type="content_text",
        )
        print(f"  安全: {r1['safe']}")
        print(f"  原因: {r1['reason']}\n")

        # 测试 2: 顶部导航（应该被拦截）
        print("测试 2: 顶部导航（应该被拦截）")
        r2 = check_click_safety(
            text="Clawdbot Control",
            bbox=(800, 10, 920, 30),
            source_window="Edge",
            target_type="unknown",
        )
        print(f"  安全: {r2['safe']}")
        print(f"  原因: {r2['reason']}\n")

        # 测试 3: 关闭按钮（应该被拦截）
        print("测试 3: 关闭按钮（应该被拦截）")
        r3 = check_click_safety(
            text="关闭",
            bbox=(1880, 5, 1920, 35),
            source_window="Telegram",
            target_type="unknown",
        )
        print(f"  安全: {r3['safe']}")
        print(f"  原因: {r3['reason']}\n")

        # 测试 4: 窗口不匹配（应该被拦截）
        print("测试 4: 窗口不匹配（应该被拦截）")
        r4 = check_click_safety(
            text="普通文字",
            bbox=(400, 400, 500, 420),
            source_window="Edge",
            target_type="content_text",
        )
        print(f"  安全: {r4['safe']}")
        print(f"  原因: {r4['reason']}\n")

        # 测试 5: 危险文本（应该被拦截）
        print("测试 5: 危险文本关键词（应该被拦截）")
        r5 = check_click_safety(
            text="删除全部",
            bbox=(400, 400, 500, 420),
            source_window="Telegram",
            target_type="static_text",
        )
        print(f"  安全: {r5['safe']}")
        print(f"  原因: {r5['reason']}\n")

        # 测试 6: 低置信度（应该被拦截）
        print("测试 6: 低置信度 OCR 识别（应该被拦截）")
        r6 = check_click_safety(
            text="普通文字",
            bbox=(400, 300, 500, 320),
            source_window="Telegram",
            target_type="content_text",
            confidence=0.3,
        )
        print(f"  安全: {r6['safe']}")
        print(f"  原因: {r6['reason']}\n")

        # 测试 7: 高置信度安全目标（应该通过）
        print("测试 7: 高置信度安全目标（应该通过）")
        r7 = check_click_safety(
            text="项目概览",
            bbox=(200, 300, 280, 320),
            source_window="Telegram",
            target_type="content_text",
            confidence=0.92,
        )
        print(f"  安全: {r7['safe']}")
        print(f"  原因: {r7['reason']}\n")

    elif cmd == "audit":
        if AUDIT_LOG.exists():
            lines = AUDIT_LOG.read_text(encoding="utf-8").strip().split("\n")
            print(f"=== 点击审计日志 ({len(lines)} 条) ===\n")
            for line in lines[-10:]:  # 最近 10 条
                entry = json.loads(line)
                status = "✅ ALLOW" if entry["allowed"] else "🚫 DENY"
                target_text = entry.get("target", {}).get("text", "?")
                print(f"  [{entry['ts']}] {status} | '{target_text}' | {entry['reason'][:80]}")
        else:
            print("暂无审计日志")

    else:
        print(f"未知命令: {cmd}")
        print("运行 python safe_click.py 查看帮助")
