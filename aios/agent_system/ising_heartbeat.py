#!/usr/bin/env python3
"""
Ising Heartbeat — 独立心跳脚本

用法：
  python ising_heartbeat.py          # 单次心跳（用当天真实 daily_metrics）
  python ising_heartbeat.py --loop   # 持续心跳，每 60s 一次
  python ising_heartbeat.py --status # 查看当前状态

每次运行做一次真实 tick：
  1. collect_all_metrics() 获取当日指标
  2. metrics_from_daily() 转换为 18 维输入
  3. Pulse.tick() 计算 Ising 物理状态
  4. 持久化 J/crystal/history

数据目录: data/ising/
  coupling_matrix.json  — J 耦合矩阵（Hebbian 学习）
  crystal_field.json    — h 外场（能量驱动自适应）
  pulse_history.json    — 心跳历史记录

Author: TaijiOS
Date: 2026-04-15
"""

import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from daily_metrics import collect_all_metrics
from ising_core import heartbeat_from_daily, get_pulse


def do_heartbeat(health_score: float = None, verbose: bool = True) -> dict:
    """执行一次真实心跳"""
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")

    # 1. 收集真实指标
    daily = collect_all_metrics(today)

    # 2. 注入健康评分（如果没有外部提供，从指标推算）
    if health_score is None:
        sr = daily.get("success_rate", 0.0)
        lat = daily.get("avg_latency", 10.0)
        # 简易健康分：成功率 70% + 延迟反向 30%
        health_score = sr * 0.7 + max(0, 100 - lat * 5) * 0.3
    daily["health_score"] = health_score

    # 3. Ising tick
    result = heartbeat_from_daily(daily)

    # 4. 强制保存（积累期每次都存）
    pulse = get_pulse()
    pulse.save_all()

    # 5. 输出
    if verbose:
        tick = result["tick"]
        H = result["state"]["H"]
        dH = result["delta_H"]
        bits = result["hexagram_bits"]
        T = result["T_eff"]
        direction = result["direction"]
        changed = result["hexagram_changed"]
        sigma = result["state"]["sigma"]

        # 卦名查询
        try:
            from hexagram_mapping import map_binary_to_hexagram
            info = map_binary_to_hexagram(bits)
            hex_name = info.name
            hex_risk = info.risk.value
        except Exception:
            hex_name = "?"
            hex_risk = "?"

        sigma_str = "".join("+" if s == 1 else "-" for s in sigma)

        print(f"[{now}] tick #{tick}")
        print(f"  卦象: {bits} = {hex_name} ({hex_risk})")
        print(f"  sigma: [{sigma_str}] (infra exec learn route collab govern)")
        print(f"  能量: H={H:.3f}  ΔH={dH:+.3f}  方向={direction}")
        print(f"  温度: T={T:.2f}  卦变={changed}")
        if result["actions"]:
            print(f"  动作: {', '.join(result['actions'][:5])}")

        # 输入指标摘要
        sr = daily.get("success_rate", 0)
        lat = daily.get("avg_latency", 0)
        tasks = daily.get("tasks_total", 0)
        pending = daily.get("tasks_pending", 0)
        print(f"  输入: sr={sr:.1f}% lat={lat:.1f}s tasks={tasks} pending={pending} health={health_score:.1f}")

    return result


def show_status():
    """显示当前 Ising 引擎状态"""
    pulse = get_pulse()
    s = pulse.get_status()

    if not s["alive"]:
        print("太极OS Ising 引擎尚未产生心跳")
        return

    # 卦名
    try:
        from hexagram_mapping import map_binary_to_hexagram
        info = map_binary_to_hexagram(s["hexagram_bits"])
        hex_name = info.name
    except Exception:
        hex_name = "?"

    print(f"═══ 太极OS Ising 引擎状态 ═══")
    print(f"  心跳数: {s['tick_count']}")
    print(f"  卦象:   {s['hexagram_bits']} = {hex_name}")
    print(f"  能量:   H={s['H']:.3f} (耦合{s['H_coupling']:.3f} + 外场{s['H_field']:.3f})")
    print(f"  温度:   T={s['T_eff']:.2f}")
    print(f"  方向:   {s.get('direction', 'N/A')}")
    print(f"  J范数:  {s['J_matrix_norm']:.3f}")

    # 外场
    labels = ["infra", "exec", "learn", "route", "collab", "govern"]
    h = s["crystal_field"]
    print(f"  外场:   " + "  ".join(f"{labels[i]}={h[i]:+.3f}" for i in range(6)))

    # 历史记录数
    data_dir = Path(__file__).parent / "data" / "ising"
    hist_path = data_dir / "pulse_history.json"
    if hist_path.exists():
        try:
            hist = json.loads(hist_path.read_text(encoding="utf-8"))
            print(f"  历史:   {len(hist)} 条记录")
            if hist:
                first = hist[0].get("timestamp", 0)
                last = hist[-1].get("timestamp", 0)
                if first and last:
                    span = (last - first) / 3600
                    print(f"  跨度:   {span:.1f} 小时 ({datetime.fromtimestamp(first).strftime('%m-%d %H:%M')} → {datetime.fromtimestamp(last).strftime('%m-%d %H:%M')})")
        except Exception:
            pass


def loop_heartbeat(interval: int = 60):
    """持续心跳循环"""
    print(f"太极OS Ising 心跳循环启动 (间隔 {interval}s, Ctrl+C 停止)")
    print("=" * 50)

    count = 0
    try:
        while True:
            count += 1
            try:
                do_heartbeat(verbose=True)
            except Exception as e:
                print(f"  [ERROR] {e}")
            print()

            if count % 10 == 0:
                show_status()
                print()

            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n心跳停止，共 {count} 次")
        show_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="太极OS Ising Heartbeat")
    parser.add_argument("--loop", action="store_true", help="持续心跳模式")
    parser.add_argument("--interval", type=int, default=60, help="心跳间隔秒数 (默认60)")
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    parser.add_argument("--health", type=float, default=None, help="手动指定健康评分")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.loop:
        loop_heartbeat(args.interval)
    else:
        do_heartbeat(health_score=args.health)
