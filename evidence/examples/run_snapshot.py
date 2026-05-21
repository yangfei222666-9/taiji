#!/usr/bin/env python3
"""Create a local mock learning-only evidence snapshot.

This entrypoint is intentionally narrow: it never calls live providers and it
refuses judgment/trading modes.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=["learning_only"])
    parser.add_argument("--provider", required=True, choices=["mock"])
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    evidence_root = Path(__file__).resolve().parents[1]
    source_snapshot = evidence_root / "examples" / "snapshot.json"
    with source_snapshot.open("r", encoding="utf-8") as fh:
        snapshot = json.load(fh)

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    output = {
        "status": "ok_learning_only",
        "mode": args.mode,
        "provider": args.provider,
        "provider_live": False,
        "judgment_allowed": False,
        "paper_buy_allowed": False,
        "trade_allowed": False,
        "promote_allowed": False,
        "generated_at": generated_at,
        "source_snapshot": snapshot,
        "event_flow": [
            {
                "stage": "mock_snapshot",
                "status": "ok_learning_only",
                "provider": "mock",
                "mode": "learning_only",
                "live_execution": False,
                "judgment_execution": "blocked",
                "trade_execution": "blocked",
            }
        ],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
