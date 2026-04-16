"""
TaijiOS 真随机起卦模块
用硬件随机数生成卦象，模型只负责解读，不负责起卦。

起卦原理：
- 6个爻，每爻用 os.urandom 生成真随机数
- 随机数决定阴(0)阳(1)，以及是否为动爻
- 6爻组合成主卦，动爻变化后得变卦
- 卦象映射到64卦表

依赖方向：true_divination ← bot_core / multi_llm
"""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime

# 八卦基础表（先天八卦序）
TRIGRAMS = {
    (1, 1, 1): {"name": "乾", "symbol": "☰", "nature": "天", "number": 1},
    (0, 1, 1): {"name": "兑", "symbol": "☱", "nature": "泽", "number": 2},
    (1, 0, 1): {"name": "离", "symbol": "☲", "nature": "火", "number": 3},
    (0, 0, 1): {"name": "震", "symbol": "☳", "nature": "雷", "number": 4},
    (1, 1, 0): {"name": "巽", "symbol": "☴", "nature": "风", "number": 5},
    (0, 1, 0): {"name": "坎", "symbol": "☵", "nature": "水", "number": 6},
    (1, 0, 0): {"name": "艮", "symbol": "☶", "nature": "山", "number": 7},
    (0, 0, 0): {"name": "坤", "symbol": "☷", "nature": "地", "number": 8},
}

# 64卦名表 (上卦, 下卦) -> 卦名
HEXAGRAM_NAMES = {
    ("乾","乾"): "乾为天", ("乾","坤"): "天地否", ("乾","震"): "天雷无妄",
    ("乾","巽"): "天风姤", ("乾","坎"): "天水讼", ("乾","离"): "天火同人",
    ("乾","艮"): "天山遁", ("乾","兑"): "天泽履",
    ("坤","乾"): "地天泰", ("坤","坤"): "坤为地", ("坤","震"): "地雷复",
    ("坤","巽"): "地风升", ("坤","坎"): "地水师", ("坤","离"): "地火明夷",
    ("坤","艮"): "地山谦", ("坤","兑"): "地泽临",
    ("震","乾"): "雷天大壮", ("震","坤"): "雷地豫", ("震","震"): "震为雷",
    ("震","巽"): "雷风恒", ("震","坎"): "雷水解", ("震","离"): "雷火丰",
    ("震","艮"): "雷山小过", ("震","兑"): "雷泽归妹",
    ("巽","乾"): "风天小畜", ("巽","坤"): "风地观", ("巽","震"): "风雷益",
    ("巽","巽"): "巽为风", ("巽","坎"): "风水涣", ("巽","离"): "风火家人",
    ("巽","艮"): "风山渐", ("巽","兑"): "风泽中孚",
    ("坎","乾"): "水天需", ("坎","坤"): "水地比", ("坎","震"): "水雷屯",
    ("坎","巽"): "水风井", ("坎","坎"): "坎为水", ("坎","离"): "水火既济",
    ("坎","艮"): "水山蹇", ("坎","兑"): "水泽节",
    ("离","乾"): "火天大有", ("离","坤"): "火地晋", ("离","震"): "火雷噬嗑",
    ("离","巽"): "火风鼎", ("离","坎"): "火水未济", ("离","离"): "离为火",
    ("离","艮"): "火山旅", ("离","兑"): "火泽睽",
    ("艮","乾"): "山天大畜", ("艮","坤"): "山地剥", ("艮","震"): "山雷颐",
    ("艮","巽"): "山风蛊", ("艮","坎"): "山水蒙", ("艮","离"): "山火贲",
    ("艮","艮"): "艮为山", ("艮","兑"): "山泽损",
    ("兑","乾"): "泽天夬", ("兑","坤"): "泽地萃", ("兑","震"): "泽雷随",
    ("兑","巽"): "泽风大过", ("兑","坎"): "泽水困", ("兑","离"): "泽火革",
    ("兑","艮"): "泽山咸", ("兑","兑"): "兑为泽",
}

@dataclass
class Yao:
    """一爻"""
    value: int          # 0=阴, 1=阳
    moving: bool        # 是否动爻
    position: int       # 爻位（1-6，从下往上）

    @property
    def changed_value(self) -> int:
        return 1 - self.value if self.moving else self.value

    def __str__(self):
        base = "⚊" if self.value == 1 else "⚋"
        return f"{base}{'○' if self.moving else ''}"


