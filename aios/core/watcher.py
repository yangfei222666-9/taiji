# aios/core/watcher.py - 主动感知守护进程 v1.0
"""
基于 watchdog 的实时文件系统监听 + 系统资源监控。

功能：
1. 文件系统实时监听（watchdog）
2. 系统资源监控（磁盘/内存/CPU）
3. 网络连通性探测
4. 关键进程监控
5. 所有事件通过 EventBus 发布

CLI:
    python -m aios.core.watcher              # 前台运行
    python -m aios.core.watcher --daemon     # 后台运行（Windows 服务模式）
"""

import sys, time, json, subprocess, threading, signal
from pathlib import Path
from typing import Optional

# 添加 aios 到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print("❌ watchdog 未安装，请运行: pip install watchdog", file=sys.stderr)
    sys.exit(1)

from core.event_bus import get_bus, PRIORITY_NORMAL, PRIORITY_HIGH, PRIORITY_CRITICAL
from core.config import load as load_config

# ── 配置 ──
DEFAULT_WATCH_DIRS = [
    "memory/",
    "aios/events/",
    "autolearn/data/",
]
DEFAULT_CHECK_INTERVAL = 60  # 资源检查间隔（秒）
DEFAULT_THRESHOLDS = {
    "disk_pct": 90,
    "memory_pct": 90,
    "disk_free_gb": 5,
}


class WatcherConfig:
    """从 config.yaml 或默认值加载配置"""

    def __init__(self):
        cfg = load_config()

        # 监听目录（相对于 workspace）
        workspace = Path(__file__).resolve().parent.parent.parent

        # 从 config 读取或使用默认值
        watch_dirs_str = cfg.get("watcher.watch_dirs", "")
        if watch_dirs_str:
            watch_dirs = [d.strip() for d in watch_dirs_str.split(",")]
        else:
            watch_dirs = DEFAULT_WATCH_DIRS

        self.watch_paths = [workspace / d for d in watch_dirs]

        # 检查间隔
        self.check_interval = int(
            cfg.get("watcher.check_interval_sec", str(DEFAULT_CHECK_INTERVAL))
        )

        # 阈值
        self.disk_pct_threshold = int(
            cfg.get("watcher.thresholds.disk_pct", str(DEFAULT_THRESHOLDS["disk_pct"]))
        )
        self.memory_pct_threshold = int(
            cfg.get(
                "watcher.thresholds.memory_pct", str(DEFAULT_THRESHOLDS["memory_pct"])
            )
        )
        self.disk_free_gb_threshold = int(
            cfg.get(
                "watcher.thresholds.disk_free_gb",
                str(DEFAULT_THRESHOLDS["disk_free_gb"]),
            )
        )

        # 网络探测目标
        targets_str = cfg.get("watcher.network_targets", "")
        if targets_str:
            self.network_targets = [t.strip() for t in targets_str.split(",")]
        else:
            self.network_targets = ["8.8.8.8", "1.1.1.1"]

        # 进程监控
        procs_str = cfg.get("watcher.process_names", "")
        if procs_str:
            self.process_names = [p.strip() for p in procs_str.split(",")]
        else:
            self.process_names = ["python", "node"]


# ── 文件系统监听 ──


