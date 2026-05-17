# AUDIT_CHECKLIST.md - TaijiOS / GitHub Actions Audit Readiness Checklist

> Repo: `yangfei222666-9/taiji`
> Scope: CI / Build / Deploy / Runtime / Security / Traceability
> Updated: 2026-05-17
> Status: readiness checklist, not an audit pass

## Boundary

This checklist defines the evidence that a GitHub Actions audit should collect.
It does not claim that the current repository, release, image, deployment, or
runtime already passed these gates.

Rules:

- Do not store or print `GITHUB_TOKEN`, signing keys, or provider secrets.
- Treat `GITHUB_TOKEN` as an ephemeral operator-provided credential.
- Keep GitHub run verification separate from local artifact existence.
- Keep CI success separate from release, deploy, runtime, rollback, and production readiness.
- `checklist_ready != audit_pass`
- `artifact_downloaded != artifact_verified`
- `verified_handoff != GitHub merge`
- `release_exists != deployment_healthy`

## 0. Environment Variables

```bash
export OWNER="yangfei222666-9"
export REPO="taiji"
export RUN_ID="<github_actions_run_id>"
export ARTIFACT_ID="<artifact_id>"
export COMMIT="$(git rev-parse HEAD)"
export TS="$(date +%Y%m%d-%H%M%S)"
export IMAGE="ghcr.io/${OWNER}/${REPO}"
```

## 1. CI Gate

Canonical artifact:

```text
actions/artifacts/${ARTIFACT_ID}.zip
```

Expected contents:

```text
test-results/junit.xml
coverage/coverage.xml
```

Verify:

```bash
curl -H "Authorization: token ${GITHUB_TOKEN}" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/runs/${RUN_ID}"
curl -L -H "Authorization: token ${GITHUB_TOKEN}" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/artifacts/${ARTIFACT_ID}/zip" \
  -o ci-artifact.zip
unzip -l ci-artifact.zip
```

## 2. Unit Test Gate

```bash
unzip -p ci-artifact.zip test-results/junit.xml | head
unzip -p ci-artifact.zip coverage/coverage.xml | head
```

## 3. Lint / Static Analysis Gate

Expected artifacts:

```text
lint/eslint.json
ruff-report.json
```

Verify:

```bash
unzip -l ci-artifact.zip | egrep 'eslint|ruff'
```

## 4. Build Gate

Canonical artifact:

```text
dist/taiji-${COMMIT}.tar.gz
```

Verify:

```bash
tar -tzf "dist/taiji-${COMMIT}.tar.gz"
```

## 5. SBOM Gate

Canonical artifact:

```text
artifacts/sbom/${COMMIT}.spdx.json
```

Verify:

```bash
jq '.packages | length' "artifacts/sbom/${COMMIT}.spdx.json"
```

## 6. Supply Chain Attestation Gate

Expected artifact:

```text
artifacts/attestations/taiji-attestation.intoto.json
```

Verify:

```bash
cosign verify-attestation --key cosign.pub "${IMAGE}:${COMMIT}"
```

## 7. Container Signature Gate

```bash
cosign verify --key cosign.pub "${IMAGE}:${COMMIT}"
```

## 8. Change Audit Gate

Canonical artifact:

```text
logs/change/${COMMIT}.jsonl
```

Verify:

```bash
jq -r 'select(.commit=="'"${COMMIT}"'").files[]' "logs/change/${COMMIT}.jsonl"
```

## 9. Request Audit Gate

Canonical artifact:

```text
logs/audit/$(date +%F).jsonl
```

Verify:

```bash
jq 'select(.request_id=="<REQUEST_ID>")' "logs/audit/$(date +%F).jsonl"
```

## 10. Config Snapshot Gate

Expected artifact:

```text
config/snapshots/config-${TS}.json
```

Verify:

```bash
jq '. | keys' "config/snapshots/config-${TS}.json"
```

## 11. Deployment Diff Gate

Expected artifact:

```text
ci/artifacts/deploy-${RUN_ID}/diff.patch
```

Verify:

```bash
git --no-pager show "${COMMIT}" --name-only
```

## 12. Kubernetes Snapshot Gate

Expected artifact:

```text
k8s/manifests/snapshot-${TS}.tar.gz
```

Verify:

```bash
tar -tzf "k8s/manifests/snapshot-${TS}.tar.gz"
```

## 13. Runtime Metrics Gate

Expected artifact:

```text
metrics/taiji/${TS}.json
```

Verify:

```bash
jq '.latency_p95, .error_rate' "metrics/taiji/${TS}.json"
```

## 14. Rollback Gate

Expected artifact:

```text
rollbacks/${TS}/${COMMIT}.json
```

Verify:

```bash
jq -r '.reason+" @"+.commit' "rollbacks/${TS}/${COMMIT}.json"
```

## 15. Database Migration Gate

Expected artifacts:

```text
db/migrations/*.sql
db/migration-logs/*.jsonl
```

Verify:

```bash
head -n 20 db/migrations/*.sql
jq '.[-1]' db/migration-logs/*.jsonl
```

## 16. Model / Rule Version Gate

Expected artifact:

```text
models/*/manifest.json
```

Verify:

```bash
jq -r '.model_id, .checksum' models/*/manifest.json
```

## 17. ACL / IAM Change Gate

Expected artifact:

```text
security/acl/changes-${TS}.jsonl
```

Verify:

```bash
jq -c 'select(.actor=="<USER>").diff' "security/acl/changes-${TS}.jsonl"
```

## 18. GitHub Release Gate

```bash
gh release view --repo "${OWNER}/${REPO}"
```

## 19. Provenance Gate

```bash
oras discover "${IMAGE}:${COMMIT}"
```

## 20. Full Audit Sweep

```bash
make audit
```

## Recommended Repository Structure

```text
.
├── artifacts
│   ├── attestations
│   └── sbom
├── build
├── ci
├── config
├── coverage
├── db
├── dist
├── k8s
├── lint
├── logs
├── metrics
├── models
├── rollbacks
├── security
└── test-results
```

## Recommended CI Target

```makefile
audit:
	@echo "== CI =="
	@test -f coverage/coverage.xml
	@echo "== SBOM =="
	@test -f artifacts/sbom/${COMMIT}.spdx.json
	@echo "== Signature =="
	@cosign verify --key cosign.pub ${IMAGE}:${COMMIT}
	@echo "== Done =="
```

## Minimum Audit Retention Policy

| Artifact | Retention |
| --- | --- |
| CI artifacts | 90d |
| Audit logs | 365d |
| SBOM | Permanent |
| Attestations | Permanent |
| Release packages | Permanent |
| Metrics | 30d |
| Rollback records | 365d |

## Compliance Mapping

| Control | Evidence |
| --- | --- |
| Traceability | `logs/change/*.jsonl` |
| Reproducibility | `dist/*.tar.gz` |
| Supply Chain Integrity | `cosign + SBOM` |
| Runtime Accountability | `logs/audit/*.jsonl` |
| Rollback Capability | `rollbacks/*` |
| Config Drift | `config snapshots` |
| Deployment Integrity | `deploy diff` |

## Current Verification Status

```text
checklist_written=true
local_verifier=tools/verify_github_actions_audit_checklist.py
github_api_called=false
artifact_downloaded=false
cosign_verified=false
oras_verified=false
release_verified=false
deployment_verified=false
runtime_metrics_verified=false
git_available=true
staged_count=0
dirty_count=4
audit_pass=false
```
