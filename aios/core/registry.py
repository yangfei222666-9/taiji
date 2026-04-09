"""
AIOS Plugin Registry v1.0
可插拔插件系统：自动发现、注册、生命周期管理

每个插件是 aios/plugins/<name>/ 目录下的 Python 包，需实现：
  - plugin.py 中的 PluginClass(继承 BasePlugin)
  或
  - __init__.py 中导出 PLUGIN_META dict

用法:
  from aios.core.registry import registry
  registry.discover()           # 自动扫描 plugins/ 目录
  registry.get("aram")          # 获取插件实例
  registry.list_plugins()       # 列出所有插件
  registry.call("aram", "match", query="盖伦")  # 调用插件方法
"""

import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"


class BasePlugin:
    """插件基类，所有插件应继承此类"""

    # 子类必须覆盖
    name: str = "unnamed"
    version: str = "0.0.0"
    description: str = ""
    author: str = ""

    # 可选：声明提供的能力（供 registry 查询）
    capabilities: List[str] = []

    # 可选：声明依赖的其他插件
    dependencies: List[str] = []

    def __init__(self):
        self._enabled = True
        self._loaded_at = time.time()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def on_load(self):
        """插件加载时调用（可覆盖）"""
        pass

    def on_unload(self):
        """插件卸载时调用（可覆盖）"""
        pass

    def health_check(self) -> dict:
        """健康检查（可覆盖）"""
        return {"status": "ok", "plugin": self.name, "version": self.version}

    def meta(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities,
            "enabled": self._enabled,
        }


class PluginRegistry:
    """插件注册中心"""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._load_errors: Dict[str, str] = {}

    def discover(self, plugins_dir: Path = None):
        """自动扫描 plugins/ 目录，加载所有插件"""
        pdir = plugins_dir or PLUGINS_DIR
        if not pdir.exists():
            return

        for candidate in pdir.iterdir():
            if not candidate.is_dir():
                continue
            if candidate.name.startswith("_"):
                continue
            if candidate.name in self._plugins:
                continue  # 已加载

            try:
                self._load_plugin(candidate)
            except Exception as e:
                self._load_errors[candidate.name] = str(e)

    def _load_plugin(self, plugin_dir: Path):
        """加载单个插件"""
        name = plugin_dir.name

        # 方式1: plugin.py 中有继承 BasePlugin 的类
        plugin_py = plugin_dir / "plugin.py"
        if plugin_py.exists():
            spec_name = f"aios.plugins.{name}.plugin"
            if spec_name not in sys.modules:
                # 确保 parent 在 path 中
                parent = str(plugin_dir.parent.parent)
                if parent not in sys.path:
                    sys.path.insert(0, parent)
                mod = importlib.import_module(f"plugins.{name}.plugin")
            else:
                mod = sys.modules[spec_name]

            # 找到 BasePlugin 子类
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin
                ):
                    instance = attr()
                    instance.on_load()
                    self._plugins[name] = instance
                    return

        # 方式2: __init__.py 中有 PLUGIN_META
        init_py = plugin_dir / "__init__.py"
        if init_py.exists():
            parent = str(plugin_dir.parent.parent)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            mod = importlib.import_module(f"plugins.{name}")
            meta = getattr(mod, "PLUGIN_META", None)
            if meta and isinstance(meta, dict):
                # 动态创建插件实例
                instance = BasePlugin()
                instance.name = meta.get("name", name)
                instance.version = meta.get("version", "0.0.0")
                instance.description = meta.get("description", "")
                instance.capabilities = meta.get("capabilities", [])
                instance._module = mod
                instance.on_load()
                self._plugins[name] = instance
                return

        # 方式3: 有任何 .py 文件，创建轻量包装
        py_files = list(plugin_dir.glob("*.py"))
        if py_files:
            instance = BasePlugin()
            instance.name = name
            instance.description = f"Legacy plugin: {name}"
            instance.capabilities = [f.stem for f in py_files if f.stem != "__init__"]
            instance._legacy = True
            instance._dir = plugin_dir
            self._plugins[name] = instance

    def register(self, plugin: BasePlugin):
        """手动注册插件"""
        plugin.on_load()
        self._plugins[plugin.name] = plugin

    def unregister(self, name: str):
        """卸载插件"""
        if name in self._plugins:
            self._plugins[name].on_unload()
            del self._plugins[name]

    def get(self, name: str) -> Optional[BasePlugin]:
        """获取插件实例"""
        return self._plugins.get(name)

    def list_plugins(self) -> List[dict]:
        """列出所有插件"""
        result = []
        for name, plugin in sorted(self._plugins.items()):
            info = plugin.meta()
            info["load_errors"] = self._load_errors.get(name)
            result.append(info)
        return result

    def find_by_capability(self, capability: str) -> List[BasePlugin]:
        """按能力查找插件"""
        return [
            p
            for p in self._plugins.values()
            if capability in p.capabilities and p.enabled
        ]

    def call(self, plugin_name: str, method: str, **kwargs) -> Any:
        """调用插件方法"""
        plugin = self.get(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' not found")
        if not plugin.enabled:
            raise ValueError(f"Plugin '{plugin_name}' is disabled")

        # 先查插件实例方法
        fn = getattr(plugin, method, None)
        if fn and callable(fn):
            return fn(**kwargs)

        # 再查 legacy 模块
        if hasattr(plugin, "_module"):
            fn = getattr(plugin._module, method, None)
            if fn and callable(fn):
                return fn(**kwargs)

        # 最后查 legacy 目录下的子模块
        if hasattr(plugin, "_legacy") and hasattr(plugin, "_dir"):
            mod_path = plugin._dir / f"{method}.py"
            if mod_path.exists():
                parent = str(plugin._dir.parent.parent)
                if parent not in sys.path:
                    sys.path.insert(0, parent)
                mod = importlib.import_module(f"plugins.{plugin_name}.{method}")
                return mod

        raise AttributeError(f"Plugin '{plugin_name}' has no method '{method}'")

    def health_check_all(self) -> dict:
        """所有插件健康检查"""
        results = {}
        for name, plugin in self._plugins.items():
            try:
                results[name] = plugin.health_check()
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        return results

    def summary(self) -> str:
        """文本摘要"""
        plugins = self.list_plugins()
        if not plugins:
            return "📦 无已注册插件"
        lines = [f"📦 已注册插件: {len(plugins)}"]
        for p in plugins:
            status = "✅" if p["enabled"] else "❌"
            lines.append(f"  {status} {p['name']} v{p['version']} — {p['description']}")
        if self._load_errors:
            lines.append(f"\n⚠️ 加载失败: {len(self._load_errors)}")
            for name, err in self._load_errors.items():
                lines.append(f"  ❌ {name}: {err}")
        return "\n".join(lines)


# 全局单例
registry = PluginRegistry()


# CLI
def main():
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    registry.discover()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "list":
            print(json.dumps(registry.list_plugins(), ensure_ascii=False, indent=2))
        elif cmd == "health":
            print(json.dumps(registry.health_check_all(), ensure_ascii=False, indent=2))
        elif cmd == "summary":
            print(registry.summary())
        else:
            print(f"未知命令: {cmd}")
    else:
        print(registry.summary())


if __name__ == "__main__":
    main()