class WatcherEventHandler(FileSystemEventHandler):
    """watchdog 事件处理器"""

    def __init__(self):
        super().__init__()
        self.bus = get_bus()
        self._cooldown = {}  # 防抖：同一文件 1 秒内只触发一次
        self._cooldown_sec = 1.0

    def _should_emit(self, path: str) -> bool:
        """防抖检查"""
        now = time.time()
        last = self._cooldown.get(path, 0)
        if now - last < self._cooldown_sec:
            return False
        self._cooldown[path] = now
        return True

    def _emit_event(self, event_type: str, src_path: str, dest_path: str = None):
        """发布文件事件"""
        if not self._should_emit(src_path):
            return

        payload = {
            "path": str(src_path),
            "type": event_type,
        }
        if dest_path:
            payload["dest_path"] = str(dest_path)

        self.bus.emit(f"watcher.file.{event_type}", payload, PRIORITY_NORMAL, "watcher")

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self._emit_event("created", event.src_path)

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self._emit_event("modified", event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self._emit_event("deleted", event.src_path)

    def on_moved(self, event: FileSystemEvent):
        if not event.is_directory:
            self._emit_event("moved", event.src_path, event.dest_path)


# ── 系统资源监控 ──


class SystemMonitor:
    """系统资源监控（磁盘/内存/CPU）"""

    def __init__(self, config: WatcherConfig):
        self.config = config
        self.bus = get_bus()
        self._last_alert = {}  # 防止重复告警
        self._alert_cooldown = 600  # 同类告警 10 分钟内不重复

    def _should_alert(self, key: str) -> bool:
        """告警冷却检查"""
        now = time.time()
        last = self._last_alert.get(key, 0)
        if now - last < self._alert_cooldown:
            return False
        self._last_alert[key] = now
        return True

    def check(self):
        """执行一次系统检查"""
        metrics = {}
        alerts = []

        # 磁盘使用率
        try:
            import shutil

            total, used, free = shutil.disk_usage("C:\\")
            disk_pct = round(used / total * 100, 1)
            disk_free_gb = round(free / (1024**3), 1)

            metrics["disk_c_pct"] = disk_pct
            metrics["disk_c_free_gb"] = disk_free_gb

            # 告警检查
            if disk_pct > self.config.disk_pct_threshold and self._should_alert(
                "disk_pct"
            ):
                alerts.append(
                    {
                        "type": "disk_usage_high",
                        "severity": "CRIT" if disk_pct > 95 else "WARN",
                        "value": disk_pct,
                        "threshold": self.config.disk_pct_threshold,
                    }
                )

            if (
                disk_free_gb < self.config.disk_free_gb_threshold
                and self._should_alert("disk_free")
            ):
                alerts.append(
                    {
                        "type": "disk_space_low",
                        "severity": "CRIT",
                        "value": disk_free_gb,
                        "threshold": self.config.disk_free_gb_threshold,
                    }
                )
        except Exception as e:
            metrics["disk_error"] = str(e)[:200]

        # 内存使用率
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_OperatingSystem | "
                    "Select-Object @{N='pct';E={[math]::Round(($_.TotalVisibleMemorySize - $_.FreePhysicalMemory) / $_.TotalVisibleMemorySize * 100, 1)}}).pct",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                memory_pct = float(result.stdout.strip())
                metrics["memory_pct"] = memory_pct

                if (
                    memory_pct > self.config.memory_pct_threshold
                    and self._should_alert("memory_pct")
                ):
                    alerts.append(
                        {
                            "type": "memory_usage_high",
                            "severity": "CRIT" if memory_pct > 95 else "WARN",
                            "value": memory_pct,
                            "threshold": self.config.memory_pct_threshold,
                        }
                    )
        except Exception as e:
            metrics["memory_error"] = str(e)[:200]

        # 发布指标事件
        self.bus.emit("watcher.system.metrics", metrics, PRIORITY_NORMAL, "watcher")

        # 发布告警事件
        for alert in alerts:
            priority = (
                PRIORITY_CRITICAL if alert["severity"] == "CRIT" else PRIORITY_HIGH
            )
            self.bus.emit(
                f"watcher.system.alert.{alert['type']}", alert, priority, "watcher"
            )


# ── 网络连通性探测 ──


class NetworkMonitor:
    """网络连通性探测"""

    def __init__(self, config: WatcherConfig):
        self.config = config
        self.bus = get_bus()
        self._state = {}  # 记录上次状态

    def check(self):
        """执行一次网络检查"""
        for target in self.config.network_targets:
            try:
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "2000", target],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                reachable = result.returncode == 0

                prev_state = self._state.get(target, True)

                # 状态变化时发布事件
                if not reachable and prev_state:
                    # 从可达变为不可达
                    self.bus.emit(
                        "watcher.network.unreachable",
                        {"target": target},
                        PRIORITY_CRITICAL,
                        "watcher",
                    )
                elif reachable and not prev_state:
                    # 从不可达恢复
                    self.bus.emit(
                        "watcher.network.recovered",
                        {"target": target},
                        PRIORITY_NORMAL,
                        "watcher",
                    )

                self._state[target] = reachable

            except Exception as e:
                # 探测失败视为不可达
                if self._state.get(target, True):
                    self.bus.emit(
                        "watcher.network.unreachable",
                        {"target": target, "error": str(e)[:100]},
                        PRIORITY_CRITICAL,
                        "watcher",
                    )
                    self._state[target] = False


