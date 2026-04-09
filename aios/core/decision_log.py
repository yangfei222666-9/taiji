#!/usr/bin/env python3
# aios/core/decision_log.py - 决策透明度系统
"""
决策审计系统，记录"为什么这么做"。

Schema:
{
  "id": "uuid",
  "ts": "ISO-8601",
  "epoch": unix_seconds,
  "context": "决策场景描述",
  "options": ["选项1", "选项2", ...],
  "chosen": "最终选择",
  "reason": "选择理由",
  "confidence": 0.0-1.0,
  "outcome": "pending|success|fail"
}
"""

import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import get_path


def _decisions_path() -> Path:
    """获取决策日志路径"""
    base = get_path("paths.data")
    if base:
        return base / "decisions.jsonl"
    return Path(__file__).resolve().parent.parent / "data" / "decisions.jsonl"


def _append_jsonl(path: Path, obj: dict):
    """追加 JSONL 记录"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def log_decision(
    context: str, options: List[str], chosen: str, reason: str, confidence: float = 0.5
) -> str:
    """
    记录一次决策。

    Args:
        context: 决策场景描述
        options: 可选项列表
        chosen: 最终选择
        reason: 选择理由
        confidence: 信心度 (0.0-1.0)

    Returns:
        决策 ID (uuid)
    """
    decision_id = str(uuid.uuid4())
    record = {
        "id": decision_id,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "epoch": int(time.time()),
        "context": context,
        "options": options,
        "chosen": chosen,
        "reason": reason,
        "confidence": max(0.0, min(1.0, confidence)),
        "outcome": "pending",
    }
    _append_jsonl(_decisions_path(), record)
    return decision_id


def get_decision(decision_id: str) -> Optional[Dict]:
    """根据 ID 获取决策记录"""
    path = _decisions_path()
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if record.get("id") == decision_id:
                    return record
            except Exception:
                continue
    return None


def update_outcome(decision_id: str, outcome: str) -> bool:
    """
    更新决策结果。

    Args:
        decision_id: 决策 ID
        outcome: 结果 (success|fail)

    Returns:
        是否更新成功
    """
    if outcome not in ("success", "fail"):
        return False

    path = _decisions_path()
    if not path.exists():
        return False

    # 读取所有记录
    records = []
    updated = False
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if record.get("id") == decision_id:
                    record["outcome"] = outcome
                    updated = True
                records.append(record)
            except Exception:
                continue

    if not updated:
        return False

    # 重写文件
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return True


def query_decisions(
    since_days: int = 7,
    context: Optional[str] = None,
    confidence_min: Optional[float] = None,
    outcome: Optional[str] = None,
) -> List[Dict]:
    """
    查询决策记录。

    Args:
        since_days: 查询最近 N 天
        context: 按 context 关键词过滤
        confidence_min: 最低信心度过滤
        outcome: 按结果过滤 (pending|success|fail)

    Returns:
        符合条件的决策列表
    """
    path = _decisions_path()
    if not path.exists():
        return []

    cutoff = time.time() - since_days * 86400
    results = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)

                # 时间过滤
                if record.get("epoch", 0) < cutoff:
                    continue

                # context 过滤
                if context and context.lower() not in record.get("context", "").lower():
                    continue

                # confidence 过滤
                if (
                    confidence_min is not None
                    and record.get("confidence", 0) < confidence_min
                ):
                    continue

                # outcome 过滤
                if outcome and record.get("outcome") != outcome:
                    continue

                results.append(record)
            except Exception:
                continue

    return results


def decision_stats(since_days: int = 30) -> Dict:
    """
    决策统计。

    Returns:
        {
            "total": 总决策数,
            "success_rate": 成功率,
            "avg_confidence": 平均信心度,
            "by_context": {context: count},
            "by_outcome": {outcome: count}
        }
    """
    decisions = query_decisions(since_days=since_days)

    if not decisions:
        return {
            "total": 0,
            "success_rate": 0.0,
            "avg_confidence": 0.0,
            "by_context": {},
            "by_outcome": {},
        }

    total = len(decisions)
    success_count = sum(1 for d in decisions if d.get("outcome") == "success")
    completed = sum(1 for d in decisions if d.get("outcome") in ("success", "fail"))

    success_rate = success_count / completed if completed > 0 else 0.0
    avg_confidence = sum(d.get("confidence", 0) for d in decisions) / total

    # 按 context 统计
    by_context = {}
    for d in decisions:
        ctx = d.get("context", "unknown")
        by_context[ctx] = by_context.get(ctx, 0) + 1

    # 按 outcome 统计
    by_outcome = {}
    for d in decisions:
        out = d.get("outcome", "unknown")
        by_outcome[out] = by_outcome.get(out, 0) + 1

    return {
        "total": total,
        "success_rate": round(success_rate, 3),
        "avg_confidence": round(avg_confidence, 3),
        "by_context": by_context,
        "by_outcome": by_outcome,
    }


# ── CLI ──


def _format_decision(d: Dict, fmt: str = "default") -> str:
    """格式化单条决策"""
    if fmt == "telegram":
        outcome_emoji = {"pending": "⏳", "success": "✅", "fail": "❌"}.get(
            d.get("outcome"), "❓"
        )
        conf = d.get("confidence", 0)
        return (
            f"{outcome_emoji} {d.get('context', 'N/A')[:40]}\n"
            f"  选择: {d.get('chosen', 'N/A')}\n"
            f"  信心: {conf:.1%} | {d.get('ts', 'N/A')}"
        )
    else:
        return (
            f"[{d.get('id', 'N/A')[:8]}] {d.get('ts', 'N/A')}\n"
            f"  Context: {d.get('context', 'N/A')}\n"
            f"  Options: {', '.join(d.get('options', []))}\n"
            f"  Chosen: {d.get('chosen', 'N/A')}\n"
            f"  Reason: {d.get('reason', 'N/A')}\n"
            f"  Confidence: {d.get('confidence', 0):.2f}\n"
            f"  Outcome: {d.get('outcome', 'N/A')}"
        )


def _format_stats(stats: Dict, fmt: str = "default") -> str:
    """格式化统计信息"""
    if fmt == "telegram":
        return (
            f"📊 决策统计\n"
            f"总数: {stats['total']} | 成功率: {stats['success_rate']:.1%}\n"
            f"平均信心: {stats['avg_confidence']:.1%}\n"
            f"结果分布: {stats['by_outcome']}"
        )
    else:
        lines = [
            "=== Decision Statistics ===",
            f"Total: {stats['total']}",
            f"Success Rate: {stats['success_rate']:.1%}",
            f"Avg Confidence: {stats['avg_confidence']:.2f}",
            "",
            "By Context:",
        ]
        for ctx, cnt in stats["by_context"].items():
            lines.append(f"  {ctx}: {cnt}")
        lines.append("")
        lines.append("By Outcome:")
        for out, cnt in stats["by_outcome"].items():
            lines.append(f"  {out}: {cnt}")
        return "\n".join(lines)


def main():
    import argparse
    import sys
    import io

    # 修复 Windows 控制台编码
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    parser = argparse.ArgumentParser(description="决策日志 CLI")
    parser.add_argument("action", choices=["list", "stats", "query"], help="操作")
    parser.add_argument("--days", type=int, default=7, help="查询天数")
    parser.add_argument("--context", help="按 context 过滤")
    parser.add_argument("--confidence", type=float, help="最低信心度")
    parser.add_argument(
        "--outcome", choices=["pending", "success", "fail"], help="按结果过滤"
    )
    parser.add_argument(
        "--format", choices=["default", "telegram"], default="default", help="输出格式"
    )
    args = parser.parse_args()

    if args.action == "list":
        decisions = query_decisions(since_days=args.days)
        if not decisions:
            print("无决策记录")
            return
        for d in decisions[-20:]:  # 最近 20 条
            print(_format_decision(d, args.format))
            print()

    elif args.action == "stats":
        stats = decision_stats(since_days=args.days)
        print(_format_stats(stats, args.format))

    elif args.action == "query":
        decisions = query_decisions(
            since_days=args.days,
            context=args.context,
            confidence_min=args.confidence,
            outcome=args.outcome,
        )
        print(f"找到 {len(decisions)} 条记录")
        for d in decisions:
            print(_format_decision(d, args.format))
            print()


if __name__ == "__main__":
    main()
