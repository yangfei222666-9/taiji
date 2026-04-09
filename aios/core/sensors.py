# aios/core/sensors.py - 感知探针 v0.2
"""
主动感知外部变化，发布事件到 EventBus。

探针类型：
- FileWatcher: 监控文件/目录变更（基于 mtime 快照对比）
- ProcessMonitor: 监控关键进程状态
- SystemHealth: CPU/内存/磁盘使用率

设计：无守护进程，每次调用 scan() 做一次快照对比。
适合在心跳中调用，不需要后台线程。

v0.2: cooldown 配置，同类事件在冷却期内不重复发布。
"""

import json, time, os, subprocess
from pathlib import Path
from typing import Optional

from core.event_bus import get_bus, PRIORITY_NORMAL, PRIORITY_HIGH, PRIORITY_CRITICAL

STATE_FILE = Path(__file__).resolve().parent.parent / "events" / "sensor_state.json"

# 默认冷却时间（秒）
DEFAULT_COOLDOWNS = {
    "sensor.file.modified": 600,  # 同一文件 10 分钟内不重复报
    "sensor.file.created": 600,
    "sensor.file.deleted": 600,
    "sensor.process.started": 300,  # 进程变化 5 分钟
    "sensor.process.stopped": 300,
    "sensor.system.health": 1800,  # 系统健康告警 30 分钟
    "sensor.network.unreachable": 600,  # 网络不可达 10 分钟
    "sensor.gpu.warn": 1800,  # GPU 温度告警 30 分钟
    "sensor.gpu.critical": 600,  # GPU 严重过热 10 分钟
    "sensor.app.started": 300,  # 应用启动 5 分钟
    "sensor.app.stopped": 300,  # 应用关闭 5 分钟
    "sensor.lol.version_updated": 0,  # LOL 版本更新立即通知
}


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _is_cooled_down(state: dict, topic: str, key: str, cooldowns: dict = None) -> bool:
    """检查某个 topic+key 是否已过冷却期"""
    cd_map = cooldowns or DEFAULT_COOLDOWNS
    cd_seconds = cd_map.get(topic, 0)
    if cd_seconds <= 0:
        return True  # 无冷却限制
    last_fired = state.get("cooldowns", {}).get(f"{topic}:{key}", 0)
    return (time.time() - last_fired) > cd_seconds


def _mark_fired(state: dict, topic: str, key: str):
    """记录事件触发时间"""
    if "cooldowns" not in state:
        state["cooldowns"] = {}
    state["cooldowns"][f"{topic}:{key}"] = time.time()


class FileWatcher:
    """基于 mtime 的文件变更检测"""

    def __init__(self, watch_paths: list[str], extensions: list[str] = None):
        self.watch_paths = [Path(p) for p in watch_paths]
        self.extensions = set(extensions or [".py", ".json", ".jsonl", ".md"])

    def scan(self) -> list[dict]:
        state = _load_state()
        file_state = state.get("file_mtimes", {})
        changes = []

        current = {}
        for wp in self.watch_paths:
            if not wp.exists():
                continue
            targets = [wp] if wp.is_file() else wp.rglob("*")
            for f in targets:
                if not f.is_file():
                    continue
                if f.suffix not in self.extensions:
                    continue
                key = str(f)
                mtime = f.stat().st_mtime
                current[key] = mtime

                old_mtime = file_state.get(key)
                if old_mtime is None:
                    changes.append({"type": "created", "path": key})
                elif mtime > old_mtime:
                    changes.append({"type": "modified", "path": key})

        # 检测删除
        for key in file_state:
            if key not in current:
                # 只报告 watch_paths 下的删除
                for wp in self.watch_paths:
                    if key.startswith(str(wp)):
                        changes.append({"type": "deleted", "path": key})
                        break

        state["file_mtimes"] = current

        bus = get_bus()
        emitted = []
        for c in changes:
            topic = f"sensor.file.{c['type']}"
            if _is_cooled_down(state, topic, c["path"]):
                bus.emit(topic, c, PRIORITY_NORMAL, "file_watcher")
                _mark_fired(state, topic, c["path"])
                emitted.append(c)

        _save_state(state)
        return emitted