# ── 进程监控 ──


class ProcessMonitor:
    """关键进程监控"""

    def __init__(self, config: WatcherConfig):
        self.config = config
        self.bus = get_bus()
        self._state = set()  # 上次检测到的进程

    def check(self):
        """执行一次进程检查"""
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Process | Select-Object -ExpandProperty Name -Unique",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            current_all = (
                set(result.stdout.strip().split("\n"))
                if result.returncode == 0
                else set()
            )
        except Exception:
            return

        # 过滤关键进程
        current_tracked = set()
        for name in self.config.process_names:
            for proc in current_all:
                if name.lower() in proc.strip().lower():
                    current_tracked.add(proc.strip())

        # 检测变化
        appeared = current_tracked - self._state
        disappeared = self._state - current_tracked

        for proc in appeared:
            self.bus.emit(
                "watcher.process.started", {"process": proc}, PRIORITY_NORMAL, "watcher"
            )

        for proc in disappeared:
            self.bus.emit(
                "watcher.process.stopped", {"process": proc}, PRIORITY_HIGH, "watcher"
            )

        self._state = current_tracked


# ── 主守护进程 ──


class WatcherDaemon:
    """主守护进程"""

    def __init__(self, config: WatcherConfig):
        self.config = config
        self.observer = Observer()
        self.system_monitor = SystemMonitor(config)
        self.network_monitor = NetworkMonitor(config)
        self.process_monitor = ProcessMonitor(config)
        self.running = False
        self._check_thread: Optional[threading.Thread] = None

    def start(self):
        """启动守护进程"""
        print("🚀 AIOS Watcher 启动中...")

        # 启动文件系统监听
        handler = WatcherEventHandler()
        for path in self.config.watch_paths:
            if path.exists():
                self.observer.schedule(handler, str(path), recursive=True)
                print(f"📁 监听: {path}")
            else:
                print(f"⚠️  路径不存在: {path}")

        self.observer.start()

        # 启动资源检查线程
        self.running = True
        self._check_thread = threading.Thread(target=self._check_loop, daemon=True)
        self._check_thread.start()

        print(f"✅ Watcher 已启动（检查间隔: {self.config.check_interval}s）")
        print("按 Ctrl+C 停止")

    def _check_loop(self):
        """资源检查循环"""
        while self.running:
            try:
                self.system_monitor.check()
                self.network_monitor.check()
                self.process_monitor.check()
            except Exception as e:
                print(f"❌ 检查失败: {e}", file=sys.stderr)

            time.sleep(self.config.check_interval)

    def stop(self):
        """停止守护进程"""
        print("\n🛑 正在停止 Watcher...")
        self.running = False
        self.observer.stop()
        self.observer.join()
        if self._check_thread:
            self._check_thread.join(timeout=5)
        print("✅ Watcher 已停止")

    def run_forever(self):
        """前台运行"""
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


# ── CLI ──


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AIOS Watcher - 主动感知守护进程")
    parser.add_argument(
        "--daemon", action="store_true", help="后台运行（Windows 服务模式）"
    )
    parser.add_argument("--config", help="配置文件路径（默认: aios/config.yaml）")
    args = parser.parse_args()

    config = WatcherConfig()
    daemon = WatcherDaemon(config)

    if args.daemon:
        # Windows 后台模式：重定向输出到日志文件
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"watcher_{time.strftime('%Y%m%d_%H%M%S')}.log"

        sys.stdout = open(log_file, "w", encoding="utf-8")
        sys.stderr = sys.stdout

        print(f"🔧 后台模式启动，日志: {log_file}")
        daemon.run_forever()
    else:
        # 前台模式
        daemon.run_forever()


if __name__ == "__main__":
    main()
