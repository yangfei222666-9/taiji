#!/usr/bin/env python3
"""
AIOS 外部系统集成模块
外部系统集成注册表，封装常用自动化流程
"""

import json
import subprocess
import platform
from pathlib import Path
from typing import List, Dict, Optional, Any

# 数据文件路径
DATA_DIR = Path(__file__).parent.parent / "data"
INTEGRATIONS_FILE = DATA_DIR / "integrations.json"


def ensure_data_dir():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_integrations() -> List[Dict[str, Any]]:
    """加载所有集成配置"""
    ensure_data_dir()
    if INTEGRATIONS_FILE.exists():
        with open(INTEGRATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_integrations(integrations: List[Dict[str, Any]]):
    """保存所有集成配置"""
    ensure_data_dir()
    with open(INTEGRATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(integrations, f, ensure_ascii=False, indent=2)


def register(integration: Dict[str, Any]) -> bool:
    """
    注册一个集成

    Args:
        integration: 集成配置字典
            - name: 集成名称（必需）
            - type: 类型（browser/api/cli）
            - description: 描述
            - config: 配置信息
            - health_check_cmd: 健康检查命令

    Returns:
        是否成功
    """
    if "name" not in integration:
        return False

    integrations = _load_integrations()

    # 检查是否已存在
    for i, existing in enumerate(integrations):
        if existing["name"] == integration["name"]:
            integrations[i] = integration
            _save_integrations(integrations)
            return True

    # 新增
    integrations.append(integration)
    _save_integrations(integrations)
    return True


def list_integrations() -> List[Dict[str, Any]]:
    """列出所有集成"""
    return _load_integrations()


def get_integration(name: str) -> Optional[Dict[str, Any]]:
    """获取指定集成"""
    integrations = _load_integrations()
    for integration in integrations:
        if integration["name"] == name:
            return integration
    return None


def health_check(name: str) -> Dict[str, Any]:
    """
    执行单个集成的健康检查

    Args:
        name: 集成名称

    Returns:
        健康检查结果 {name, status(ok/warn/error), message}
    """
    integration = get_integration(name)
    if not integration:
        return {"name": name, "status": "error", "message": "Integration not found"}

    health_check_cmd = integration.get("health_check_cmd")
    if not health_check_cmd:
        return {
            "name": name,
            "status": "warn",
            "message": "No health check command defined",
        }

    try:
        # 执行健康检查命令
        result = subprocess.run(
            health_check_cmd, shell=True, capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            return {
                "name": name,
                "status": "ok",
                "message": result.stdout.strip() or "OK",
            }
        else:
            return {
                "name": name,
                "status": "error",
                "message": result.stderr.strip() or "Check failed",
            }

    except subprocess.TimeoutExpired:
        return {"name": name, "status": "error", "message": "Health check timeout"}
    except Exception as e:
        return {"name": name, "status": "error", "message": str(e)}


def health_check_all() -> List[Dict[str, Any]]:
    """执行所有集成的健康检查"""
    integrations = _load_integrations()
    results = []
    for integration in integrations:
        result = health_check(integration["name"])
        results.append(result)
    return results


# ============ 内置集成模板 ============


def get_builtin_integrations() -> List[Dict[str, Any]]:
    """获取内置集成模板"""
    is_windows = platform.system() == "Windows"

    return [
        {
            "name": "browser_screenshot",
            "type": "browser",
            "description": "使用 browser 工具截图指定 URL",
            "config": {
                "default_url": "https://example.com",
                "output_dir": "screenshots",
            },
            "health_check_cmd": "echo OK" if not is_windows else "echo OK",
        },
        {
            "name": "system_info",
            "type": "cli",
            "description": "收集系统信息（CPU/RAM/Disk/GPU）",
            "config": {},
            "health_check_cmd": (
                'systeminfo | findstr /C:"OS Name" /C:"Total Physical Memory"'
                if is_windows
                else "uname -a"
            ),
        },
        {
            "name": "git_status",
            "type": "cli",
            "description": "检查 workspace git 状态",
            "config": {"workspace_path": str(Path.cwd())},
            "health_check_cmd": "git --version",
        },
    ]


def install_builtin_integrations():
    """安装内置集成模板"""
    builtins = get_builtin_integrations()
    for integration in builtins:
        register(integration)
    return len(builtins)


# ============ 集成执行器 ============


def execute_integration(
    name: str, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    执行集成

    Args:
        name: 集成名称
        params: 执行参数

    Returns:
        执行结果 {success, output, error}
    """
    integration = get_integration(name)
    if not integration:
        return {"success": False, "output": None, "error": "Integration not found"}

    params = params or {}
    integration_type = integration.get("type")

    if integration_type == "cli":
        return _execute_cli_integration(integration, params)
    elif integration_type == "browser":
        return _execute_browser_integration(integration, params)
    elif integration_type == "api":
        return _execute_api_integration(integration, params)
    else:
        return {
            "success": False,
            "output": None,
            "error": f"Unknown integration type: {integration_type}",
        }


def _execute_cli_integration(
    integration: Dict[str, Any], params: Dict[str, Any]
) -> Dict[str, Any]:
    """执行 CLI 类型集成"""
    name = integration["name"]

    if name == "system_info":
        return _collect_system_info()
    elif name == "git_status":
        return _check_git_status(
            integration.get("config", {}).get("workspace_path", ".")
        )
    else:
        return {
            "success": False,
            "output": None,
            "error": "CLI integration not implemented",
        }


def _execute_browser_integration(
    integration: Dict[str, Any], params: Dict[str, Any]
) -> Dict[str, Any]:
    """执行 Browser 类型集成"""
    return {
        "success": False,
        "output": None,
        "error": "Browser integration requires OpenClaw browser tool",
    }


def _execute_api_integration(
    integration: Dict[str, Any], params: Dict[str, Any]
) -> Dict[str, Any]:
    """执行 API 类型集成"""
    return {
        "success": False,
        "output": None,
        "error": "API integration not implemented",
    }


def _collect_system_info() -> Dict[str, Any]:
    """收集系统信息"""
    try:
        info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }

        # CPU 信息
        try:
            import psutil

            info["cpu_count"] = psutil.cpu_count(logical=True)
            info["cpu_percent"] = psutil.cpu_percent(interval=1)
            info["memory_total_gb"] = round(
                psutil.virtual_memory().total / (1024**3), 2
            )
            info["memory_available_gb"] = round(
                psutil.virtual_memory().available / (1024**3), 2
            )
            info["disk_total_gb"] = round(psutil.disk_usage("/").total / (1024**3), 2)
            info["disk_free_gb"] = round(psutil.disk_usage("/").free / (1024**3), 2)
        except ImportError:
            info["note"] = "Install psutil for detailed system metrics"

        return {"success": True, "output": info, "error": None}

    except Exception as e:
        return {"success": False, "output": None, "error": str(e)}


def _check_git_status(workspace_path: str) -> Dict[str, Any]:
    """检查 git 状态"""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            status = result.stdout.strip()
            return {
                "success": True,
                "output": {
                    "clean": len(status) == 0,
                    "status": status or "Working tree clean",
                },
                "error": None,
            }
        else:
            return {"success": False, "output": None, "error": result.stderr.strip()}

    except Exception as e:
        return {"success": False, "output": None, "error": str(e)}


# ============ CLI ============


def format_output(data: Any, format_type: str = "default") -> str:
    """格式化输出"""
    if format_type == "telegram":
        # Telegram 精简输出
        if isinstance(data, list):
            if not data:
                return "✅ No integrations"

            # 健康检查结果
            if data and "status" in data[0]:
                lines = []
                for item in data:
                    status_emoji = {"ok": "✅", "warn": "⚠️", "error": "❌"}.get(
                        item["status"], "❓"
                    )
                    lines.append(
                        f"{status_emoji} {item['name']}: {item.get('message', 'N/A')[:50]}"
                    )
                return "\n".join(lines)

            # 集成列表
            lines = []
            for integration in data:
                type_emoji = {"browser": "🌐", "api": "🔌", "cli": "⌨️"}.get(
                    integration.get("type"), "📦"
                )
                lines.append(
                    f"{type_emoji} {integration['name']} - {integration.get('description', 'N/A')[:40]}"
                )
            return "\n".join(lines)

        elif isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False, indent=2)

    # 默认格式
    return json.dumps(data, ensure_ascii=False, indent=2)


def main():
    """CLI 入口"""
    import argparse
    import sys

    # 修复 Windows 控制台 Unicode 输出
    if sys.platform == "win32":
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    parser = argparse.ArgumentParser(description="AIOS Integrations - 外部系统集成")
    parser.add_argument(
        "action",
        choices=["list", "health", "register", "install-builtin", "execute"],
        help="操作类型",
    )
    parser.add_argument("--name", help="集成名称")
    parser.add_argument("--type", choices=["browser", "api", "cli"], help="集成类型")
    parser.add_argument("--description", help="集成描述")
    parser.add_argument("--config", help="配置（JSON 字符串）")
    parser.add_argument("--health-check-cmd", help="健康检查命令")
    parser.add_argument(
        "--format", choices=["default", "telegram"], default="default", help="输出格式"
    )

    args = parser.parse_args()

    if args.action == "list":
        integrations = list_integrations()
        print(format_output(integrations, args.format))

    elif args.action == "health":
        if args.name:
            result = health_check(args.name)
            print(format_output([result], args.format))
        else:
            results = health_check_all()
            print(format_output(results, args.format))

    elif args.action == "register":
        if not args.name or not args.type:
            print("❌ Error: --name and --type are required for register")
            return

        integration = {
            "name": args.name,
            "type": args.type,
            "description": args.description or "",
            "config": json.loads(args.config) if args.config else {},
            "health_check_cmd": args.health_check_cmd or "",
        }

        if register(integration):
            print(f"✅ Registered: {args.name}")
        else:
            print(f"❌ Failed to register: {args.name}")

    elif args.action == "install-builtin":
        count = install_builtin_integrations()
        print(f"✅ Installed {count} builtin integrations")

    elif args.action == "execute":
        if not args.name:
            print("❌ Error: --name is required for execute")
            return

        result = execute_integration(args.name)
        print(format_output(result, args.format))


if __name__ == "__main__":
    main()
