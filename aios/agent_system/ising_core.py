#!/usr/bin/env python3
"""
TaijiOS Ising 物理引擎 — 让系统活起来的心跳

核心思想：
  易经六爻 ≡ 6-spin Ising chain
  五引擎   ≡ 操作 spin 的物理过程
  H(能量)  ≡ 系统好坏的唯一标量

这个文件做三件事：
  1. 定义 H = -Σ Jᵢⱼ σᵢσⱼ - Σ hᵢσᵢ （能量函数）
  2. 维护 Jᵢⱼ 非对称耦合矩阵，用 ΔJᵢⱼ ∝ σᵢ·Δσⱼ 学习
  3. 提供 pulse() 心跳：每次 tick 计算 H → 比较 ΔH → 驱动 crystal 写入

状态编码：
  σᵢ ∈ {+1, -1}  （阳=+1, 阴=-1, 对应 hexagram_lines 的 state=1/0）
  σ₁=基础设施, σ₂=执行, σ₃=学习, σ₄=调度, σ₅=协作, σ₆=治理

Author: TaijiOS (Opus 4.6 校准)
Date: 2026-04-15
"""

import json
import math
import time
import logging
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from hexagram_lines import calculate_six_lines, LineScore
from event_bus import emit, subscribe

log = logging.getLogger("aios.ising")

DATA_DIR = Path(__file__).parent / "data" / "ising"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 六爻标签
YAO_LABELS = ["infra", "execution", "learning", "routing", "collaboration", "governance"]


# ============================================================
# 数据结构
# ============================================================

@dataclass
class IsingState:
    """系统的 Ising 快照"""
    sigma: List[int]          # 6 spins: +1 or -1
    scores: List[float]       # 6 continuous scores (0~1)
    changing: List[bool]      # 6 changing flags
    H: float = 0.0           # 总能量
    H_coupling: float = 0.0  # 耦合能 -Σ Jᵢⱼ σᵢσⱼ
    H_field: float = 0.0     # 外场能 -Σ hᵢσᵢ
    T_eff: float = 0.0       # 有效温度 (changing yao 比例)
    hexagram_bits: str = ""   # 6-bit string
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================
# 耦合矩阵 Jᵢⱼ — 六爻之间的交互
# ============================================================

# 初始耦合矩阵（非对称，module-level 常量，避免每 tick 重建）
# J[i][j] = i 对 j 的影响强度
# 拓扑: infra → execution → learning → routing → collaboration → governance
_DEFAULT_J = (
    #  infra  exec   learn  route  collab govern
    (0.00, 0.30, 0.10, 0.15, 0.05, 0.05),  # infra →
    (0.10, 0.00, 0.25, 0.20, 0.10, 0.05),  # execution →
    (0.05, 0.15, 0.00, 0.20, 0.10, 0.10),  # learning →
    (0.05, 0.10, 0.10, 0.00, 0.20, 0.10),  # routing →
    (0.05, 0.05, 0.10, 0.15, 0.00, 0.20),  # collaboration →
    (0.10, 0.10, 0.15, 0.10, 0.15, 0.00),  # governance →
)


def _default_J() -> List[List[float]]:
    """返回可变的 J 矩阵副本（供初始化用）"""
    return [list(row) for row in _DEFAULT_J]


class CouplingMatrix:
    """
    非对称耦合矩阵 Jᵢⱼ

    学习规则（带方向的 Hebbian）：
      ΔJᵢⱼ = η · σᵢ · Δσⱼ
    i 的当前状态 × j 的变化量 → 保留因果方向
    """

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.J = _default_J()
        self.eta = 0.02  # 学习率（保守，防止震荡）
        self.decay = 0.995  # 缓慢衰减回默认值
        self._load()

    def coupling_energy(self, sigma: List[int]) -> float:
        """计算耦合能 H_J = -Σᵢⱼ Jᵢⱼ σᵢσⱼ"""
        H = 0.0
        for i in range(6):
            for j in range(6):
                if i != j:
                    H -= self.J[i][j] * sigma[i] * sigma[j]
        return H

    def learn(self, sigma: List[int], sigma_prev: List[int], reward: float):
        """
        非对称 Hebbian 学习：
          ΔJᵢⱼ = η · reward · σᵢ · (σⱼ - σⱼ_prev)

        reward > 0 (H 下降了) → 强化导致此转移的耦合
        reward < 0 (H 上升了) → 削弱
        """
        for i in range(6):
            for j in range(6):
                if i == j:
                    continue
                delta_j = sigma[j] - sigma_prev[j]
                if delta_j != 0:
                    update = self.eta * reward * sigma[i] * delta_j
                    self.J[i][j] += update
                    # 钳位到 [-0.5, 0.5]
                    self.J[i][j] = max(-0.5, min(0.5, self.J[i][j]))

    def decay_toward_default(self):
        """缓慢衰减回初始值，防止 J 漂移太远"""
        for i in range(6):
            for j in range(6):
                self.J[i][j] = self.decay * self.J[i][j] + (1 - self.decay) * _DEFAULT_J[i][j]

    def _save(self):
        path = self.data_dir / "coupling_matrix.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"J": self.J, "eta": self.eta, "updated_at": time.time()},
                      f, ensure_ascii=False, indent=2)

    def _load(self):
        path = self.data_dir / "coupling_matrix.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.J = data["J"]
            except Exception:
                pass

    def save(self):
        self._save()


