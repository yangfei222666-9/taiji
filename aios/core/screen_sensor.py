# aios/core/screen_sensor.py - 屏幕感知模块 v0.1
"""
屏幕截图与变化检测，发布事件到 EventBus。

功能：
- ScreenCapture: 截屏基础能力（保存/base64/差异对比）
- ScreenMonitor: 实时监控屏幕变化，检测通知弹窗

设计：无守护进程，每次调用 scan() 做一次截图对比。
适合在心跳中调用，不需要后台线程。

依赖: mss, Pillow
"""

import json
import time
import base64
from pathlib import Path
from typing import Optional
from io import BytesIO

try:
    import mss
    import numpy as np
    from PIL import Image, ImageChops
except ImportError as e:
    raise ImportError(f"缺少依赖: {e}. 请安装: pip install mss Pillow numpy") from e

from core.event_bus import get_bus, PRIORITY_NORMAL, PRIORITY_HIGH

STATE_FILE = Path(__file__).resolve().parent.parent / "events" / "sensor_state.json"
SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "events" / "screenshots"

# 默认冷却时间（秒）
DEFAULT_COOLDOWNS = {
    "sensor.screen.changed": 60,
    "sensor.screen.notification": 120,
    "sensor.screen.captured": 0,  # 无冷却
}


def _load_state() -> dict:
    """加载传感器状态"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict):
    """保存传感器状态"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _is_cooled_down(state: dict, topic: str, key: str = "default") -> bool:
    """检查某个 topic+key 是否已过冷却期"""
    cd_seconds = DEFAULT_COOLDOWNS.get(topic, 0)
    if cd_seconds <= 0:
        return True
    last_fired = state.get("cooldowns", {}).get(f"{topic}:{key}", 0)
    return (time.time() - last_fired) > cd_seconds


def _mark_fired(state: dict, topic: str, key: str = "default"):
    """记录事件触发时间"""
    if "cooldowns" not in state:
        state["cooldowns"] = {}
    state["cooldowns"][f"{topic}:{key}"] = time.time()


class ScreenCapture:
    """截屏基础能力"""

    def __init__(self):
        self.sct = mss.mss()
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    def capture(self, monitor: int = 0, region: tuple = None) -> Path:
        """截取屏幕，保存到 aios/events/screenshots/，返回路径

        Args:
            monitor: 0=全屏, 1=主显示器, 2=第二显示器
            region: (left, top, width, height) 可选区域截取

        Returns:
            截图文件路径
        """
        try:
            # 选择监视器
            if region:
                mon = {
                    "left": region[0],
                    "top": region[1],
                    "width": region[2],
                    "height": region[3],
                }
            elif monitor == 0:
                mon = self.sct.monitors[0]  # 全屏（所有显示器）
            else:
                mon = self.sct.monitors[min(monitor, len(self.sct.monitors) - 1)]

            # 截图
            sct_img = self.sct.grab(mon)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # 保存
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"screen_{timestamp}.png"
            filepath = SCREENSHOT_DIR / filename
            img.save(filepath, "PNG")

            # 清理旧截图（保留最近50张）
            self._cleanup_old_screenshots()

            return filepath

        except Exception as e:
            raise RuntimeError(f"截屏失败: {e}") from e

    def capture_base64(self, monitor: int = 0, region: tuple = None) -> str:
        """截屏并返回 base64 编码（用于直接传给视觉模型）

        Args:
            monitor: 0=全屏, 1=主显示器, 2=第二显示器
            region: (left, top, width, height) 可选区域截取

        Returns:
            base64 编码的 PNG 图片
        """
        try:
            # 选择监视器
            if region:
                mon = {
                    "left": region[0],
                    "top": region[1],
                    "width": region[2],
                    "height": region[3],
                }
            elif monitor == 0:
                mon = self.sct.monitors[0]
            else:
                mon = self.sct.monitors[min(monitor, len(self.sct.monitors) - 1)]

            # 截图
            sct_img = self.sct.grab(mon)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # 转 base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_bytes = buffer.getvalue()
            return base64.b64encode(img_bytes).decode("utf-8")

        except Exception as e:
            raise RuntimeError(f"截屏失败: {e}") from e

    def diff(self, img1_path: Path, img2_path: Path, threshold: float = 0.05) -> dict:
        """对比两张截图差异

        Args:
            img1_path: 第一张图片路径
            img2_path: 第二张图片路径
            threshold: 像素变化比例阈值

        Returns:
            {"changed": bool, "diff_ratio": float, "diff_regions": [...]}
        """
        try:
            img1 = Image.open(img1_path).convert("RGB")
            img2 = Image.open(img2_path).convert("RGB")

            # 尺寸不同直接判定为变化
            if img1.size != img2.size:
                return {
                    "changed": True,
                    "diff_ratio": 1.0,
                    "diff_regions": [],
                    "reason": "size_mismatch",
                }

            # 计算像素差异
            diff = ImageChops.difference(img1, img2)
            diff_gray = diff.convert("L")

            # 统计变化像素
            pixels = np.array(diff_gray)
            total_pixels = pixels.size
            changed_pixels = np.sum(pixels > 30)  # 阈值30，过滤微小变化
            diff_ratio = changed_pixels / total_pixels if total_pixels > 0 else 0

            # 检测变化区域（简单分块检测）
            diff_regions = self._detect_diff_regions(diff_gray)

            return {
                "changed": diff_ratio > threshold,
                "diff_ratio": round(diff_ratio, 4),
                "diff_regions": diff_regions,
            }

        except Exception as e:
            raise RuntimeError(f"图片对比失败: {e}") from e

    def _detect_diff_regions(
        self, diff_gray: Image.Image, block_size: int = 100
    ) -> list[dict]:
        """检测变化区域（分块检测）"""
        width, height = diff_gray.size
        regions = []

        for y in range(0, height, block_size):
            for x in range(0, width, block_size):
                box = (x, y, min(x + block_size, width), min(y + block_size, height))
                block = diff_gray.crop(box)
                block_array = np.array(block)
                changed = np.sum(block_array > 30)
                ratio = changed / block_array.size if block_array.size > 0 else 0

                if ratio > 0.1:  # 区块内10%以上像素变化
                    regions.append({"region": box, "change_ratio": round(ratio, 3)})

        return regions

    def _cleanup_old_screenshots(self, keep: int = 50):
        """清理旧截图，保留最近 keep 张"""
        try:
            screenshots = sorted(
                SCREENSHOT_DIR.glob("screen_*.png"), key=lambda p: p.stat().st_mtime
            )
            if len(screenshots) > keep:
                for old_file in screenshots[:-keep]:
                    old_file.unlink(missing_ok=True)
        except Exception:
            pass  # 清理失败不影响主流程


