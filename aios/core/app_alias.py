# aios/core/app_alias.py - 应用别名归一化
"""
职责：
1. routing_alias  → 执行匹配（柯柯音乐 → QQMusic.exe）
2. display_alias  → 用户可见名（柯柯音乐 → QQ音乐）

所有对用户回复统一用 canonical name，不回显 ASR 错词。
别名表从 memory/corrections.json 的 voice_aliases + app_paths 加载，
也支持硬编码兜底。
"""

import json
from pathlib import Path

CORRECTIONS_FILE = (
    Path(__file__).resolve().parent.parent.parent / "memory" / "corrections.json"
)

# 繁→简 常见字映射（轻量，不引入外部依赖）
_T2S = str.maketrans(
    "樂開關閉電腦視頻遊戲設備網絡記憶體處點選單連線檔案資訊訊號碼圖書館運動場區塊鏈結構體積極進階層級別類型態勢範圍環節點擊發現場景觀測試驗證據點評論壇區域網路線程式碼頭條件數據庫存儲備份額度量級別針對話題組織結構體驗證書籤選項鏈結構體積極進階層級別類型態勢範圍環節點擊發現場景觀測試驗證據點評論壇區域網路線程式碼頭條件數據庫存儲備份額度量級別針對話題組織結構體驗證書籤選項",
    "乐开关闭电脑视频游戏设备网络记忆体处点选单连线档案资讯讯号码图书馆运动场区块链结构体积极进阶层级别类型态势范围环节点击发现场景观测试验证据点评论坛区域网路线程式码头条件数据库存储备份额度量级别针对话题组织结构体验证书签选项链结构体积极进阶层级别类型态势范围环节点击发现场景观测试验证据点评论坛区域网路线程式码头条件数据库存储备份额度量级别针对话题组织结构体验证书签选项",
)


def _normalize(text: str) -> str:
    """繁→简 + 小写，用于别名匹配"""
    return text.translate(_T2S).lower().strip()


# 硬编码兜底（corrections.json 加载失败时用）
_BUILTIN_ALIASES = {
    "柯柯音乐": "QQ音乐",
    "扣扣音乐": "QQ音乐",
    "酷酷音乐": "QQ音乐",
    "呵呵音乐": "QQ音乐",
    "可可音乐": "QQ音乐",
    "qq音乐": "QQ音乐",
    "QQ音乐": "QQ音乐",
    "微信": "微信",
    "wechat": "微信",
}

_BUILTIN_PATHS = {
    "QQ音乐": "E:\\QQMusic\\QQMusic.exe",
}

_BUILTIN_PROCESS = {
    "QQ音乐": "QQMusic.exe",
}

# 动作风险分级
RISK_LEVELS = {
    # 低风险：直接执行
    "open": "low",
    "close": "low",
    "play": "low",
    "pause": "low",
    "volume": "low",
    "switch_mode": "low",
    # 高风险：需要二次确认
    "uninstall": "high",
    "delete": "high",
    "send_message": "high",
    "payment": "high",
    "format": "high",
}


def _load_corrections() -> dict:
    """从 corrections.json 加载别名表"""
    if CORRECTIONS_FILE.exists():
        try:
            data = json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))
            return data
        except Exception:
            pass
    return {}