# ============================================================
# 外场 hᵢ — Crystal 对每个 spin 的历史偏置
# ============================================================

class CrystalField:
    """
    外场向量 h[i] — 从 experience_crystals 推导的偏置

    正 hᵢ → 历史上该维度"阳"带来好结果 → 偏置向阳
    负 hᵢ → 历史上该维度"阴"带来好结果 → 偏置向阴
    """

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.h = [0.0] * 6  # 初始无偏置
        self._load()

    def field_energy(self, sigma: List[int]) -> float:
        """计算外场能 H_h = -Σᵢ hᵢ σᵢ"""
        return -sum(self.h[i] * sigma[i] for i in range(6))

    def update(self, sigma: List[int], delta_H: float):
        """
        能量变化驱动的外场更新：
          ΔH < 0（变好了） → 强化当前 σᵢ 方向的 hᵢ
          ΔH > 0（变差了） → 削弱

        规则：Δhᵢ = α · sign(-ΔH) · σᵢ · |ΔH|
        即：ΔH<0(好) → +α·σᵢ·|ΔH|；ΔH>0(差) → -α·σᵢ·|ΔH|
        """
        alpha = 0.01  # 外场学习率
        for i in range(6):
            # ΔH < 0（变好）→ 强化当前 σᵢ 方向 → h[i] 向 σᵢ 偏移
            # ΔH > 0（变差）→ 削弱当前 σᵢ 方向 → h[i] 向 -σᵢ 偏移
            # field energy H_h = -Σ hᵢσᵢ，h[i]↑ + σᵢ=+1 → 能量↓ → 正确强化
            sign = 1.0 if delta_H < 0 else -1.0
            magnitude = min(abs(delta_H), 2.0)  # 钳位防止跳变
            self.h[i] += alpha * sign * sigma[i] * magnitude
            # 钳位到 [-0.3, 0.3]
            self.h[i] = max(-0.3, min(0.3, self.h[i]))

    def decay(self, rate: float = 0.998):
        """缓慢衰减回零，防止 h 饱和在 clamp 边界失去自适应能力。
        半衰期 ≈ ln(2)/ln(1/rate) ≈ 346 ticks"""
        for i in range(6):
            self.h[i] *= rate

    def _save(self):
        path = self.data_dir / "crystal_field.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"h": self.h, "labels": YAO_LABELS, "updated_at": time.time()},
                      f, ensure_ascii=False, indent=2)

    def _load(self):
        path = self.data_dir / "crystal_field.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.h = data["h"]
            except Exception:
                pass

    def save(self):
        self._save()


# ============================================================
# Hamiltonian — 能量函数
# ============================================================

def compute_H(sigma: List[int], coupling: CouplingMatrix, crystal: CrystalField) -> Tuple[float, float, float]:
    """
    计算系统总能量

    H = H_coupling + H_field
      = -Σᵢⱼ Jᵢⱼ σᵢσⱼ  -  Σᵢ hᵢσᵢ

    Returns: (H_total, H_coupling, H_field)
    """
    H_c = coupling.coupling_energy(sigma)
    H_f = crystal.field_energy(sigma)
    return H_c + H_f, H_c, H_f


# ============================================================
# 状态编码：metrics → IsingState
# ============================================================

