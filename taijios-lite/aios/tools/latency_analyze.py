"""
TaijiOS 延迟归因分析 CLI

用法：
    python -m aios.tools.latency_analyze                    # 今天
    python -m aios.tools.latency_analyze --date 20260416    # 指定日期
    python -m aios.tools.latency_analyze --days 7           # 最近7天
"""

import argparse
import statistics
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from aios.core.latency_logger import LatencyLogger


def percentile(data: list[float], p: int) -> float:
    """计算分位数（不依赖 numpy/pandas）"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def analyze(records: list[dict]) -> None:
    """分析并打印报告"""
    if not records:
        print("无记录。")
        return

    total = len(records)
    print(f"\n总调用: {total} 次")
    print("=" * 50)

    # ── 延迟分析 ──────────────────────────────────
    total_ms_list = [r.get("total_ms", 0) for r in records if r.get("total_ms")]
    gen_ms_list = [r.get("generation_ms", 0) for r in records if r.get("generation_ms")]
    val_ms_list = [r.get("verification_ms", 0) for r in records if r.get("verification_ms")]

    if total_ms_list:
        print(f"\n延迟 (total_ms):")
        print(f"  均值: {statistics.mean(total_ms_list):.0f}ms")
        print(f"  p50:  {percentile(total_ms_list, 50):.0f}ms")
        print(f"  p95:  {percentile(total_ms_list, 95):.0f}ms")
        print(f"  p99:  {percentile(total_ms_list, 99):.0f}ms")

    if gen_ms_list:
        print(f"\n生成延迟 (generation_ms):")
        print(f"  均值: {statistics.mean(gen_ms_list):.0f}ms")
        print(f"  p50:  {percentile(gen_ms_list, 50):.0f}ms")
        print(f"  p95:  {percentile(gen_ms_list, 95):.0f}ms")

    if val_ms_list:
        print(f"\n验证延迟 (verification_ms):")
        print(f"  均值: {statistics.mean(val_ms_list):.0f}ms")
        print(f"  p50:  {percentile(val_ms_list, 50):.0f}ms")
        print(f"  p95:  {percentile(val_ms_list, 95):.0f}ms")

    # ── 模型分布 ──────────────────────────────────
    chain_counter = Counter(r.get("model_chain", "unknown") for r in records)
    print(f"\n模型链分布:")
    for chain, count in chain_counter.most_common():
        print(f"  {chain}: {count} ({count/total*100:.1f}%)")

    # ── 验证状态分布 ──────────────────────────────
    status_counter = Counter(r.get("verification_status", "unknown") for r in records)
    print(f"\n验证状态:")
    for status, count in status_counter.most_common():
        print(f"  {status}: {count} ({count/total*100:.1f}%)")

    # ── modified 率 ──────────────────────────────
    modified_count = sum(1 for r in records if r.get("modified"))
    print(f"\n修正率: {modified_count}/{total} ({modified_count/total*100:.1f}%)")

    # ── 规则触发 ──────────────────────────────────
    rule_counter = Counter()
    triggered_calls = 0
    for r in records:
        rules = r.get("triggered_rules", [])
        if rules:
            triggered_calls += 1
            for rule in rules:
                name = rule["rule"] if isinstance(rule, dict) else rule
                rule_counter[name] += 1

    if rule_counter:
        print(f"\n规则触发 ({triggered_calls}/{total} 次调用命中):")
        for rule, count in rule_counter.most_common():
            print(f"  {rule}: {count} 次 ({count/total*100:.1f}%)")
    else:
        print(f"\n规则触发: 无")

    # ── 降级统计 ──────────────────────────────────
    degraded_count = sum(1 for r in records if r.get("degraded"))
    if degraded_count:
        reasons = Counter(r.get("degradation_reason", "unknown") for r in records if r.get("degraded"))
        print(f"\n降级: {degraded_count} 次 ({degraded_count/total*100:.1f}%)")
        for reason, count in reasons.most_common():
            print(f"  {reason}: {count}")

    # ── Ising 心跳 ──────────────────────────────
    block_count = sum(1 for r in records if r.get("block_fallback"))
    if block_count:
        print(f"\nIsing 禁止降级: {block_count} 次")

    print()


def main():
    parser = argparse.ArgumentParser(description="TaijiOS 延迟归因分析")
    parser.add_argument("--date", type=str, help="日期 YYYYMMDD（默认今天）")
    parser.add_argument("--days", type=int, default=1, help="分析最近N天（默认1）")
    parser.add_argument("--log-dir", type=str, default=None, help="日志目录")
    args = parser.parse_args()

    ll = LatencyLogger(args.log_dir) if args.log_dir else LatencyLogger()

    if args.date:
        d = date(int(args.date[:4]), int(args.date[4:6]), int(args.date[6:8]))
        days = [d]
    else:
        today = date.today()
        days = [today - timedelta(days=i) for i in range(args.days)]

    all_records = []
    for d in sorted(days):
        records = ll.read_day(d)
        if records:
            print(f"--- {d} ({len(records)} 条) ---")
            all_records.extend(records)

    if args.days > 1 and all_records:
        print(f"\n{'='*50}")
        print(f"合计 {len(days)} 天")

    analyze(all_records)


if __name__ == "__main__":
    main()
