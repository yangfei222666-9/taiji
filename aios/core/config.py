# aios/core/config.py - 加载 config.yaml（flat key: paths.events）
import os
from pathlib import Path

AIOS_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = AIOS_ROOT / "config.yaml"

_cache = {}


def expand_env_vars(s: str) -> str:
    return os.path.expandvars(s)


def read_simple_yaml(path: Path) -> dict:
    """简单 yaml 解析，嵌套 → flat key（paths.events）"""
    if not path.exists():
        return {}
    result = {}
    indent_stack = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        while indent_stack and indent <= indent_stack[-1][0]:
            indent_stack.pop()

        prefix = ".".join(s[1] for s in indent_stack)

        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            # strip inline comments before unquoting
            if '"' in val:
                # handle quoted value with possible trailing comment
                val = val.strip()
                if val.startswith('"'):
                    end = val.find('"', 1)
                    val = val[1:end] if end > 0 else val.strip('"')
                elif val.startswith("'"):
                    end = val.find("'", 1)
                    val = val[1:end] if end > 0 else val.strip("'")
                else:
                    val = val.split('#')[0].strip().strip('"').strip("'")
            elif "'" in val:
                val = val.strip()
                if val.startswith("'"):
                    end = val.find("'", 1)
                    val = val[1:end] if end > 0 else val.strip("'")
                else:
                    val = val.split('#')[0].strip().strip("'")
            else:
                val = val.split('#')[0].strip()

            full_key = f"{prefix}.{key}" if prefix else key

            if val:
                result[full_key] = val
            else:
                indent_stack.append((indent, key))

    return result


def load() -> dict:
    if "cfg" in _cache:
        return _cache["cfg"]
    cfg = read_simple_yaml(CONFIG_PATH)
    _cache["cfg"] = cfg
    return cfg


def get(key: str, default: str = "") -> str:
    return load().get(key, default)


def get_path(key: str) -> Path:
    raw = get(key)
    if not raw:
        return None
    return Path(expand_env_vars(raw))


def get_float(key: str, default: float = 0.0) -> float:
    raw = get(key)
    if not raw:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


def get_bool(key: str, default: bool = False) -> bool:
    raw = get(key)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "y", "on")


def get_int(key: str, default: int = 0) -> int:
    raw = get(key)
    if not raw:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default
