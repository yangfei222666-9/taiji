# Win11 T7 Project Inventory v0.1

## Verdict

```text
verdict=partial_win11_t7_inventory_scope_dirty
scope=win11_t7_project_inventory_with_migration_classes_v0_1
mode=read_only_inventory_then_docs_only
repo_root=/Users/weiwei/Desktop/taiji
external_disk=/Volumes/T7
```

This inventory is a read-only classification pass. It does not copy, move, delete, rename, archive, import, stage, commit, push, call providers, connect brokers, trade, promote, or read secrets.

The T7 disk is a candidate artifact pool, not source of truth. The canonical TaijiOS repo remains `/Users/weiwei/Desktop/taiji`.

## Boundary

```text
import_allowed=false by default
old_dirty_tree_is_not_baseline
Win11/T7 artifacts_require_receiver_side_verification
provider/API candidates_default_to_sandbox
learning_only != judgment
observe_only != trade
scope pass != repo pass
blocked != failed
```

Skipped or quarantined by policy:

```text
/Volumes/T7/secure
.env*
keychain material
unknown executable/binary blobs
old build output
dependency caches
temporary files
broker/trade/order material
.Trashes / $RECYCLE.BIN / System Volume Information
```

## Scan Summary

Observed read-only:

```text
disk=/Volumes/T7
filesystem=Windows_NTFS
size=2.0 TB
primary_win11_workspace=/Volumes/T7/taijios_full_workspace
historical_backup_roots=/Volumes/T7/TaijiOS_Backup, /Volumes/T7/AIOS_Backups
release_roots=/Volumes/T7/TaijiOS-release, /Volumes/T7/TaijiOS_coldstart
handoff_roots=/Volumes/T7/TAIJI_MAC_REVIEW_FINAL_DROP_20260512_185347, /Volumes/T7/TaijiOS_offline_handoff
rust_markers=Cargo.toml not_observed
go_markers=go.mod not_observed
```

Current canonical repo caveat:

```text
branch=main...origin/main synced
HEAD=origin/main=remote_main=b7b947a7f89b2fd728dcc7bc88eba299f5af43d4
staged_count=0
packet_scope_untracked=2
changed_files_outside_scope=0
repo_pass_claimed=false
```

Current packet dirty files:

```text
docs/WIN11_T7_PROJECT_INVENTORY_v0.1.md
docs/TAIJIOS_REARCHITECTURE_PLAN_v0.1.md
```

## Migration Classes

| Class | Name | Meaning | Default action |
| --- | --- | --- | --- |
| A | Core Merge Candidate | Clear source and verification path; may become canonical core code after review | `canonical_review` |
| B | Lab Candidate | Valuable experiment; not stable enough for core | `lab_review` |
| C | Product Spine Candidate | Boot Preflight / EventFlow / Scope Isolation / Artifact Memory / Closeout | `product_spine_extract` |
| D | UI / XuanShu Candidate | TaijiPet / XuanShu / HUD / demo / Evidence Studio | `ui_review` |
| E | TaijiMind / Provider Candidate | LLM Gateway / RAG / local model / API router | `provider_sandbox_review` |
| F | Archive Only | Historical value; should not enter mainline | `archive_index` |
| G | Quarantine / Do Not Migrate | Secret risk, old build, temp, binary, unknown, broker/trade/order | `quarantine` |

## Inventory Records

Each record preserves the requested schema fields. `import_allowed=false` means the path is not authorized for migration; it can only become eligible after a separate packet, verifier, and user-approved import scope.

