#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${STATE_DIR:-.audit/state}"
AUDIT_OUT_DIR="${AUDIT_OUT_DIR:-.audit/out/local}"
MATERIAL_GATE_HOURS="${MATERIAL_GATE_HOURS:-72}"
SIGSTORE_REKOR_SERVER="${SIGSTORE_REKOR_SERVER:-https://rekor.sigstore.dev}"
REKOR_REQUIRED="${REKOR_REQUIRED:-1}"
REKOR_OFFLINE_MODE="${REKOR_OFFLINE_MODE:-0}"
COSIGN_VERIFY_REQUIRED="${COSIGN_VERIFY_REQUIRED:-0}"
COSIGN_CERT_IDENTITY="${COSIGN_CERT_IDENTITY:-}"
COSIGN_CERT_IDENTITY_REGEXP="${COSIGN_CERT_IDENTITY_REGEXP:-}"
COSIGN_CERT_OIDC_ISSUER="${COSIGN_CERT_OIDC_ISSUER:-}"
COSIGN_CERT_OIDC_ISSUER_REGEXP="${COSIGN_CERT_OIDC_ISSUER_REGEXP:-}"
AUDIT_EMIT_ENABLED="${AUDIT_EMIT_ENABLED:-1}"

WORKDIR="$(mktemp -d)"
ARTIFACT_ROOT="$WORKDIR/artifacts"
EVENT_FLOW="$AUDIT_OUT_DIR/event_flow.jsonl"
SUMMARY_JSON="$AUDIT_OUT_DIR/summary.json"
MANIFEST_JSON="$AUDIT_OUT_DIR/manifest.json"
SHA_FILE="$AUDIT_OUT_DIR/sha256.txt"
REKOR_FILE="$AUDIT_OUT_DIR/rekor.txt"
SIGSTORE_JSON="$AUDIT_OUT_DIR/sigstore.json"
PULSE_FILE="$AUDIT_OUT_DIR/pulse.txt"
RUN_PAYLOAD="$AUDIT_OUT_DIR/run_payload.json"
ARTIFACTS_PAYLOAD="$AUDIT_OUT_DIR/artifacts.json"

mkdir -p "$STATE_DIR" "$AUDIT_OUT_DIR" "$ARTIFACT_ROOT"
trap 'rm -rf "$WORKDIR"' EXIT

: > "$EVENT_FLOW"
: > "$SHA_FILE"
: > "$REKOR_FILE"

record_event() {
  local stage="$1"
  local status="$2"
  local detail="${3:-}"
  jq -cn \
    --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --arg stage "$stage" \
    --arg status "$status" \
    --arg detail "$detail" \
    '{ts:$ts, stage:$stage, status:$status, detail:$detail}' >> "$EVENT_FLOW"
}

write_summary() {
  local verdict="$1"
  local blocked_stage="$2"
  local failure_cause="$3"
  local material_changed="$4"
  local pulse_emitted="$5"
  local run_id="$6"
  local run_ts="$7"
  local run_age_hours="$8"
  jq -n \
    --arg verdict "$verdict" \
    --arg blocked_stage "$blocked_stage" \
    --arg failure_cause "$failure_cause" \
    --arg material_changed "$material_changed" \
    --arg pulse_emitted "$pulse_emitted" \
    --arg run_id "$run_id" \
    --arg run_ts "$run_ts" \
    --arg run_age_hours "$run_age_hours" \
    --arg evidence_path "$AUDIT_OUT_DIR" \
    --arg rekor_required "$REKOR_REQUIRED" \
    --arg cosign_verify_required "$COSIGN_VERIFY_REQUIRED" \
    '{
      verdict: $verdict,
      blocked_stage: (if $blocked_stage == "" then null else $blocked_stage end),
      failure_cause: (if $failure_cause == "" then null else $failure_cause end),
      material_changed: ($material_changed == "1"),
      pulse_emitted: ($pulse_emitted == "1"),
      run_id: (if $run_id == "" then null else $run_id end),
      run_created_at: (if $run_ts == "" then null else $run_ts end),
      run_age_hours: (if $run_age_hours == "" then null else ($run_age_hours | tonumber) end),
      evidence_path: $evidence_path,
      rekor_required: ($rekor_required == "1"),
      cosign_verify_required: ($cosign_verify_required == "1"),
      claims: {
        material_change_detector: true,
        low_noise_audit_pulse: true,
        evidence_linked_notification: true,
        rekor_aware_audit: true,
        reproducible_build_verified: false,
        provenance_verified: false,
        slsa_compliant: false,
        signed_artifact_trusted: false,
        repo_wide_integrity_verified: false
      }
    }' > "$SUMMARY_JSON"
}