def metrics_to_ising(metrics: Dict[str, float],
                     coupling: CouplingMatrix,
                     crystal: CrystalField) -> IsingState:
    """
    系统指标 → Ising 状态

    流程：
    1. hexagram_lines 计算 6 个 LineScore
    2. 离散化为 σ ∈ {+1, -1}
    3. 计算 H
    4. 有效温度 = changing yao 占比
    """
    lines = calculate_six_lines(metrics)
    line_list = [
        lines["line_1_infra"],
        lines["line_2_execution"],
        lines["line_3_learning"],
        lines["line_4_routing"],
        lines["line_5_collaboration"],
        lines["line_6_governance"],
    ]

    scores = [l.score for l in line_list]
    states = [l.state for l in line_list]
    changing = [l.is_changing for l in line_list]

    # 转换为 Ising spin: state=1→+1, state=0→-1
    sigma = [1 if s == 1 else -1 for s in states]

    # 计算能量
    H_total, H_c, H_f = compute_H(sigma, coupling, crystal)

    # 有效温度 = changing yao 比例 (0~1)
    T_eff = sum(1 for c in changing if c) / 6.0

    # 卦码 — HEXAGRAM_TABLE 约定"初爻在右"，states[0]=初爻 需放在最右
    bits = "".join(str(s) for s in reversed(states))

    return IsingState(
        sigma=sigma,
        scores=scores,
        changing=changing,
        H=round(H_total, 4),
        H_coupling=round(H_c, 4),
        H_field=round(H_f, 4),
        T_eff=round(T_eff, 3),
        hexagram_bits=bits,
    )


# ============================================================
# 心跳 Pulse — 让系统活起来的核心循环
# ============================================================