| Path | Type | Stack | Evidence files | Class | Value | Risk flags | Action | Import | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/Volumes/T7/taijios_full_workspace/aios/core` | python | Python | `pyproject.toml`, `aios/core/*` observed under workspace | A | high | old_dirty_tree, unverified_diff | canonical_review | false | Core EventBus/Scheduler/Reactor style code may inform canonical core, but must be diff-reviewed before merge. |
| `/Volumes/T7/taijios_full_workspace/aios/agent_system` | python | Python | `pyproject.toml`, agent/task directories observed | A | high | old_dirty_tree, runtime_side_effects_possible | canonical_review | false | Agent queue/lifecycle/execution ideas are core-relevant but cannot bypass canonical tests. |
| `/Volumes/T7/taijios_full_workspace/runs/ops_check` | artifact | JSON, JSONL, Markdown | `summary.json`, `event_flow.jsonl`, `closeout.md` observed | C | high | artifact_currentness_unverified | product_spine_extract | false | Directly maps to Artifact Memory and Closeout conventions. |
| `/Volumes/T7/taijios_full_workspace/runs/event_flow` | artifact | JSON, JSONL | `promote_events.jsonl`, `dryrun_2026_04_24_summary.json` observed | C | high | promotion_boundary, dry_run_only | product_spine_extract | false | EventFlow and dry-run promotion evidence are useful, but promotion remains blocked. |
| `/Volumes/T7/TAIJI_MAC_REVIEW_FINAL_DROP_20260512_185347` | artifact | Shell, JSON, Markdown | `README_FIRST_MAC_REVIEW.md`, `RUN_THIS_ON_MAC.sh`, verification artifacts observed | C | high | handoff_not_merge, receiver_result_required | product_spine_extract | false | Strong cross-machine handoff boundary model; explicitly separates handoff pass from GitHub merge. |
| `/Volumes/T7/TaijiOS_Exchange` | artifact | JSON | `manifest.json` observed | C | high | proposal_not_admission | product_spine_extract | false | `proposal != admission` and artifact schema ideas map to Scope Isolation and Artifact Memory. |
| `/Volumes/T7/taijios_full_workspace/docs` | docs | Markdown, JSONL | architecture, gate, gateway, service docs observed | C | medium | stale_docs_possible | product_spine_extract | false | Contains many prior policy and gateway docs; extract only source-backed rules. |
| `/Volumes/T7/TaijiOS_Evidence_Studio` | docs | Markdown, JSON | `README.md`, manifest templates, publish queue observed | D | high | publish_not_authorized | ui_review | false | Evidence-to-video/demo workflow is valuable for XuanShu/HUD/product demo, not runtime truth. |
| `/Volumes/T7/taijios_full_workspace/frontend` | node | React, Vite, TypeScript | `package.json` observed | D | medium | old_ui_candidate | ui_review | false | React/Vite frontend candidate for HUD/demo surface; needs design and dependency review. |
| `/Volumes/T7/taijios-landing` | docs | Jekyll, Markdown, assets | Jekyll site files observed | D | medium | publish_boundary | ui_review | false | Landing/pricing content can inform public entrypoints; does not prove deploy readiness. |
| `/Volumes/T7/taijios_full_workspace/aios/gateway` | python | Python, FastAPI-style gateway | gateway directory observed under `aios` | E | high | provider_sandbox_required, secret_boundary | provider_sandbox_review | false | LLM Gateway/API router candidate; no provider readiness is claimed. |
| `/Volumes/T7/taijios_full_workspace/aios/learning` | python | Python | learning directory observed under `aios` | E | medium | model_output_not_truth | provider_sandbox_review | false | RAG/learning/local-model ideas can feed TaijiMind only as sandbox/candidate evidence. |
| `/Volumes/T7/taijios_full_workspace/taijios-soul` | python | Python | `pyproject.toml`, `README.md` observed | B | medium | product_claims_unverified | lab_review | false | Persona/memory layer may be lab value; not canonical core without verification. |
| `/Volumes/T7/taijios_full_workspace/self-improving-loop` | python | Python | `pyproject.toml`, docs/tests/src observed | B | high | promote_boundary, self_evolution_overclaim | lab_review | false | Useful self-improvement skeleton; must stay candidate until real promote/demote/archive execution is verified. |
| `/Volumes/T7/taijios_full_workspace/aios/quant` | python | Python | quant directory observed under `aios` | B | medium | learning_only, provider_boundary, trade_boundary | lab_review | false | Quant can only be learning_only/observe_only unless future gates explicitly prove otherwise. |
| `/Volumes/T7/taijios_full_workspace/signal_arena` | docs | unknown | directory observed | G | blocked | trade_order_risk, external_platform | quarantine | false | Signal/trade-adjacent content stays quarantined unless a separate observe-only audit proves safe scope. |
| `/Volumes/T7/personal_quant` | docs | Markdown | `constraints.md` observed at top-level scan | G | blocked | personal_finance, trade_boundary | quarantine | false | Personal quant/trading material is not migration input. |
| `/Volumes/T7/TaijiOS-release` | git_repo | Python, docs | `.git`, `pyproject.toml`, `README.md` observed | F | medium | old_release, not_canonical_baseline | archive_index | false | Release snapshot has historical value but must not overwrite canonical mainline. |
| `/Volumes/T7/TaijiOS_Backup` | backup | Python, Node, docs, artifacts | `.git`, many `pyproject.toml`, `package.json`, summaries observed | F | medium | duplicate_history, stale_backup | archive_index | false | Backup layer only; extract patterns from specific packets, not wholesale code. |
| `/Volumes/T7/AIOS_Backups` | backup | Python, docs | dated backup roots and git repos observed | F | low | dated_backup, duplicate_history | archive_index | false | Historical snapshots only. |
| `/Volumes/T7/tmp` | unknown | mixed | many temporary experiment dirs observed | F | low | tmp_sprawl, unknown_currentness | archive_index | false | Default archive-only unless a subfolder has manifest plus evidence. |
| `/Volumes/T7/secure` | unknown | unknown | path observed but not opened | G | blocked | secure_path, secret_boundary | quarantine | false | Explicitly excluded from read/open/import. |
| `.env*` anywhere on T7 | unknown | unknown | not read by policy | G | blocked | secret_boundary | quarantine | false | Secret-bearing files are never migrated or summarized. |
| Unknown `.exe`, `.zip`, `.db`, lock files, build outputs | binary | unknown | names observed in top-level scans, contents not opened | G | blocked | unknown_binary, build_artifact, possible_secret | quarantine | false | Not source-of-truth and not importable without a separate artifact policy. |

## Classification Notes

1. A-class entries are only candidates for canonical review. They are not authorized imports.
2. C-class entries have the strongest immediate productization value because they reinforce Evidence Kernel and Product Spine.
3. D-class entries are product/demo/UI candidates and must not claim runtime capability.
4. E-class entries require sandbox/provider boundaries. Existing gateway code does not prove live provider readiness.
5. F-class entries are historical indexes only.
6. G-class entries must not migrate unless a future explicit safety review reclassifies a narrow item.

## Not Claimed

```text
repo pass
clean migration
new Mac bootstrap complete
Win11 handoff accepted
provider ready
broker ready
trade ready
paper-buy ready
judgment ready
promotion ready
public deploy ready
```
