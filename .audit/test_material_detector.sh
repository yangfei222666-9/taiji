#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

STATE_DIR="$TMPDIR/state"
FIXTURE_ROOT="$TMPDIR/fixtures"
ARTIFACT_DIR="$FIXTURE_ROOT/latest-build"
mkdir -p "$STATE_DIR" "$ARTIFACT_DIR"
printf 'alpha\n' > "$ARTIFACT_DIR/build.txt"

run_detector() {
  local out_dir="$1"
  shift
  (
    cd "$ROOT_DIR"
    STATE_DIR="$STATE_DIR" \
    AUDIT_OUT_DIR="$out_dir" \
    LOCAL_ARTIFACT_ROOT="$FIXTURE_ROOT" \
    LOCAL_RUN_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    REKOR_REQUIRED=0 \
    REKOR_OFFLINE_MODE=1 \
    COSIGN_VERIFY_REQUIRED=0 \
    AUDIT_EMIT_ENABLED=1 \
    "$@" \
    ./.audit/material_detector.sh
  )
}

assert_jq() {
  local file="$1"
  local query="$2"
  jq -e "$query" "$file" >/dev/null
}

OUT1="$TMPDIR/out1"
run_detector "$OUT1" > "$TMPDIR/run1.log"
grep -q "TAIJIOS AUDIT PULSE" "$TMPDIR/run1.log"
assert_jq "$OUT1/summary.json" '.verdict == "PARTIAL" and .material_changed == true and .pulse_emitted == true'
jq -e . "$OUT1/event_flow.jsonl" >/dev/null

OUT2="$TMPDIR/out2"
run_detector "$OUT2" > "$TMPDIR/run2.log"
if grep -q "TAIJIOS AUDIT PULSE" "$TMPDIR/run2.log"; then
  echo "expected unchanged run to suppress pulse" >&2
  exit 1
fi
assert_jq "$OUT2/summary.json" '.verdict == "PARTIAL" and .material_changed == false and .pulse_emitted == false'

printf 'beta\n' > "$ARTIFACT_DIR/build.txt"
OUT3="$TMPDIR/out3"
run_detector "$OUT3" > "$TMPDIR/run3.log"
grep -q "TAIJIOS AUDIT PULSE" "$TMPDIR/run3.log"
assert_jq "$OUT3/summary.json" '.verdict == "PARTIAL" and .material_changed == true and .pulse_emitted == true'

OUT4="$TMPDIR/out4"
set +e
(
  cd "$ROOT_DIR"
  STATE_DIR="$TMPDIR/blocked-state" \
  AUDIT_OUT_DIR="$OUT4" \
  LOCAL_ARTIFACT_ROOT="$FIXTURE_ROOT" \
  LOCAL_RUN_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  REKOR_REQUIRED=1 \
  REKOR_OFFLINE_MODE=0 \
  FORCE_REKOR_UNAVAILABLE=1 \
  AUDIT_EMIT_ENABLED=0 \
  ./.audit/material_detector.sh
) > "$TMPDIR/run4.log" 2>&1
status=$?
set -e
if [ "$status" -ne 2 ]; then
  echo "expected Rekor unavailable case to exit 2, got $status" >&2
  cat "$TMPDIR/run4.log" >&2
  exit 1
fi
assert_jq "$OUT4/summary.json" '.verdict == "BLOCKED" and .blocked_stage == "rekor" and .pulse_emitted == false'

echo "material detector fixture tests passed"