class ProcessMonitor:
    """关键进程存活检测"""

    def __init__(self, process_names: list[str] = None):
        self.process_names = process_names or ["openclaw", "python"]

    def scan(self) -> list[dict]:
        state = _load_state()
        prev_procs = set(state.get("running_procs", []))
        events = []

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
                encoding="utf-8",
                errors="replace",
            )
            current_all = (
                set(result.stdout.strip().split("\n"))
                if result.returncode == 0
                else set()
            )
        except Exception:
            current_all = set()

        current_tracked = set()
        for name in self.process_names:
            for proc in current_all:
                if name.lower() in proc.strip().lower():
                    current_tracked.add(proc.strip())

        # 新出现的进程
        appeared = current_tracked - prev_procs
        # 消失的进程
        disappeared = prev_procs - current_tracked

        bus = get_bus()
        for p in appeared:
            topic = "sensor.process.started"
            if _is_cooled_down(state, topic, p):
                ev = {"process": p, "status": "started"}
                bus.emit(topic, ev, PRIORITY_NORMAL, "process_monitor")
                _mark_fired(state, topic, p)
                events.append(ev)

        for p in disappeared:
            topic = "sensor.process.stopped"
            if _is_cooled_down(state, topic, p):
                ev = {"process": p, "status": "stopped"}
                bus.emit(topic, ev, PRIORITY_HIGH, "process_monitor")
                _mark_fired(state, topic, p)
                events.append(ev)

        state["running_procs"] = list(current_tracked)
        _save_state(state)
        return events


class SystemHealth:
    """系统资源使用率"""

    def scan(self) -> dict:
        metrics = {}
        try:
            # 磁盘使用率 (C:)
            import shutil

            total, used, free = shutil.disk_usage("C:\\")
            metrics["disk_c_pct"] = round(used / total * 100, 1)
            metrics["disk_c_free_gb"] = round(free / (1024**3), 1)
        except Exception:
            pass

        try:
            # 内存使用率
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
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                metrics["memory_pct"] = float(result.stdout.strip())
        except Exception:
            pass

        bus = get_bus()
        state = _load_state()
        priority = PRIORITY_NORMAL

        # 告警阈值
        if metrics.get("disk_c_free_gb", 999) < 10:
            priority = PRIORITY_HIGH
        if metrics.get("disk_c_free_gb", 999) < 5:
            priority = PRIORITY_CRITICAL
        if metrics.get("memory_pct", 0) > 90:
            priority = max(priority, PRIORITY_HIGH)

        # 只在有告警级别或冷却期过了才发布
        topic = "sensor.system.health"
        if priority > PRIORITY_NORMAL or _is_cooled_down(state, topic, "system"):
            bus.emit(topic, metrics, priority, "system_health")
            _mark_fired(state, topic, "system")
            _save_state(state)

        return metrics


class NetworkProbe:
    """网络连通性检测"""

    def __init__(self, targets: list[str] = None):
        self.targets = targets or [
            "8.8.8.8",  # Google DNS
            "1.1.1.1",  # Cloudflare DNS
            "api.anthropic.com",  # Claude API
        ]

    def scan(self) -> dict:
        results = {}
        state = _load_state()
        bus = get_bus()

        for target in self.targets:
            try:
                # Windows ping: -n 1 = 1次, -w 2000 = 超时2秒
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "2000", target],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    encoding="utf-8",
                    errors="replace",
                )
                reachable = result.returncode == 0
                results[target] = {"reachable": reachable, "error": None}

                # 检测状态变化
                prev_state = state.get("network_state", {}).get(target, True)
                if not reachable and prev_state:
                    # 从可达变为不可达
                    topic = "sensor.network.unreachable"
                    if _is_cooled_down(state, topic, target):
                        bus.emit(
                            topic, {"target": target}, PRIORITY_HIGH, "network_probe"
                        )
                        _mark_fired(state, topic, target)
                elif reachable and not prev_state:
                    # 从不可达恢复
                    topic = "sensor.network.recovered"
                    bus.emit(
                        topic, {"target": target}, PRIORITY_NORMAL, "network_probe"
                    )

                # 更新状态
                if "network_state" not in state:
                    state["network_state"] = {}
                state["network_state"][target] = reachable

            except Exception as e:
                results[target] = {"reachable": False, "error": str(e)[:100]}

        _save_state(state)
        return results


