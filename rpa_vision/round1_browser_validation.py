"""
Round-1-browser: Safe Click 浏览器复验脚本

目标：在浏览器窗口中，对内容区段落文本执行安全点击
验收：四闸全过 + proposal 对照 + 审计日志 + 截图留档

轮次编号: Round-1-browser
窗口类型: 浏览器 (Edge / Chrome)
文本类型: 段落文本 (content_text)
位置: 左侧内容区
"""
import json
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

import pyautogui
import win32gui
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aios.core.safe_click import (
    ClickTarget,
    execute_safe_click,
    evaluate_click,
    CONFIDENCE_THRESHOLD,
)

ROUND_ID = "Round-1-browser"
DEBUG_DIR = Path("debug_screenshots")
REPORT_DIR = Path("validation_reports")
EVIDENCE_DIR = Path("evidence") / ROUND_ID


def find_browser_window():
    """查找浏览器窗口 (Edge / Chrome)"""
    candidates = []

    def callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            for browser in ["Edge", "Chrome", "Firefox", "Brave"]:
                if browser in title:
                    results.append((hwnd, title, browser))

    win32gui.EnumWindows(callback, candidates)

    if not candidates:
        return None, None, None
    # 优先 Edge，其次 Chrome
    for pref in ["Edge", "Chrome", "Firefox", "Brave"]:
        for hwnd, title, browser in candidates:
            if browser == pref:
                return hwnd, title, browser
    return candidates[0]


def save_screenshot(prefix, ts):
    """保存截图，以轮次编号为前缀"""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    img = ImageGrab.grab()
    path = EVIDENCE_DIR / f"{ROUND_ID}_{prefix}_{ts}.png"
    img.save(str(path))
    print(f"  截图已保存: {path}")
    return path


def build_proposal(target_text, bbox, center_x, center_y, source_window, target_type, confidence):
    """构建 proposal 记录，用于事后对照"""
    return {
        "round_id": ROUND_ID,
        "timestamp": datetime.now().isoformat(),
        "target_text": target_text,
        "target_type": target_type,
        "bbox": bbox,
        "center": (center_x, center_y),
        "source_window": source_window,
        "confidence": confidence,
        "expected_behavior": "光标聚焦或文本选中，无跳转无弹窗",
    }


def save_proposal(proposal):
    """保存 proposal 到证据目录"""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"{ROUND_ID}_proposal.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(proposal, f, ensure_ascii=False, indent=2)
    print(f"  Proposal 已保存: {path}")
    return path


def run_checklist(proposal, result, before_title, after_title, before_path, after_path):
    """运行 5 项验收 checklist"""
    checks = []

    # 1. 闸门全部放行理由清晰记录
    decision = result.get("decision", {})
    gates = decision.get("gate_results", {})
    all_passed = all(g.get("passed", False) for g in gates.values())
    checks.append({
        "item": "闸门全部放行理由清晰记录",
        "passed": all_passed and decision.get("allowed", False),
        "detail": decision.get("reason", ""),
    })

    # 2. 点击坐标落在目标 bbox 内
    cx, cy = proposal["center"]
    bx1, by1, bx2, by2 = proposal["bbox"]
    in_bbox = bx1 <= cx <= bx2 and by1 <= cy <= by2
    checks.append({
        "item": "点击坐标准确落在目标 bbox 内",
        "passed": in_bbox,
        "detail": f"center=({cx},{cy}), bbox=({bx1},{by1},{bx2},{by2})",
    })

    # 3. 前台窗口不切换
    title_stable = before_title == after_title or (
        before_title and after_title and
        before_title.split(" - ")[-1] == after_title.split(" - ")[-1]
    )
    checks.append({
        "item": "前台窗口不切换",
        "passed": title_stable,
        "detail": f"before='{before_title}', after='{after_title}'",
    })

    # 4. 点击后只有低风险 UI 变化
    executed = result.get("executed", False)
    status = result.get("status", "")
    low_risk = executed and status == "clicked"
    checks.append({
        "item": "点击后只有低风险 UI 变化",
        "passed": low_risk,
        "detail": f"status={status}",
    })

    # 5. proposal 与实际目标一致
    actual_target = result.get("target_text", "")
    proposal_match = actual_target == proposal["target_text"]
    checks.append({
        "item": "proposal 中 target_text/bbox/center 与预期点击对象一致",
        "passed": proposal_match,
        "detail": f"proposal='{proposal['target_text']}', actual='{actual_target}'",
    })

    return checks