class ScreenMonitor:
    """实时监控屏幕变化"""

    def __init__(self, interval: int = 30, threshold: float = 0.05):
        """
        Args:
            interval: 截屏间隔秒数
            threshold: 变化检测阈值
        """
        self.interval = interval
        self.threshold = threshold
        self.capture = ScreenCapture()

    def scan(self) -> list[dict]:
        """单次扫描（心跳调用），对比上次截图

        如果变化超阈值，发布 sensor.screen.changed 事件

        Returns:
            变化列表
        """
        state = _load_state()
        changes = []

        try:
            # 检查扫描间隔
            last_scan = state.get("last_scan_time", 0)
            if time.time() - last_scan < self.interval:
                return []  # 未到扫描时间

            # 截取当前屏幕
            current_path = self.capture.capture(monitor=1)  # 主显示器

            # 发布截图事件
            bus = get_bus()
            bus.emit(
                "sensor.screen.captured",
                {"path": str(current_path)},
                PRIORITY_NORMAL,
                "screen_monitor",
            )

            # 对比上次截图
            last_path = state.get("last_screenshot_path")
            if last_path and Path(last_path).exists():
                diff_result = self.capture.diff(
                    Path(last_path), current_path, self.threshold
                )

                if diff_result["changed"]:
                    change_event = {
                        "current": str(current_path),
                        "previous": last_path,
                        "diff_ratio": diff_result["diff_ratio"],
                        "regions": diff_result["diff_regions"],
                    }
                    changes.append(change_event)

                    # 发布变化事件（带冷却）
                    topic = "sensor.screen.changed"
                    if _is_cooled_down(state, topic):
                        bus.emit(topic, change_event, PRIORITY_NORMAL, "screen_monitor")
                        _mark_fired(state, topic)

                    # 检测通知弹窗
                    notifications = self.detect_notification(current_path)
                    if notifications:
                        notif_topic = "sensor.screen.notification"
                        if _is_cooled_down(state, notif_topic):
                            bus.emit(
                                notif_topic,
                                {
                                    "notifications": notifications,
                                    "screenshot": str(current_path),
                                },
                                PRIORITY_HIGH,
                                "screen_monitor",
                            )
                            _mark_fired(state, notif_topic)

            # 更新状态
            state["last_screenshot_path"] = str(current_path)
            state["last_scan_time"] = time.time()
            _save_state(state)

        except Exception as e:
            # 扫描失败不崩溃，记录错误
            bus = get_bus()
            bus.emit(
                "sensor.screen.error",
                {"error": str(e)[:200]},
                PRIORITY_HIGH,
                "screen_monitor",
            )

        return changes

    def detect_notification(self, img_path: Path) -> list[dict]:
        """检测屏幕上的通知弹窗区域（右下角/右上角）

        基于像素分析，不依赖 OCR

        Args:
            img_path: 截图路径

        Returns:
            [{"region": (x,y,w,h), "type": "notification", "position": "bottom-right"}]
        """
        try:
            img = Image.open(img_path).convert("RGB")
            width, height = img.size
            notifications = []

            # 检测区域：右下角和右上角
            check_regions = [
                {
                    "name": "bottom-right",
                    "box": (width - 400, height - 200, width, height),
                },
                {"name": "top-right", "box": (width - 400, 0, width, 200)},
            ]

            for region_info in check_regions:
                box = region_info["box"]
                region = img.crop(box)

                # 简单的通知检测：检查区域内是否有明显的矩形边界
                # 通过检测边缘像素的一致性
                if self._has_notification_pattern(region):
                    notifications.append(
                        {
                            "region": box,
                            "type": "notification",
                            "position": region_info["name"],
                        }
                    )

            return notifications

        except Exception:
            return []

    def _has_notification_pattern(self, region: Image.Image) -> bool:
        """检测区域是否有通知弹窗特征

        通知弹窗通常有：
        1. 明显的矩形边界
        2. 与背景色差异较大
        3. 内部有文字区域（颜色变化）
        """
        try:
            # 转灰度
            gray = region.convert("L")
            pixels = np.array(gray)

            if pixels.size == 0:
                return False

            # 计算像素标准差（通知区域通常有较高的对比度）
            mean = np.mean(pixels)
            std_dev = np.std(pixels)

            # 标准差大于30表示有明显的内容变化
            if std_dev < 30:
                return False

            # 检测边缘：上下左右边缘的像素一致性
            width, height = region.size
            if width < 50 or height < 50:
                return False

            # 简单边缘检测：检查四周是否有连续的相似像素（边框）
            edges = []
            edges.append(np.array(gray.crop((0, 0, width, 5))))  # 上边
            edges.append(np.array(gray.crop((0, height - 5, width, height))))  # 下边
            edges.append(np.array(gray.crop((0, 0, 5, height))))  # 左边
            edges.append(np.array(gray.crop((width - 5, 0, width, height))))  # 右边

            edge_pixels = np.concatenate([e.flatten() for e in edges])
            edge_std = np.std(edge_pixels)

            # 边缘标准差小（一致性高）+ 内容标准差大 = 可能是通知
            return edge_std < 20 and std_dev > 40

        except Exception:
            return False