def scan_all(
    watch_paths: list[str] = None,
    process_names: list[str] = None,
    network_targets: list[str] = None,
    enable_screen: bool = False,
    enable_gpu: bool = True,
    enable_app_monitor: bool = True,
    enable_lol_version: bool = True,
) -> dict:
    """一次性跑所有探针，返回汇总

    enable_screen: 是否启用屏幕感知（默认关闭，按需开启）
    enable_gpu: 是否启用 GPU 监控（默认开启）
    enable_app_monitor: 是否启用应用监控（默认开启）
    enable_lol_version: 是否启用 LOL 版本监控（默认开启）
    """
    results = {}

    fw = FileWatcher(
        watch_paths
        or [
            str(Path(__file__).resolve().parent.parent),  # aios/
            str(
                Path(__file__).resolve().parent.parent.parent / "autolearn"
            ),  # autolearn/
        ]
    )
    results["file_changes"] = fw.scan()

    pm = ProcessMonitor(process_names or ["openclaw", "python", "node"])
    results["process_events"] = pm.scan()

    sh = SystemHealth()
    results["system_health"] = sh.scan()

    np = NetworkProbe(network_targets)
    results["network"] = np.scan()

    # GPU 监控
    if enable_gpu:
        gm = GPUMonitor(temp_warn=75, temp_crit=85)
        results["gpu"] = gm.scan()

    # 应用监控
    if enable_app_monitor:
        am = AppMonitor()
        results["apps"] = am.scan()

    # LOL 版本监控
    if enable_lol_version:
        lvm = LOLVersionMonitor()
        results["lol_version"] = lvm.scan()

    # 屏幕感知（可选）
    if enable_screen:
        try:
            from core.screen_sensor import scan_screen

            results["screen_changes"] = scan_screen(interval=30, threshold=0.05)
        except Exception as e:
            results["screen_changes"] = {"error": str(e)[:100]}

    return results


class AppMonitor:
    """应用启动状态监控"""

    def __init__(self, apps: dict = None):
        """
        apps: {app_name: executable_name}
        例如: {"QQ音乐": "QQMusic", "英雄联盟": "LeagueClient"}
        """
        self.apps = apps or {
            "QQ音乐": "QQMusic",
            "英雄联盟": "LeagueClient",
            "WeGame": "WeGame",
        }

    def scan(self) -> dict:
        state = _load_state()
        prev_apps = state.get("app_status", {})
        current_apps = {}
        events = []
        bus = get_bus()

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
                encoding="utf-8",
                errors="replace",
            )
            running_procs = (
                set(result.stdout.strip().split("\n"))
                if result.returncode == 0
                else set()
            )
        except Exception:
            running_procs = set()

        for app_name, exe_name in self.apps.items():
            is_running = any(
                exe_name.lower() in proc.strip().lower() for proc in running_procs
            )
            current_apps[app_name] = is_running

            prev_status = prev_apps.get(app_name, False)

            if is_running and not prev_status:
                # 应用启动
                topic = "sensor.app.started"
                if _is_cooled_down(state, topic, app_name):
                    ev = {"app": app_name, "status": "started"}
                    bus.emit(topic, ev, PRIORITY_NORMAL, "app_monitor")
                    _mark_fired(state, topic, app_name)
                    events.append(ev)

            elif not is_running and prev_status:
                # 应用关闭
                topic = "sensor.app.stopped"
                if _is_cooled_down(state, topic, app_name):
                    ev = {"app": app_name, "status": "stopped"}
                    bus.emit(topic, ev, PRIORITY_NORMAL, "app_monitor")
                    _mark_fired(state, topic, app_name)
                    events.append(ev)

        state["app_status"] = current_apps
        _save_state(state)
        return {"apps": current_apps, "events": events}