fail_blocked() {
  local blocked_stage="$1"
  local failure_cause="$2"
  local run_id="${3:-}"
  local run_ts="${4:-}"
  local run_age_hours="${5:-}"
  record_event "$blocked_stage" "blocked" "$failure_cause"
  write_summary "BLOCKED" "$blocked_stage" "$failure_cause" "0" "0" "$run_id" "$run_ts" "$run_age_hours"
  echo "[audit] BLOCKED stage=${blocked_stage} cause=${failure_cause}" >&2
  exit 2
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    fail_blocked "preflight" "missing command: ${cmd}"
  fi
}

portable_age_hours() {
  local iso_ts="$1"
  python3 - "$iso_ts" <<'PY'
import datetime
import sys

raw = sys.argv[1]
if raw.endswith("Z"):
    raw = raw[:-1] + "+00:00"
created = datetime.datetime.fromisoformat(raw)
now = datetime.datetime.now(datetime.timezone.utc)
print(int((now - created).total_seconds() // 3600))
PY
}

github_get() {
  local url="$1"
  curl -fsSL \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${GH_TOKEN}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$url"
}

safe_name() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_'
}

select_github_run_with_artifacts() {
  local owner="$1"
  local repo="$2"
  local runs_json="$WORKDIR/runs.json"
  local current_run_id="${GITHUB_RUN_ID:-}"
  local workflow_filter="${AUDIT_SOURCE_WORKFLOW:-}"

  github_get "https://api.github.com/repos/${owner}/${repo}/actions/runs?status=success&per_page=20" > "$runs_json"
  cp "$runs_json" "$RUN_PAYLOAD"

  mapfile -t candidate_ids < <(
    jq -r \
      --arg current_run_id "$current_run_id" \
      --arg workflow_filter "$workflow_filter" \
      '.workflow_runs[]
        | select((.id | tostring) != $current_run_id)
        | select($workflow_filter == "" or .name == $workflow_filter or .path == $workflow_filter or (.path | endswith("/" + $workflow_filter)))
        | .id' "$runs_json"
  )

  for candidate_id in "${candidate_ids[@]}"; do
    local artifacts_json="$WORKDIR/artifacts_${candidate_id}.json"
    github_get "https://api.github.com/repos/${owner}/${repo}/actions/runs/${candidate_id}/artifacts" > "$artifacts_json"
    if [ "$(jq -r '.total_count // 0' "$artifacts_json")" -gt 0 ]; then
      jq -r \
        --arg id "$candidate_id" \
        '.workflow_runs[] | select((.id | tostring) == $id) | [.id, .created_at] | @tsv' "$runs_json"
      cp "$artifacts_json" "$ARTIFACTS_PAYLOAD"
      return 0
    fi
  done

  return 1
}

collect_github_artifacts() {
  if [ -z "${GH_TOKEN:-}" ]; then
    fail_blocked "github_fetch" "GH_TOKEN missing"
  fi
  if [ -z "${GITHUB_REPOSITORY:-}" ]; then
    fail_blocked "github_fetch" "GITHUB_REPOSITORY missing"
  fi

  local owner="${GITHUB_REPOSITORY%/*}"
  local repo="${GITHUB_REPOSITORY#*/}"
  local selected

  record_event "github_fetch" "started" "fetching latest successful run with artifacts"
  if ! selected="$(select_github_run_with_artifacts "$owner" "$repo")"; then
    record_event "github_fetch" "pending" "no successful run with artifacts found"
    write_summary "PENDING" "" "no successful run with artifacts found" "0" "0" "" "" ""
    echo "[audit] no successful run with artifacts found"
    exit 0
  fi

  RUN_ID="$(printf '%s' "$selected" | awk '{print $1}')"
  RUN_TS="$(printf '%s' "$selected" | awk '{print $2}')"
  record_event "github_fetch" "ok" "run_id=${RUN_ID}"

  local idx=0
  jq -c '.artifacts[]' "$ARTIFACTS_PAYLOAD" | while IFS= read -r artifact; do
    idx=$((idx + 1))
    local name url target zip_path safe
    name="$(printf '%s' "$artifact" | jq -r '.name')"
    url="$(printf '%s' "$artifact" | jq -r '.archive_download_url')"
    safe="$(safe_name "$name")"
    target="$ARTIFACT_ROOT/${idx}_${safe}"
    zip_path="$WORKDIR/${idx}_${safe}.zip"
    mkdir -p "$target"
    curl -fsSL \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer ${GH_TOKEN}" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "$url" \
      -o "$zip_path"
    unzip -q "$zip_path" -d "$target"
    printf '%s\t%s\t%s\n' "$name" "$target" "$(printf '%s' "$artifact" | jq -r '.updated_at')" >> "$WORKDIR/artifact_dirs.tsv"
  done
}

collect_local_artifacts() {
  local local_root="${LOCAL_ARTIFACT_ROOT:-}"
  RUN_ID="${LOCAL_RUN_ID:-local-fixture}"
  RUN_TS="${LOCAL_RUN_TS:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}"

  if [ -z "$local_root" ] || [ ! -d "$local_root" ]; then
    fail_blocked "local_fixture" "LOCAL_ARTIFACT_ROOT missing or not a directory"
  fi

  record_event "local_fixture" "started" "$local_root"
  jq -n '{artifacts: []}' > "$ARTIFACTS_PAYLOAD"

  local idx=0
  while IFS= read -r item; do
    idx=$((idx + 1))
    local name safe target updated_at
    name="$(basename "$item")"
    safe="$(safe_name "$name")"
    target="$ARTIFACT_ROOT/${idx}_${safe}"
    updated_at="$RUN_TS"
    mkdir -p "$target"
    if [ -d "$item" ]; then
      (cd "$item" && find . -type f | LC_ALL=C sort | while IFS= read -r rel; do
        mkdir -p "$target/$(dirname "$rel")"
        cp "$rel" "$target/$rel"
      done)
    elif [ "${item##*.}" = "zip" ]; then
      unzip -q "$item" -d "$target"
    else
      cp "$item" "$target/$name"
    fi
    printf '%s\t%s\t%s\n' "$name" "$target" "$updated_at" >> "$WORKDIR/artifact_dirs.tsv"
    jq \
      --arg name "$name" \
      --arg updated_at "$updated_at" \
      '.artifacts += [{name: $name, updated_at: $updated_at, archive_download_url: "local"}]' \
      "$ARTIFACTS_PAYLOAD" > "$WORKDIR/artifacts.next.json"
    mv "$WORKDIR/artifacts.next.json" "$ARTIFACTS_PAYLOAD"
  done < <(find "$local_root" -mindepth 1 -maxdepth 1 | LC_ALL=C sort)

  record_event "local_fixture" "ok" "artifact_count=${idx}"
}

content_manifest_for_dir() {
  local root="$1"
  find "$root" -type f | LC_ALL=C sort | while IFS= read -r file; do
    local rel sha
    rel="${file#"$root"/}"
    sha="$(sha256_file "$file")"
    printf '%s  %s\n' "$sha" "$rel"
  done
}

build_manifest() {
  local entries_json="$WORKDIR/manifest_entries.jsonl"
  : > "$entries_json"

  if [ ! -s "$WORKDIR/artifact_dirs.tsv" ]; then
    record_event "manifest" "pending" "no artifacts"
    jq -n '{artifacts: []}' > "$MANIFEST_JSON"
    return 0
  fi

  while IFS=$'\t' read -r name dir updated_at; do
    local content_sha file_count manifest_path safe
    safe="$(safe_name "$name")"
    manifest_path="$AUDIT_OUT_DIR/${safe}.normalized.sha256"
    content_manifest_for_dir "$dir" > "$manifest_path"
    content_sha="$(sha256_file "$manifest_path")"
    file_count="$(wc -l < "$manifest_path" | tr -d ' ')"
    printf '%s  %s\n' "$content_sha" "$name" >> "$SHA_FILE"
    jq -cn \
      --arg name "$name" \
      --arg updated_at "$updated_at" \
      --arg normalized_sha256 "$content_sha" \
      --arg normalized_manifest "$(basename "$manifest_path")" \
      --argjson file_count "$file_count" \
      '{
        name: $name,
        updated_at: $updated_at,
        normalized_sha256: $normalized_sha256,
        normalized_manifest: $normalized_manifest,
        file_count: $file_count
      }' >> "$entries_json"
  done < "$WORKDIR/artifact_dirs.tsv"

  jq -s '{artifacts: .}' "$entries_json" > "$MANIFEST_JSON"
  record_event "manifest" "ok" "normalized artifact manifest created"
}