def scan_screen(interval: int = 30, threshold: float = 0.05) -> list[dict]:
    """便捷函数：执行一次屏幕扫描"""
    monitor = ScreenMonitor(interval, threshold)
    return monitor.scan()


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "capture"

    if cmd == "capture":
        # 截一张图，打印路径
        cap = ScreenCapture()
        path = cap.capture(monitor=1)
        print(f"截图已保存: {path}")

    elif cmd == "scan":
        # 执行一次扫描对比
        changes = scan_screen(interval=0)  # 忽略间隔限制
        if changes:
            print(f"检测到 {len(changes)} 处变化:")
            print(json.dumps(changes, ensure_ascii=False, indent=2))
        else:
            print("未检测到变化")

    elif cmd == "monitor":
        # 连续监控（打印变化）
        print("开始监控屏幕变化（Ctrl+C 退出）...")
        monitor = ScreenMonitor(interval=5, threshold=0.05)
        try:
            while True:
                changes = monitor.scan()
                if changes:
                    print(f"[{time.strftime('%H:%M:%S')}] 检测到变化:")
                    for c in changes:
                        print(
                            f"  - 变化率: {c['diff_ratio']:.2%}, 区域数: {len(c['regions'])}"
                        )
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n监控已停止")

    elif cmd == "diff" and len(sys.argv) >= 4:
        # 对比两张图
        img1 = Path(sys.argv[2])
        img2 = Path(sys.argv[3])
        if not img1.exists() or not img2.exists():
            print("错误: 图片文件不存在")
            sys.exit(1)

        cap = ScreenCapture()
        result = cap.diff(img1, img2)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print("用法:")
        print("  python screen_sensor.py capture          # 截一张图")
        print("  python screen_sensor.py scan             # 执行一次扫描对比")
        print("  python screen_sensor.py monitor          # 连续监控")
        print("  python screen_sensor.py diff img1 img2   # 对比两张图")