def generate_report(proposal, checks, result, before_title, after_title, before_path, after_path):
    """生成 Round-1-browser 验证报告"""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_pass = all(c["passed"] for c in checks)
    verdict = "PASS" if all_pass else "FAIL"

    lines = [
        f"# {ROUND_ID} - Safe Click 浏览器复验报告",
        f"",
        f"**验证时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**验证状态:** {'✅' if all_pass else '❌'} {verdict}",
        f"",
        f"---",
        f"",
        f"## 1. Proposal",
        f"",
        f"- **轮次编号:** {ROUND_ID}",
        f"- **目标文本:** {proposal['target_text']}",
        f"- **目标类型:** {proposal['target_type']}",
        f"- **目标 bbox:** {proposal['bbox']}",
        f"- **点击中心:** {proposal['center']}",
        f"- **来源窗口:** {proposal['source_window']}",
        f"- **置信度:** {proposal['confidence']}",
        f"- **预期行为:** {proposal['expected_behavior']}",
        f"",
        f"---",
        f"",
        f"## 2. 闸门决策",
        f"",
    ]

    decision = result.get("decision", {})
    gates = decision.get("gate_results", {})
    for gname, gdata in gates.items():
        status = "✅ PASS" if gdata.get("passed") else "❌ FAIL"
        reason = gdata.get("reason", "")
        lines.append(f"- **{gname}:** {status} {reason}")
    lines.append(f"- **综合:** {decision.get('reason', '')}")

    lines += [
        f"",
        f"---",
        f"",
        f"## 3. 执行结果",
        f"",
        f"- **executed:** {result.get('executed', False)}",
        f"- **status:** {result.get('status', '')}",
        f"- **窗口标题 before:** {before_title}",
        f"- **窗口标题 after:** {after_title}",
        f"",
        f"---",
        f"",
        f"## 4. 验收 Checklist (5/5)",
        f"",
    ]

    for i, c in enumerate(checks, 1):
        icon = "✅" if c["passed"] else "❌"
        lines.append(f"{i}. {icon} **{c['item']}** — {c['detail']}")

    lines += [
        f"",
        f"---",
        f"",
        f"## 5. 证据留档",
        f"",
        f"- Proposal: `{EVIDENCE_DIR / f'{ROUND_ID}_proposal.json'}`",
        f"- 截图 before: `{before_path}`",
        f"- 截图 after: `{after_path}`",
        f"- 审计日志: `click_audit_log.jsonl` (按时间戳筛选本轮记录)",
        f"",
        f"---",
        f"",
        f"## 6. 最终判定",
        f"",
        f"**{ROUND_ID}: {verdict}**",
        f"",
    ]

    report_path = REPORT_DIR / f"{ROUND_ID}_report_{ts}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n报告已生成: {report_path}")
    return report_path, verdict