rekor_healthcheck() {
  if [ "$REKOR_OFFLINE_MODE" = "1" ]; then
    record_event "rekor" "skipped" "REKOR_OFFLINE_MODE=1"
    return 0
  fi
  if [ "${FORCE_REKOR_UNAVAILABLE:-0}" = "1" ]; then
    return 1
  fi
  if ! command -v rekor-cli >/dev/null 2>&1; then
    [ "$REKOR_REQUIRED" = "1" ] && return 1
    record_event "rekor" "skipped" "rekor-cli missing and REKOR_REQUIRED=0"
    return 0
  fi
  curl -fsSL "${SIGSTORE_REKOR_SERVER}/api/v1/log" >/dev/null
}

collect_rekor_entries() {
  if [ "$REKOR_OFFLINE_MODE" = "1" ] || ! command -v rekor-cli >/dev/null 2>&1; then
    : > "$REKOR_FILE"
    return 0
  fi

  while IFS= read -r sha; do
    [ -n "$sha" ] || continue
    {
      echo "sha256:${sha}"
      rekor-cli search \
        --rekor_server "$SIGSTORE_REKOR_SERVER" \
        --sha "sha256:${sha}" 2>/dev/null || true
      echo
    } >> "$REKOR_FILE"
  done < <(awk '{print $1}' "$SHA_FILE" | LC_ALL=C sort -u)

  record_event "rekor" "ok" "rekor diff input collected"
}