@dataclass
class DivinationResult:
    """起卦结果"""
    yaos: list[Yao]                    # 6爻（从下到上）
    primary_name: str = ""             # 主卦名
    changed_name: str = ""             # 变卦名
    upper_trigram: str = ""            # 上卦
    lower_trigram: str = ""            # 下卦
    moving_yaos: list[int] = field(default_factory=list)  # 动爻位置
    timestamp: str = ""                # 起卦时间
    seed_hex: str = ""                 # 随机种子（可追溯）

    def summary(self) -> str:
        """一行摘要"""
        moving = ",".join(str(y) for y in self.moving_yaos) if self.moving_yaos else "无"
        return f"主卦：{self.primary_name} | 变卦：{self.changed_name} | 动爻：第{moving}爻"

    def detail(self) -> str:
        """完整描述，供模型解读用"""
        lines = [
            f"起卦时间：{self.timestamp}",
            f"随机种子：{self.seed_hex}",
            f"",
            f"主卦：{self.primary_name}（上{self.upper_trigram}下{self.lower_trigram}）",
            f"变卦：{self.changed_name}",
            f"动爻：{'、'.join(f'第{y}爻' for y in self.moving_yaos) if self.moving_yaos else '无动爻'}",
            f"",
            f"六爻（从初爻到上爻）：",
        ]
        for yao in self.yaos:
            yin_yang = "阳" if yao.value == 1 else "阴"
            move_mark = "（动）" if yao.moving else ""
            lines.append(f"  第{yao.position}爻：{yin_yang}{move_mark}")
        return "\n".join(lines)


def _random_bytes(n: int) -> bytes:
    """获取 n 字节硬件随机数"""
    return os.urandom(n)


def _byte_to_yao(b: int) -> tuple[int, bool]:
    """一个随机字节 → (阴阳, 是否动爻)
    低2位决定：
      00 = 老阴（阴，动）
      01 = 少阳（阳，不动）
      10 = 少阴（阴，不动）
      11 = 老阳（阳，动）
    概率各25%，符合传统蓍草法的简化版
    """
    low2 = b & 0x03
    if low2 == 0:    # 老阴
        return 0, True
    elif low2 == 1:  # 少阳
        return 1, False
    elif low2 == 2:  # 少阴
        return 0, False
    else:            # 老阳
        return 1, True


def _trigram_lookup(y1: int, y2: int, y3: int) -> dict:
    """三爻查八卦"""
    key = (y1, y2, y3)
    return TRIGRAMS.get(key, {"name": "?", "symbol": "?", "nature": "?"})


def cast() -> DivinationResult:
    """真随机起卦。返回完整卦象结果。

    使用 os.urandom 生成6字节随机数，每字节决定一爻。
    卦象由随机数决定，不受模型影响。
    """
    # 生成随机种子
    raw = _random_bytes(6)
    seed_hex = raw.hex()

    # 6爻
    yaos = []
    for i in range(6):
        value, moving = _byte_to_yao(raw[i])
        yaos.append(Yao(value=value, moving=moving, position=i + 1))

    # 主卦：下卦=1-3爻，上卦=4-6爻
    lower = _trigram_lookup(yaos[0].value, yaos[1].value, yaos[2].value)
    upper = _trigram_lookup(yaos[3].value, yaos[4].value, yaos[5].value)

    primary_name = HEXAGRAM_NAMES.get(
        (upper["name"], lower["name"]), f"{upper['name']}{lower['name']}卦"
    )

    # 变卦：动爻变化后
    lower_c = _trigram_lookup(yaos[0].changed_value, yaos[1].changed_value, yaos[2].changed_value)
    upper_c = _trigram_lookup(yaos[3].changed_value, yaos[4].changed_value, yaos[5].changed_value)

    changed_name = HEXAGRAM_NAMES.get(
        (upper_c["name"], lower_c["name"]), f"{upper_c['name']}{lower_c['name']}卦"
    )

    moving_yaos = [y.position for y in yaos if y.moving]

    return DivinationResult(
        yaos=yaos,
        primary_name=primary_name,
        changed_name=changed_name,
        upper_trigram=f"{upper['name']}({upper['symbol']}{upper['nature']})",
        lower_trigram=f"{lower['name']}({lower['symbol']}{lower['nature']})",
        moving_yaos=moving_yaos,
        timestamp=datetime.now().isoformat(timespec="seconds"),
        seed_hex=seed_hex,
    )


def cast_and_format(question: str = "", person: str = "") -> str:
    """起卦 + 格式化为 prompt，供模型解读用"""
    result = cast()
    lines = [
        "【真随机起卦结果 — 硬件随机数生成，非模型计算】",
        "",
        result.detail(),
        "",
    ]
    if question:
        lines.append(f"占问事项：{question}")
    if person:
        lines.append(f"占问对象：{person}")
    lines.append("")
    lines.append("请严格基于以上卦象进行解读，不要重新起卦。")
    return "\n".join(lines)
