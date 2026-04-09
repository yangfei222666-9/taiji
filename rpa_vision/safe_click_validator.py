"""
Safe Click Validator - 闸门内真点击验证（统一版）

核心改动：
  - 删除本地重复的闸门逻辑
  - 统一使用 aios.core.safe_click 的四道闸门
  - 保留验证流程编排 + 截图 + 报告输出
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pyautogui
import win32gui
from PIL import ImageGrab

# 确保能 import aios.core.safe_click
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aios.core.safe_click import (
    ClickTarget,
    execute_safe_click,
    evaluate_click,
    CONFIDENCE_THRESHOLD,
)

# 截图目录
DEBUG_DIR = Path("debug_screenshots")


class SafeClickValidator:
    def __init__(self, target_window_title=None, dry_run=False):
        self.target_window_title = target_window_title
        self.dry_run = dry_run
        self.window_hwnd = None
        self.window_rect = None

        if target_window_title:
            self._bind_window()

    def _bind_window(self):
        """窗口绑定：查找并锁定目标窗口"""
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if self.target_window_title in title:
                    windows.append((hwnd, title))

        windows = []
        win32gui.EnumWindows(callback, windows)

        if not windows:
            raise ValueError(f"Window not found: {self.target_window_title}")

        self.window_hwnd = windows[0][0]
        self.window_rect = win32gui.GetWindowRect(self.window_hwnd)

        print(f"窗口绑定成功: {windows[0][1]}")
        print(f"  窗口位置: {self.window_rect}")

    def execute_safe_click(self, x, y, target_text="", target_type="static_text",
                           confidence=0.85):
        """执行安全点击 —— 委托给 aios.core.safe_click 的四道闸门"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # 构造 ClickTarget（统一数据结构）
        target = ClickTarget(
            text=target_text,
            bbox=(x - 20, y - 10, x + 20, y + 10),  # 合成 bbox
            source_window=self.target_window_title or "",
            target_type=target_type,
            confidence=confidence,
        )
        # 覆盖自动计算的中心点为精确坐标
        target.center_x = x
        target.center_y = y

        # 截图前状态
        DEBUG_DIR.mkdir(exist_ok=True)
        before_screenshot = ImageGrab.grab()
        before_path = DEBUG_DIR / f"before_click_{ts}.png"
        before_screenshot.save(str(before_path))

        before_title = ""
        if self.window_hwnd:
            try:
                before_title = win32gui.GetWindowText(self.window_hwnd)
            except Exception:
                pass

        # 通过统一闸门执行
        result = execute_safe_click(target, force_dry_run=self.dry_run)

        time.sleep(0.5)

        # 截图后状态
        after_screenshot = ImageGrab.grab()
        after_path = DEBUG_DIR / f"after_click_{ts}.png"
        after_screenshot.save(str(after_path))

        after_title = ""
        if self.window_hwnd:
            try:
                after_title = win32gui.GetWindowText(self.window_hwnd)
            except Exception:
                pass

        # 输出结果
        executed = result.get("executed", False)
        status = result.get("status", "unknown")

        if executed:
            print(f"点击成功 ({x}, {y})")
            print(f"  窗口标题变化: {before_title} -> {after_title}")
            return True, "success"
        elif status == "dry_run":
            reason = result.get("dry_run_reason", "")
            print(f"[DRY-RUN] {reason}")
            return self.dry_run, f"dry_run: {reason}"
        else:
            reason = result.get("dry_run_reason", result.get("error", "rejected"))
            print(f"点击被拒: {reason}")
            return False, reason


def run_validation():
    """运行第一轮闸门内真点击验证（自动化）"""
    print("=" * 60)
    print("Safe Click Validator - 闸门内真点击验证（统一四闸版）")
    print(f"置信度阈值: {CONFIDENCE_THRESHOLD}")
    print("=" * 60)

    print("\n目标选择标准（4 条硬约束）：")
    print("1. 内容区，不在顶部/底部/右上角")
    print("2. OCR 类型属于安全白名单")
    print("3. 文本不含任何动作词")
    print("4. OCR 置信度 >= 阈值")

    # 自动打开记事本
    print("\n正在启动记事本...")
    subprocess.Popen(["notepad.exe"])
    time.sleep(2)

    # 初始化验证器
    validator = None
    for title in ["记事本", "Notepad", "无标题"]:
        try:
            validator = SafeClickValidator(target_window_title=title, dry_run=False)
            break
        except ValueError:
            continue

    if not validator:
        print("记事本窗口未找到，请手动打开记事本后重试")
        return

    # 将记事本窗口置于前台
    win32gui.SetForegroundWindow(validator.window_hwnd)
    time.sleep(0.5)

    # 获取窗口中心点（内容区）
    left, top, right, bottom = validator.window_rect
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2 + 50

    print(f"\n测试目标：窗口中心点（内容区）")
    print(f"  坐标: ({center_x}, {center_y})")
    print(f"  目标文本: 测试文本")
    print(f"  目标类型: content_text")
    print(f"  置信度: 0.90")

    # 执行安全点击
    print("\n执行安全点击...")
    success, message = validator.execute_safe_click(
        x=center_x,
        y=center_y,
        target_text="测试文本",
        target_type="content_text",
        confidence=0.90,
    )

    if success:
        print(f"\n验证通过: {message}")
    else:
        print(f"\n验证失败: {message}")

    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)


if __name__ == "__main__":
    run_validation()