verify_sigstore_for_artifacts() {
  local sigstore_lines="$WORKDIR/sigstore.jsonl"
  : > "$sigstore_lines"

  while IFS=$'\t' read -r name dir _updated_at; do
    local verified=0
    while IFS= read -r sig; do
      local payload cert bundle cmd_status detail
      payload="${sig%.sig}"
      cert=""
      bundle=""
      [ -f "${payload}.crt" ] && cert="${payload}.crt"
      [ -f "${payload}.pem" ] && cert="${payload}.pem"
      [ -f "${payload}.bundle" ] && bundle="${payload}.bundle"
      [ -f "${payload}.bundle.json" ] && bundle="${payload}.bundle.json"

      if [ ! -f "$payload" ]; then
        detail="signature_without_payload"
        cmd_status="blocked"
      elif ! command -v cosign >/dev/null 2>&1; then
        detail="cosign_missing"
        cmd_status="blocked"
      else
        local args
        args=(verify-blob "$payload" --signature "$sig")
        [ -n "$cert" ] && args+=(--certificate "$cert")
        [ -n "$bundle" ] && args+=(--bundle "$bundle")
        [ -n "$COSIGN_CERT_IDENTITY" ] && args+=(--certificate-identity "$COSIGN_CERT_IDENTITY")
        [ -n "$COSIGN_CERT_IDENTITY_REGEXP" ] && args+=(--certificate-identity-regexp "$COSIGN_CERT_IDENTITY_REGEXP")
        [ -n "$COSIGN_CERT_OIDC_ISSUER" ] && args+=(--certificate-oidc-issuer "$COSIGN_CERT_OIDC_ISSUER")
        [ -n "$COSIGN_CERT_OIDC_ISSUER_REGEXP" ] && args+=(--certificate-oidc-issuer-regexp "$COSIGN_CERT_OIDC_ISSUER_REGEXP")
        if cosign "${args[@]}" >/dev/null 2>"$WORKDIR/cosign.err"; then
          detail="verified"
          cmd_status="ok"
          verified=$((verified + 1))
        else
          detail="$(tr '\n' ' ' < "$WORKDIR/cosign.err" | cut -c1-240)"
          cmd_status="blocked"
        fi
      fi

      jq -cn \
        --arg artifact "$name" \
        --arg payload "${payload#"$dir"/}" \
        --arg signature "${sig#"$dir"/}" \
        --arg status "$cmd_status" \
        --arg detail "$detail" \
        '{artifact:$artifact, payload:$payload, signature:$signature, status:$status, detail:$detail}' >> "$sigstore_lines"
    done < <(find "$dir" -type f -name '*.sig' | LC_ALL=C sort)

    if [ "$verified" -eq 0 ]; then
      jq -cn \
        --arg artifact "$name" \
        --arg status "unsigned_unverified" \
        '{artifact:$artifact, payload:null, signature:null, status:$status, detail:"no verified cosign signature found"}' >> "$sigstore_lines"
    fi
  done < "${WORKDIR}/artifact_dirs.tsv"

  jq -s '{checks: .}' "$sigstore_lines" > "$SIGSTORE_JSON"

  if jq -e '.checks[] | select(.status == "blocked")' "$SIGSTORE_JSON" >/dev/null; then
    fail_blocked "sigstore_verify" "cosign verification failed or identity mismatch" "${RUN_ID:-}" "${RUN_TS:-}" "${RUN_AGE_HOURS:-}"
  fi

  if [ "$COSIGN_VERIFY_REQUIRED" = "1" ] && ! jq -e '.checks[] | select(.status == "ok")' "$SIGSTORE_JSON" >/dev/null; then
    fail_blocked "sigstore_verify" "COSIGN_VERIFY_REQUIRED=1 but no verified signature found" "${RUN_ID:-}" "${RUN_TS:-}" "${RUN_AGE_HOURS:-}"
  fi

  record_event "sigstore_verify" "ok" "sigstore support evaluated"
}