class Pulse:
    """
    TaijiOS 的心跳

    每次 tick：
    1. 读当前 metrics → 计算 IsingState
    2. 比较 ΔH = H_now - H_prev
    3. ΔH < 0（变好）→ 强化 crystal，J 学习正反馈
    4. ΔH > 0（变差）→ 削弱 crystal，J 学习负反馈
    5. 发射 ising.pulse 事件，其他引擎监听
    6. T_eff 高（临界态多）→ 提示情势引擎提高警觉

    这个循环把五引擎变成一个有机体：
    - 情势引擎读 H 和 T_eff 做造动决策
    - 恢复引擎读 ΔH 判断恢复是否成功
    - 学习引擎读 J 矩阵调整协作权重
    - 记忆引擎读 crystal field 做经验回放
    - 协作引擎读耦合强度调整 agent 分配
    """

    def __init__(self, data_dir: Path = DATA_DIR):
        self._lock = threading.Lock()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.coupling = CouplingMatrix(self.data_dir)
        self.crystal = CrystalField(self.data_dir)
        self.prev_state: Optional[IsingState] = None
        self.history: List[dict] = []
        self.tick_count = 0
        self._first_change_recorded = False
        self._load_history()

    @staticmethod
    def _sanitize_metrics(metrics: Dict[str, float]) -> Dict[str, float]:
        """
        输入验证 — 防御 None / NaN / stale 指标

        策略：无效值替换为 0.5（中性），不抛异常。
        返回清洗后的 metrics + 污染计数。
        """
        clean = {}
        poisoned = 0
        for k, v in metrics.items():
            if v is None or (isinstance(v, float) and math.isnan(v)):
                clean[k] = 0.5  # 中性值
                poisoned += 1
            elif isinstance(v, (int, float)):
                clean[k] = float(v)
            else:
                clean[k] = 0.5
                poisoned += 1
        return clean, poisoned

    def tick(self, metrics: Dict[str, float]) -> dict:
        """
        一次心跳（线程安全，emit 在锁外）

        Returns: {
            state: IsingState dict,
            delta_H: float,
            direction: "improving" | "degrading" | "stable",
            hexagram_bits: str,
            T_eff: float,
            actions_taken: list,
        }
        """
        # ── 输入验证 ──
        metrics, poisoned = self._sanitize_metrics(metrics)

        # ── 锁内：纯计算 + 状态更新，不做 I/O 或 emit ──
        with self._lock:
            result, pending_events = self._tick_inner(metrics, poisoned)

        # ── 锁外：发射事件（subscriber 可安全调 get_status 等）──
        for event_type, event_data in pending_events:
            try:
                emit(event_type, event_data)
            except Exception as e:
                log.warning("Event emit failed: %s %s", event_type, e)

        return result

    def _tick_inner(self, metrics: Dict[str, float], poisoned: int) -> Tuple[dict, list]:
        """tick 内部实现（已持锁）。返回 (result, pending_events)"""
        self.tick_count += 1
        pending_events = []
        actions = []

        # ── 快照 J/crystal 用于 rollback ──
        j_snapshot = [row[:] for row in self.coupling.J]
        h_snapshot = self.crystal.h[:]

        state = metrics_to_ising(metrics, self.coupling, self.crystal)

        if poisoned > 0:
            actions.append(f"sanitized({poisoned}_metrics)")

        # ── 计算 ΔH ──
        delta_H = 0.0
        direction = "stable"
        if self.prev_state is not None:
            delta_H = state.H - self.prev_state.H

            if delta_H < -0.05:
                direction = "improving"
            elif delta_H > 0.05:
                direction = "degrading"

            # ── 毒性检测 + rollback ──
            # 如果 >3 个指标被污染且能量骤变，不学习（防止坏数据污染 J/crystal）
            if poisoned > 3 and abs(delta_H) > 0.2:
                actions.append(f"rollback(poisoned={poisoned},|ΔH|={abs(delta_H):.3f})")
                self.coupling.J = j_snapshot
                self.crystal.h = h_snapshot
            else:
                # ── Crystal 外场更新 ──
                if abs(delta_H) > 0.02:
                    self.crystal.update(state.sigma, delta_H)
                    actions.append(f"crystal_update(ΔH={delta_H:+.3f})")

                # ── J 矩阵学习 ──
                reward = -delta_H
                if abs(reward) > 0.05:
                    self.coupling.learn(state.sigma, self.prev_state.sigma, reward)
                    actions.append(f"J_learn(r={reward:+.3f})")

            # ── J 缓慢衰减 + Crystal 缓慢衰减 ──
            self.coupling.decay_toward_default()
            self.crystal.decay()

        # ── 卦变检测 + 多模型验证 ──
        hexagram_changed = False
        if self.prev_state and state.hexagram_bits != self.prev_state.hexagram_bits:
            hexagram_changed = True
            old_bits = self.prev_state.hexagram_bits
            new_bits = state.hexagram_bits
            # bits 现在是"初爻在右"：bits[5]=初爻(infra), bits[0]=上爻(governance)
            # YAO_LABELS[0]=infra → 对应 bits[5-0]=bits[5]
            flipped = [YAO_LABELS[i] for i in range(6)
                       if old_bits[5 - i] != new_bits[5 - i]]
            actions.append(f"hexagram_change({old_bits}→{new_bits})")

            # ── 多模型交叉验证卦变 ──
            validation = self._validate_transition(old_bits, new_bits, flipped,
                                                    delta_H, state.T_eff)
            if validation:
                actions.append(f"cross_validated({validation['consensus']})")

            pending_events.append(("ising.hexagram_change", {
                "old_bits": old_bits, "new_bits": new_bits,
                "flipped_yao": flipped,
                "delta_H": round(delta_H, 4), "direction": direction,
                "validation": validation,
            }))

        # ── 组装结果 ──
        result = {
            "tick": self.tick_count,
            "state": state.to_dict(),
            "delta_H": round(delta_H, 4),
            "direction": direction,
            "hexagram_bits": state.hexagram_bits,
            "hexagram_changed": hexagram_changed,
            "T_eff": state.T_eff,
            "actions": actions,
        }

        # ── 收集待发事件（锁外发射）──
        pending_events.append(("ising.pulse", {
            "tick": self.tick_count, "H": state.H,
            "delta_H": round(delta_H, 4), "direction": direction,
            "T_eff": state.T_eff, "hexagram_bits": state.hexagram_bits,
            "sigma": state.sigma,
        }))

        if state.T_eff >= 0.5:
            pending_events.append(("ising.high_temperature", {
                "T_eff": state.T_eff,
                "changing_yao": [YAO_LABELS[i] for i, c in enumerate(state.changing) if c],
                "H": state.H,
            }))
            actions.append(f"high_temp(T={state.T_eff:.2f})")

        if delta_H > 0.3:
            pending_events.append(("ising.energy_spike", {
                "delta_H": round(delta_H, 4), "H": state.H,
                "hexagram_bits": state.hexagram_bits,
            }))
            actions.append(f"energy_spike(ΔH={delta_H:+.3f})")

        # ── 持久化（含 history）──
        self._append_history(result)
        if self.tick_count % 10 == 0:
            self.coupling.save()
            self.crystal.save()
            self._save_history()

        # ── 记录最新方向供 get_status 用 ──
        self._last_direction = direction
        self._last_delta_H = round(delta_H, 4)
        self.prev_state = state
        return result, pending_events

    def get_energy(self) -> Optional[float]:
        """获取当前 H"""
        return self.prev_state.H if self.prev_state else None

    def get_temperature(self) -> Optional[float]:
        """获取当前有效温度"""
        return self.prev_state.T_eff if self.prev_state else None

    def get_coupling_matrix(self) -> List[List[float]]:
        """获取当前 J 矩阵"""
        return self.coupling.J

    def get_crystal_field(self) -> List[float]:
        """获取当前外场 h"""
        return self.crystal.h

    def get_status(self) -> dict:
        """完整状态报告（含 scores/changing/direction 供 HUD 用）

        即使本进程未做过 tick，也能从磁盘历史恢复最后状态。
        """
        state = self.prev_state

        # 如果本进程没做过 tick 但磁盘有历史，从最后一条恢复摘要
        if not state and self.tick_count > 0 and self.history:
            last = self.history[-1]
            return {
                "alive": True,
                "tick_count": self.tick_count,
                "H": last.get("H", 0),
                "H_coupling": last.get("H", 0),
                "H_field": 0.0,
                "T_eff": last.get("T_eff", 0),
                "hexagram_bits": last.get("bits", "000000"),
                "sigma": last.get("sigma", [0]*6),
                "scores": last.get("scores", [0.5]*6),
                "changing": last.get("changing", [False]*6),
                "direction": last.get("direction", "stable"),
                "delta_H": last.get("delta_H", 0.0),
                "crystal_field": self.crystal.h,
                "J_matrix_norm": sum(abs(self.coupling.J[i][j])
                                    for i in range(6) for j in range(6) if i != j),
            }

        if not state:
            return {"alive": False, "tick_count": 0}

        return {
            "alive": True,
            "tick_count": self.tick_count,
            "H": state.H,
            "H_coupling": state.H_coupling,
            "H_field": state.H_field,
            "T_eff": state.T_eff,
            "hexagram_bits": state.hexagram_bits,
            "sigma": state.sigma,
            "scores": [round(s, 3) for s in state.scores],
            "changing": state.changing,
            "direction": getattr(self, '_last_direction', 'stable'),
            "delta_H": getattr(self, '_last_delta_H', 0.0),
            "crystal_field": self.crystal.h,
            "J_matrix_norm": sum(abs(self.coupling.J[i][j])
                                for i in range(6) for j in range(6) if i != j),
        }

    def format_heartbeat(self) -> str:
        """格式化心跳状态（人话版）"""
        s = self.get_status()
        if not s["alive"]:
            return "太极OS 尚未启动心跳"

        # 与 hexagram_bits 同序（初爻在右 → sigma 也反序显示）
        sigma_str = "".join("阳" if v == 1 else "阴" for v in reversed(s["sigma"]))
        h_str = " ".join(f"{v:+.2f}" for v in s["crystal_field"])

        lines = [
            f"─── 太极OS 心跳 #{self.tick_count} ───",
            f"  卦象: {s['hexagram_bits']} ({sigma_str})",
            f"  能量: H={s['H']:.3f} (耦合{s['H_coupling']:.3f} + 外场{s['H_field']:.3f})",
            f"  温度: T={s['T_eff']:.2f} ({'临界' if s['T_eff'] >= 0.5 else '稳定' if s['T_eff'] <= 0.17 else '正常'})",
            f"  外场: [{h_str}]",
            f"  J范数: {s['J_matrix_norm']:.3f}",
        ]
        return "\n".join(lines)

    def _append_history(self, result: dict):
        """追加历史记录（含完整状态，供跨进程恢复用）"""
        # "应"关系耦合值：取 J[i][j] 和 J[j][i] 的均值
        J = self.coupling.J
        j_14 = round((J[0][3] + J[3][0]) / 2, 4)  # 初↔四 infra↔routing
        j_25 = round((J[1][4] + J[4][1]) / 2, 4)  # 二↔五 exec↔collab
        j_36 = round((J[2][5] + J[5][2]) / 2, 4)  # 三↔上 learn↔govern

        record = {
            "tick": result["tick"],
            "H": result["state"]["H"],
            "delta_H": result["delta_H"],
            "direction": result["direction"],
            "bits": result["hexagram_bits"],
            "T_eff": result["T_eff"],
            "sigma": result["state"]["sigma"],
            "scores": [round(s, 3) for s in result["state"]["scores"]],
            "changing": result["state"]["changing"],
            "J_yao_14": j_14,
            "J_yao_25": j_25,
            "J_yao_36": j_36,
            "timestamp": time.time(),
        }

        # 首次变卦里程碑
        if result["hexagram_changed"] and not self._first_change_recorded:
            record["milestone"] = "first_hexagram_change"
            self._first_change_recorded = True

        self.history.append(record)
        # 保留最近 500 条（够做趋势分析）
        if len(self.history) > 500:
            self.history = self.history[-500:]

    def _validate_transition(self, old_bits: str, new_bits: str,
                              flipped: list, delta_H: float,
                              T_eff: float) -> Optional[dict]:
        """
        多模型交叉验证卦变合理性。
        调用外部LLM判断：这个卦变在序卦传/易理上是否合理？
        返回验证结果 dict 或 None（如果验证不可用）。
        """
        try:
            from multi_llm import get_model, cross_validate
        except ImportError:
            return None

        # 只在重大卦变时验证（避免每个tick都调API）
        flipped_count = len(flipped)
        if flipped_count < 2 and abs(delta_H) < 0.15:
            return {"consensus": "minor_change_skipped", "validated": True}

        # 构造验证 prompt
        prompt = (
            f"I Ching hexagram transition validation.\n"
            f"Old hexagram: {old_bits} → New hexagram: {new_bits}\n"
            f"Flipped lines: {', '.join(flipped)} ({flipped_count} lines changed)\n"
            f"Energy change: ΔH={delta_H:+.4f}, Temperature: T={T_eff:.2f}\n\n"
            f"Is this transition plausible according to I Ching principles?\n"
            f"Consider: 序卦传 sequence logic, number of lines flipped, "
            f"whether adjacent hexagrams in any ordering.\n"
            f"Answer ONLY: PLAUSIBLE or IMPLAUSIBLE, then one sentence why."
        )

        try:
            results = cross_validate(prompt, models=["claude", "deepseek", "gemini", "gpt"],
                                     max_tokens=100, temperature=0)
            plausible_count = sum(
                1 for r in results.values()
                if isinstance(r, dict) and "answer" in r
                and "plausible" in r["answer"].lower()
                and "implausible" not in r["answer"].lower()
            )
            total = sum(1 for r in results.values()
                        if isinstance(r, dict) and "answer" in r)
            consensus = "validated" if plausible_count > total / 2 else "disputed"
            return {
                "consensus": consensus,
                "validated": consensus == "validated",
                "votes": f"{plausible_count}/{total}",
                "details": {k: v.get("answer", v.get("error", "?"))[:80]
                           for k, v in results.items()},
            }
        except Exception as e:
            logger.debug(f"Transition validation failed: {e}")
            return {"consensus": "validation_unavailable", "validated": True}

    def _load_history(self):
        path = self.data_dir / "pulse_history.json"
        if path.exists():
            try:
                self.history = json.loads(path.read_text(encoding="utf-8"))
                # 从历史恢复 tick_count，保证跨进程连续
                if self.history:
                    self.tick_count = max(h.get("tick", 0) for h in self.history)
                    # 恢复首次变卦里程碑标记
                    self._first_change_recorded = any(
                        h.get("milestone") == "first_hexagram_change"
                        for h in self.history
                    )
            except Exception:
                self.history = []

    def _save_history(self):
        """持久化 pulse history（需已持锁或由 save_all 调用）"""
        path = self.data_dir / "pulse_history.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def save_all(self):
        """持久化所有状态（线程安全）"""
        with self._lock:
            self.coupling.save()
            self.crystal.save()
            self._save_history()