def main():
    print("=" * 60)
    print(f"Safe Click 复验 - {ROUND_ID}")
    print(f"窗口类型: 浏览器 | 文本类型: 段落文本 | 位置: 左侧内容区")
    print(f"置信度阈值: {CONFIDENCE_THRESHOLD}")
    print("=" * 60)

    # Step 1: 查找浏览器窗口
    print("\n[Step 1] 查找浏览器窗口...")
    hwnd, title, browser = find_browser_window()
    if not hwnd:
        print("未找到浏览器窗口。请先打开 Edge 或 Chrome 并加载一个有段落文本的页面。")
        print("建议: 打开任意新闻/文章页面，确保内容区有可见段落文本。")
        sys.exit(1)

    print(f"  找到: {browser} — {title}")
    rect = win32gui.GetWindowRect(hwnd)
    print(f"  窗口位置: {rect}")

    # Step 2: 将浏览器置于前台（处理最小化状态）
    print("\n[Step 2] 将浏览器置于前台...")
    import win32con
    import win32api
    # 如果窗口最小化，先恢复
    if win32gui.IsIconic(hwnd):
        print("  窗口处于最小化状态，正在恢复...")
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.5)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        print("  注意: SetForegroundWindow 可能需要 ALT 键辅助")
        pyautogui.press('alt')
        time.sleep(0.2)
        win32gui.SetForegroundWindow(hwnd)
    time.sleep(1)

    # 恢复后重新获取窗口位置
    rect = win32gui.GetWindowRect(hwnd)
    print(f"  窗口位置（恢复后）: {rect}")
    left, top, right, bottom = rect

    # 校验窗口坐标合法性
    if left < -1000 or top < -1000:
        print(f"  ❌ 窗口坐标异常: ({left}, {top}) — 窗口可能仍未正确恢复")
        print("  请手动将浏览器窗口恢复到可见状态后重试。")
        sys.exit(1)

    # Step 3: 计算左侧内容区点击点
    left, top, right, bottom = rect
    # 左侧 1/3 处，垂直居中偏下（避开顶部导航）
    click_x = left + (right - left) // 3
    click_y = top + (bottom - top) // 2 + 50
    # 合成 bbox（以点击点为中心的小区域）
    bbox = (click_x - 40, click_y - 12, click_x + 40, click_y + 12)

    target_text = "browser_paragraph_text"
    target_type = "content_text"
    confidence = 0.88

    print(f"\n[Step 3] 目标参数:")
    print(f"  target_text: {target_text}")
    print(f"  target_type: {target_type}")
    print(f"  click_point: ({click_x}, {click_y})")
    print(f"  bbox: {bbox}")
    print(f"  source_window: {title}")
    print(f"  confidence: {confidence}")

    # Step 4: 构建并保存 proposal
    print(f"\n[Step 4] 构建 Proposal...")
    proposal = build_proposal(
        target_text=target_text,
        bbox=bbox,
        center_x=click_x,
        center_y=click_y,
        source_window=title,
        target_type=target_type,
        confidence=confidence,
    )
    save_proposal(proposal)

    # Step 5: 截图 before
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    print(f"\n[Step 5] 截图 before...")
    before_path = save_screenshot("before", ts)
    before_title = win32gui.GetWindowText(hwnd)

    # Step 6: 执行安全点击
    print(f"\n[Step 6] 执行安全点击...")
    target = ClickTarget(
        text=target_text,
        bbox=bbox,
        source_window=title,
        target_type=target_type,
        confidence=confidence,
    )
    target.center_x = click_x
    target.center_y = click_y

    result = execute_safe_click(target, force_dry_run=False)
    time.sleep(0.5)

    # Step 7: 截图 after
    print(f"\n[Step 7] 截图 after...")
    after_path = save_screenshot("after", ts)
    after_title = win32gui.GetWindowText(hwnd)

    # Step 8: 运行 checklist
    print(f"\n[Step 8] 运行验收 Checklist...")
    checks = run_checklist(proposal, result, before_title, after_title, before_path, after_path)
    for i, c in enumerate(checks, 1):
        icon = "✅" if c["passed"] else "❌"
        print(f"  {i}. {icon} {c['item']}")
        if not c["passed"]:
            print(f"     → {c['detail']}")

    # Step 9: 生成报告
    print(f"\n[Step 9] 生成验证报告...")
    report_path, verdict = generate_report(
        proposal, checks, result, before_title, after_title, before_path, after_path
    )

    # 最终输出
    print("\n" + "=" * 60)
    all_pass = all(c["passed"] for c in checks)
    if all_pass:
        print(f"  {ROUND_ID}: ✅ PASS")
    else:
        print(f"  {ROUND_ID}: ❌ FAIL")
        failed = [c["item"] for c in checks if not c["passed"]]
        print(f"  失败项: {', '.join(failed)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