detect_material_change() {
  local changed=0
  if [ -f "${STATE_DIR}/last_sha256.txt" ]; then
    if ! diff -q "${STATE_DIR}/last_sha256.txt" "$SHA_FILE" >/dev/null; then
      changed=1
    fi
  else
    changed=1
  fi

  if [ -f "${STATE_DIR}/last_rekor.txt" ]; then
    if ! diff -q "${STATE_DIR}/last_rekor.txt" "$REKOR_FILE" >/dev/null; then
      changed=1
    fi
  else
    changed=1
  fi

  printf '%s' "$changed"
}

emit_pulse() {
  local owner_repo="${GITHUB_REPOSITORY:-local/local}"
  local sha rekor evidence_url sigstore_status
  sha="$(awk 'NR==1 {print $1}' "$SHA_FILE")"
  rekor="$(awk 'NF {print; exit}' "$REKOR_FILE" || true)"
  evidence_url="local:${AUDIT_OUT_DIR}"
  sigstore_status="$(jq -r '[.checks[].status] | unique | join(",")' "$SIGSTORE_JSON")"

  if [ -n "${GITHUB_REPOSITORY:-}" ] && [ -n "${RUN_ID:-}" ]; then
    evidence_url="https://github.com/${GITHUB_REPOSITORY}/actions/runs/${RUN_ID}"
  fi

  cat > "$PULSE_FILE" <<EOF
TaijiOS build changed - minimal evidence summary:
artifact: normalized-latest-artifacts | sha256: ${sha:-none} | rekor: ${rekor:-none} | ci-run: ${owner_repo}#${RUN_ID:-unknown} | verifier: taijios-audit-bot | sigstore: ${sigstore_status:-unverified}
evidence:${evidence_url} | sha256:${sha:-none} | rekor:${rekor:-none} | ci-run:${owner_repo}#${RUN_ID:-unknown} | verifier:taijios-audit-bot | audit:${AUDIT_OUT_DIR}
footer: CI green is not artifact verified; reproducible build, provenance predicate, SLSA compliance, signed-artifact trust, and repo-wide integrity remain unverified unless separately proven.
EOF

  if [ "$AUDIT_EMIT_ENABLED" = "1" ]; then
    ./.audit/emit_pulse.sh "$PULSE_FILE"
  fi
}