class LOLVersionMonitor:
    """LOL 版本更新检测"""

    def __init__(self, lol_path: str = None):
        self.lol_path = lol_path or "E:\\WeGameApps\\英雄联盟"

    def scan(self) -> dict:
        state = _load_state()
        bus = get_bus()
        result = {"version": None, "updated": False, "error": None}

        try:
            # 从 LeagueClient.exe 读取版本（最可靠）
            exe_path = Path(self.lol_path) / "LeagueClient" / "LeagueClient.exe"
            if not exe_path.exists():
                result["error"] = f"LOL not found at {self.lol_path}"
                return result

            ps_cmd = f"(Get-Item '{exe_path}').VersionInfo.FileVersion"
            ps_result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
            )

            if ps_result.returncode != 0 or not ps_result.stdout.strip():
                result["error"] = "Cannot read LOL version"
                return result

            current_version = ps_result.stdout.strip()
            result["version"] = current_version
            prev_version = state.get("lol_version")

            if prev_version and prev_version != current_version:
                # 版本更新
                topic = "sensor.lol.version_updated"
                ev = {
                    "old_version": prev_version,
                    "new_version": current_version,
                    "message": f"LOL updated: {prev_version} → {current_version}",
                }
                bus.emit(topic, ev, PRIORITY_HIGH, "lol_version_monitor")
                result["updated"] = True

            state["lol_version"] = current_version
            _save_state(state)

        except Exception as e:
            result["error"] = str(e)[:100]

        return result


class GPUMonitor:
    """GPU 温度和使用率监控（NVIDIA GPU）"""

    def __init__(self, temp_warn=75, temp_crit=85):
        self.temp_warn = temp_warn
        self.temp_crit = temp_crit

    def scan(self) -> dict:
        results = {"available": False, "temp": None, "usage": None, "error": None}
        state = _load_state()
        bus = get_bus()

        try:
            # 使用 nvidia-smi 查询 GPU 信息
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=temperature.gpu,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    temp = int(parts[0].strip())
                    usage = int(parts[1].strip())

                    results["available"] = True
                    results["temp"] = temp
                    results["usage"] = usage

                    # 温度告警
                    prev_temp = state.get("gpu_temp", 0)

                    if temp >= self.temp_crit:
                        topic = "sensor.gpu.critical"
                        if _is_cooled_down(state, topic, "gpu0"):
                            bus.emit(
                                topic,
                                {
                                    "temp": temp,
                                    "usage": usage,
                                    "message": f"GPU temperature critical: {temp}C",
                                },
                                PRIORITY_CRITICAL,
                                "gpu_monitor",
                            )
                            state.setdefault("cooldowns", {})[
                                f"{topic}:gpu0"
                            ] = time.time()

                    elif temp >= self.temp_warn and prev_temp < self.temp_warn:
                        topic = "sensor.gpu.warn"
                        if _is_cooled_down(state, topic, "gpu0"):
                            bus.emit(
                                topic,
                                {
                                    "temp": temp,
                                    "usage": usage,
                                    "message": f"GPU temperature high: {temp}C",
                                },
                                PRIORITY_HIGH,
                                "gpu_monitor",
                            )
                            state.setdefault("cooldowns", {})[
                                f"{topic}:gpu0"
                            ] = time.time()

                    state["gpu_temp"] = temp
                    state["gpu_usage"] = usage

        except FileNotFoundError:
            results["error"] = "nvidia-smi not found (NVIDIA GPU drivers not installed)"
        except Exception as e:
            results["error"] = str(e)[:100]

        _save_state(state)
        return results


if __name__ == "__main__":
    r = scan_all()
    print(json.dumps(r, ensure_ascii=False, indent=2))
