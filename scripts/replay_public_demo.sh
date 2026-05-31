#!/usr/bin/env bash
set -euo pipefail

RUNS=1
PYTHON_BIN="${PYTHON:-python3}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runs)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for --runs\n' >&2
        exit 2
      fi
      RUNS="${2:-}"
      shift 2
      ;;
    --python)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for --python\n' >&2
        exit 2
      fi
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    -h|--help)
      printf 'Usage: %s [--runs N] [--python python3]\n' "$0"
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if ! [[ "$RUNS" =~ ^[0-9]+$ ]] || [[ "$RUNS" -lt 1 ]]; then
  printf 'Invalid --runs value: %s\n' "$RUNS" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT"

for run_id in $(seq 1 "$RUNS"); do
  "$PYTHON_BIN" examples/quickstart_minimal.py >/dev/null
  "$PYTHON_BIN" - "$ROOT" "$run_id" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
run_id = sys.argv[2]
out = root / "examples" / "quickstart_output"

evidence = json.loads((out / "quickstart_evidence.json").read_text(encoding="utf-8"))
json.loads((out / "quickstart_trace.json").read_text(encoding="utf-8"))
json.loads((out / "quickstart_events.json").read_text(encoding="utf-8"))

expected = {
    "total_tasks": 3,
    "succeeded": 3,
    "self_healed": 3,
    "event_log_count": 18,
}

for key, value in expected.items():
    actual = evidence.get(key)
    if actual != value:
        raise SystemExit(
            f"run={run_id} verdict=BLOCKED key={key} expected={value} actual={actual}"
        )

print(
    "run={run} verdict=PASS tasks={tasks} succeeded={succeeded} "
    "self_healed={healed} events={events}".format(
        run=run_id,
        tasks=evidence["total_tasks"],
        succeeded=evidence["succeeded"],
        healed=evidence["self_healed"],
        events=evidence["event_log_count"],
    )
)
PY
done

printf 'verdict=PASS scope=local_public_demo_replay runs=%s\n' "$RUNS"