def resolve(raw_text: str) -> dict:
    """
    输入原始文本（可能含 ASR 错词），返回归一化结果。

    返回:
    {
        "raw": "關閉柯柯音樂",
        "canonical": "QQ音乐",          # 用户可见名
        "process_name": "QQMusic.exe",   # 预检用
        "exe_path": "E:\\QQMusic\\...",  # 启动用
        "action": "close",              # open/close/None
        "matched": True,
    }
    """
    corrections = _load_corrections()
    voice_aliases = corrections.get("voice_aliases", {})
    app_paths = corrections.get("app_paths", {})

    # 合并别名表（corrections 优先）
    all_aliases = {**_BUILTIN_ALIASES, **voice_aliases}
    all_paths = {**_BUILTIN_PATHS, **app_paths}

    # 提取动作
    action = None
    text = raw_text.strip()
    for prefix, act in [
        ("打开", "open"),
        ("打開", "open"),
        ("启动", "open"),
        ("关闭", "close"),
        ("關閉", "close"),
        ("退出", "close"),
        ("停止", "close"),
        ("播放", "play"),
        ("暂停", "pause"),
        ("卸载", "uninstall"),
        ("刪除", "delete"),
        ("删除", "delete"),
        ("发送", "send_message"),
        ("發送", "send_message"),
        ("支付", "payment"),
        ("付款", "payment"),
        ("格式化", "format"),
    ]:
        if text.startswith(prefix):
            action = act
            text = text[len(prefix) :].strip()
            break

    # 查别名（繁简归一化匹配）
    canonical = None
    norm_text = _normalize(text)
    for alias, canon in all_aliases.items():
        if _normalize(alias) == norm_text:
            canonical = canon
            break

    if not canonical:
        # 模糊匹配：归一化后包含
        for alias, canon in all_aliases.items():
            norm_alias = _normalize(alias)
            if norm_alias in norm_text or norm_text in norm_alias:
                canonical = canon
                break

    if not canonical:
        return {
            "raw": raw_text,
            "canonical": text,
            "process_name": None,
            "exe_path": None,
            "action": action,
            "risk": RISK_LEVELS.get(action, "low"),
            "matched": False,
        }

    exe_path = all_paths.get(canonical, _BUILTIN_PATHS.get(canonical))
    process_name = _BUILTIN_PROCESS.get(canonical)

    return {
        "raw": raw_text,
        "canonical": canonical,
        "process_name": process_name,
        "exe_path": exe_path,
        "action": action,
        "risk": RISK_LEVELS.get(action, "low"),
        "matched": True,
    }


def display_name(raw_text: str) -> str:
    """快捷方法：只返回用户可见名"""
    return resolve(raw_text).get("canonical", raw_text)


def action_summary(raw_text: str) -> str:
    """生成用户可见的操作摘要，如 '已关闭QQ音乐'"""
    r = resolve(raw_text)
    action_map = {
        "open": "已打开",
        "close": "已关闭",
        "play": "已播放",
        "pause": "已暂停",
        "uninstall": "确认卸载",
        "delete": "确认删除",
        "send_message": "确认发送",
        "payment": "确认支付",
    }
    verb = action_map.get(r["action"], "已处理")
    return f"{verb}{r['canonical']}"


def needs_confirmation(raw_text: str) -> bool:
    """高风险动作需要二次确认"""
    return resolve(raw_text).get("risk") == "high"


if __name__ == "__main__":
    # 回归测试
    tests = [
        ("打開柯柯音樂", "open", "QQ音乐", True, "low"),
        ("關閉柯柯音樂", "close", "QQ音乐", True, "low"),
        ("打开QQ音乐", "open", "QQ音乐", True, "low"),
        ("关闭扣扣音乐", "close", "QQ音乐", True, "low"),
        ("退出微信", "close", "微信", True, "low"),
        ("打开记事本", "open", "记事本", False, "low"),
        ("卸载QQ音乐", "uninstall", "QQ音乐", True, "high"),
        ("删除微信", "delete", "微信", True, "high"),
    ]

    passed = 0
    for raw, exp_action, exp_canon, exp_matched, exp_risk in tests:
        r = resolve(raw)
        ok = (
            r["action"] == exp_action
            and r["canonical"] == exp_canon
            and r["matched"] == exp_matched
            and r["risk"] == exp_risk
        )
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(
            f"  {status} '{raw}' -> action={r['action']}, canonical={r['canonical']}, risk={r['risk']}"
        )
        if not ok:
            print(
                f"        expected: action={exp_action}, canonical={exp_canon}, risk={exp_risk}"
            )

    print(f"\n{passed}/{len(tests)} PASS")
    if passed == len(tests):
        print("ALL PASS")