# ============================================================
# Metrics 桥接 — 把 daily_metrics 输出转换成 hexagram_lines 的 18 维输入
# ============================================================

def metrics_from_daily(daily: Dict[str, any]) -> Dict[str, float]:
    """
    daily_metrics.collect_all_metrics() → hexagram_lines 18 维指标

    映射逻辑：
      infra:  success_rate → api_health, latency → network_latency, 默认依赖可用
      exec:   success_rate → task_success_rate, 推导 timeout/retry
      learn:  regeneration → hit_rate/gain/validity
      route:  fast_ratio → accuracy, pending → queue_length, 默认稳定
      collab: debate effectiveness → cooperation/sharing, conflict_rate
      govern: evolution 来自 health check, 默认 canary/stability
    """
    sr = daily.get("success_rate", 50.0) / 100.0  # 0~1
    lat = daily.get("avg_latency", 5.0)
    health_score = daily.get("health_score", 70.0)  # 来自外部注入
    tasks_total = daily.get("tasks_total", 1) or 1

    # 防御：嵌套字段可能不是 dict（上游格式不一致时降级为默认值）
    regen = daily.get("regeneration", {})
    if not isinstance(regen, dict):
        regen = {}
    router = daily.get("router", {})
    if not isinstance(router, dict):
        router = {}
    debate = daily.get("debate", {})
    if not isinstance(debate, dict):
        debate = {}
    failures = daily.get("failures", {})
    if not isinstance(failures, dict):
        failures = {}

    # 归一化 latency: 0s → lat_norm=1.0(好), 20s+ → lat_norm=0.0(差)
    lat_norm = max(0.0, min(1.0, 1.0 - lat / 20.0))
    # 注意：hexagram_lines 约定 network_latency "越高越差"（高值=高延迟），
    # 然后在 score_infra_line 中再 1.0-x 反转为"越高越好"的评分。
    # 所以这里输出 1.0-lat_norm，把"越高越好"翻成"越高越差"给 hexagram_lines。

    regen_rate = regen.get("rate", 50.0) / 100.0
    fast_ratio = router.get("fast_ratio", 60.0) / 100.0
    debate_eff = debate.get("effectiveness", {})
    if not isinstance(debate_eff, dict):
        debate_eff = {}
    debate_delta = debate_eff.get("debate_delta", 0.0)

    fail_total = failures.get("total", 0)
    fail_rate = min(1.0, fail_total / tasks_total)

    def _c(v):
        """clamp to [0, 1]"""
        return max(0.0, min(1.0, v))

    return {
        # infra (Line 1)
        "api_health": _c(sr * 0.7 + (1.0 - fail_rate) * 0.3),
        "network_latency": _c(1.0 - lat_norm),  # hexagram_lines 里 latency 越高越差
        "dependency_available": _c(0.4 + 0.4 * sr),  # smooth ramp，避免 sr=0.5 处跳变
        # execution (Line 2)
        "task_success_rate": _c(sr),
        "timeout_rate": _c(fail_rate * 0.6),
        "retry_rate": _c(fail_rate * 0.3),
        # learning (Line 3)
        "recommendation_hit_rate": _c(regen_rate * 0.8 + 0.2),
        "learning_gain": _c(regen_rate * 0.7 + 0.15),
        "experience_validity": _c(0.7 + regen_rate * 0.2),
        # routing (Line 4)
        "router_accuracy": _c(fast_ratio * 0.8 + 0.1),
        "queue_length": _c(daily.get("tasks_pending", 0) / 20.0),
        "dispatch_stability": _c(fast_ratio * 0.6 + 0.3),
        # collaboration (Line 5)
        "agent_cooperation": _c(0.6 + debate_delta / 30.0),
        "resource_sharing": _c(0.6 + fast_ratio * 0.2),
        "conflict_rate": _c(fail_rate * 0.4),
        # governance (Line 6) — evolution_score 保持 0~100 范围，hexagram_lines 内部会 /100
        "evolution_score": max(0.0, min(100.0, health_score)),
        "canary_health": _c(sr * 0.5 + 0.4),
        "global_stability": _c(sr * 0.4 + (1.0 - fail_rate) * 0.3 + 0.2),
    }