persist_state() {
  cp "$MANIFEST_JSON" "${STATE_DIR}/last_manifest.json"
  cp "$SHA_FILE" "${STATE_DIR}/last_sha256.txt"
  cp "$REKOR_FILE" "${STATE_DIR}/last_rekor.txt"
}

require_cmd jq
require_cmd unzip
require_cmd curl
require_cmd python3

RUN_ID=""
RUN_TS=""
RUN_AGE_HOURS=""
record_event "preflight" "ok" "detector started"

if [ -n "${LOCAL_ARTIFACT_ROOT:-}" ]; then
  collect_local_artifacts
else
  collect_github_artifacts
fi

RUN_AGE_HOURS="$(portable_age_hours "$RUN_TS")"
build_manifest

if ! rekor_healthcheck; then
  if [ "$REKOR_REQUIRED" = "1" ]; then
    fail_blocked "rekor" "Rekor unavailable or rekor-cli missing" "$RUN_ID" "$RUN_TS" "$RUN_AGE_HOURS"
  fi
  record_event "rekor" "degraded" "Rekor unavailable but REKOR_REQUIRED=0"
fi
collect_rekor_entries
verify_sigstore_for_artifacts

MATERIAL_CHANGED="$(detect_material_change)"
record_event "material_gate" "ok" "material_changed=${MATERIAL_CHANGED}; run_age_hours=${RUN_AGE_HOURS}"
echo "[audit] material_changed=${MATERIAL_CHANGED}"
echo "[audit] run_age_hours=${RUN_AGE_HOURS}"

PULSE_EMITTED=0
if [ "$MATERIAL_CHANGED" -eq 1 ] && [ "$RUN_AGE_HOURS" -le "$MATERIAL_GATE_HOURS" ]; then
  emit_pulse
  persist_state
  if [ "$AUDIT_EMIT_ENABLED" = "1" ]; then
    PULSE_EMITTED=1
  fi
  record_event "pulse" "ok" "pulse file generated; emit_enabled=${AUDIT_EMIT_ENABLED}; state updated"
else
  echo "[audit] no material change within ${MATERIAL_GATE_HOURS}h"
  record_event "pulse" "skipped" "no material change within gate or run too old"
fi

write_summary "PARTIAL" "" "" "$MATERIAL_CHANGED" "$PULSE_EMITTED" "$RUN_ID" "$RUN_TS" "$RUN_AGE_HOURS"