# ============================================================
# 便捷函数
# ============================================================

_global_pulse: Optional[Pulse] = None
_pulse_init_lock = threading.Lock()


def get_pulse() -> Pulse:
    """获取全局 Pulse 实例（线程安全）"""
    global _global_pulse
    if _global_pulse is None:
        with _pulse_init_lock:
            if _global_pulse is None:  # double-check locking
                _global_pulse = Pulse()
    return _global_pulse


def heartbeat(metrics: Dict[str, float]) -> dict:
    """全局心跳（一行调用）"""
    return get_pulse().tick(metrics)


def heartbeat_from_daily(daily: Dict[str, any]) -> dict:
    """从 daily_metrics 输出直接心跳（一行调用）"""
    return get_pulse().tick(metrics_from_daily(daily))


# ============================================================
# 测试 / CLI
# ============================================================

if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("=" * 55)
    print("  太极OS Ising 物理引擎 — 心跳测试")
    print("=" * 55)

    pulse = Pulse()

    # 场景 1: 健康系统
    print("\n── 场景 1: 健康系统 ──")
    metrics_healthy = {
        "api_health": 0.95, "network_latency": 0.1, "dependency_available": 0.9,
        "task_success_rate": 0.9, "timeout_rate": 0.05, "retry_rate": 0.03,
        "recommendation_hit_rate": 0.8, "learning_gain": 0.7, "experience_validity": 0.85,
        "router_accuracy": 0.88, "queue_length": 0.15, "dispatch_stability": 0.9,
        "agent_cooperation": 0.85, "resource_sharing": 0.8, "conflict_rate": 0.1,
        "evolution_score": 90, "canary_health": 0.9, "global_stability": 0.95,
    }
    r1 = pulse.tick(metrics_healthy)
    print(pulse.format_heartbeat())
    print(f"  方向: {r1['direction']}")
    print(f"  动作: {r1['actions']}")

    # 场景 2: 基础设施崩溃
    print("\n── 场景 2: 基础设施崩溃 ──")
    metrics_crash = {
        "api_health": 0.15, "network_latency": 0.9, "dependency_available": 0.2,
        "task_success_rate": 0.3, "timeout_rate": 0.7, "retry_rate": 0.6,
        "recommendation_hit_rate": 0.6, "learning_gain": 0.5, "experience_validity": 0.7,
        "router_accuracy": 0.5, "queue_length": 0.7, "dispatch_stability": 0.4,
        "agent_cooperation": 0.6, "resource_sharing": 0.5, "conflict_rate": 0.3,
        "evolution_score": 60, "canary_health": 0.5, "global_stability": 0.4,
    }
    r2 = pulse.tick(metrics_crash)
    print(pulse.format_heartbeat())
    print(f"  ΔH: {r2['delta_H']:+.3f} ({r2['direction']})")
    print(f"  卦变: {r2['hexagram_changed']}")
    print(f"  动作: {r2['actions']}")

    # 场景 3: 部分恢复
    print("\n── 场景 3: 部分恢复 ──")
    metrics_recovering = {
        "api_health": 0.6, "network_latency": 0.3, "dependency_available": 0.7,
        "task_success_rate": 0.5, "timeout_rate": 0.3, "retry_rate": 0.2,
        "recommendation_hit_rate": 0.65, "learning_gain": 0.6, "experience_validity": 0.75,
        "router_accuracy": 0.7, "queue_length": 0.3, "dispatch_stability": 0.7,
        "agent_cooperation": 0.7, "resource_sharing": 0.65, "conflict_rate": 0.15,
        "evolution_score": 75, "canary_health": 0.7, "global_stability": 0.7,
    }
    r3 = pulse.tick(metrics_recovering)
    print(pulse.format_heartbeat())
    print(f"  ΔH: {r3['delta_H']:+.3f} ({r3['direction']})")
    print(f"  动作: {r3['actions']}")

    # 场景 4: 全面恢复
    print("\n── 场景 4: 全面恢复 ──")
    r4 = pulse.tick(metrics_healthy)
    print(pulse.format_heartbeat())
    print(f"  ΔH: {r4['delta_H']:+.3f} ({r4['direction']})")
    print(f"  动作: {r4['actions']}")

    # 打印 J 矩阵变化
    print("\n── J 矩阵 (学习后) ──")
    for i, row in enumerate(pulse.coupling.J):
        label = YAO_LABELS[i]
        vals = " ".join(f"{v:+.3f}" for v in row)
        print(f"  {label:>13}: [{vals}]")

    # 打印外场
    print("\n── Crystal 外场 h (学习后) ──")
    for i, h in enumerate(pulse.crystal.h):
        print(f"  {YAO_LABELS[i]:>13}: {h:+.4f}")

    pulse.save_all()

    print(f"\n{'=' * 55}")
    print("  心跳测试完成。太极OS 活了。")
    print(f"{'=' * 55}")
