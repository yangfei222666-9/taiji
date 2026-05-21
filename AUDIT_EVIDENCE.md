# TaijiOS Audit Evidence

Status: release evidence template, not live release evidence.

This file documents the evidence produced by `.github/workflows/release.yml`.
It is valid for an audit only after a real GitHub Actions release run has
completed and the uploaded artifact bundle has been downloaded and verified.

## Version Anchor

| Item | Value |
|---|---|
| Repository | `https://github.com/yangfei222666-9/taiji` |
| Commit SHA | `<commit-sha>` |
| Release Tag | `<tag>` |
| Image Reference | `ghcr.io/yangfei222666-9/taiji:<short-sha>` |
| Image Digest | `ghcr.io/yangfei222666-9/taiji:<short-sha>@sha256:<digest>` |
| Evidence Artifact | `taiji-evidence-<commit-sha>` |

## Boundary

- `release_workflow_defined != release_passed`
- `artifact_uploaded != artifact_verified`
- `cosign_attestation_created != customer_audit_pass`
- `workflow_dispatch != production_cutover`
- No secret values belong in this document or in release artifacts.

## Supply Chain Integrity

### Cosign Signature Verification

```bash
cosign verify \
  --certificate-identity "https://github.com/yangfei222666-9/taiji/.github/workflows/release.yml@refs/tags/<tag>" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/yangfei222666-9/taiji:<short-sha>
```

Expected result after a real signed release:

```text
Verified OK
```

### Provenance Attestation Verification

```bash
cosign verify-attestation \
  --certificate-identity "https://github.com/yangfei222666-9/taiji/.github/workflows/release.yml@refs/tags/<tag>" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --type slsaprovenance \
  ghcr.io/yangfei222666-9/taiji:<short-sha>
```

The release workflow generates `supplychain/provenance.json` at runtime. A
static repository copy of that file is not release evidence.

## Build Reproducibility

Build package:

```bash
python -m build
```

Expected artifacts:

- `dist/*.whl`
- `dist/*.tar.gz`

## Testing Evidence

Run tests:

```bash
pytest tests -q \
  --maxfail=1 \
  --disable-warnings \
  --cov=aios \
  --cov-report=xml:coverage.xml \
  --cov-report=term-missing \
  --cov-fail-under=70
```

Expected artifacts:

- `coverage.xml`
- `build-log.txt`

Coverage target:

- Minimum line coverage: `>= 70%`

## SBOM

Generate CycloneDX SBOM:

```bash
cyclonedx-py environment -o cyclonedx.sbom.xml
```

Generate Syft SBOM:

```bash
syft . -o json > sbom.json
```

Expected artifacts:

- `cyclonedx.sbom.xml`
- `sbom.json`

## Integrity Verification

Generate checksums:

```bash
sha256sum dist/* > checksums.txt
```

Verify checksums:

```bash
sha256sum -c checksums.txt
```

Expected result:

```text
OK
```

## Immutable Image Lock

The release workflow writes immutable references to:

- `image.lock`

Format:

```text
ghcr.io/yangfei222666-9/taiji:<short-sha>@sha256:<digest>
ghcr.io/yangfei222666-9/taiji:<tag>@sha256:<digest>
```

The tag line exists only when the workflow is triggered by a tag.

## Evidence Artifact Index

| Artifact | Purpose |
|---|---|
| `coverage.xml` | Test coverage |
| `cyclonedx.sbom.xml` | CycloneDX SBOM |
| `sbom.json` | Syft SBOM |
| `checksums.txt` | SHA256 integrity |
| `manifest.yaml` | Commit, image, and package artifact manifest |
| `image.lock` | Immutable digest pin |
| `supplychain/provenance.json` | Runtime SLSA provenance predicate |
| `build-log.txt` | Reproducible test log |
| `dist/*` | Built Python package artifacts |

## Responsible Maintainers

| Area | Owner |
|---|---|
| Release Pipeline | `@yangfei222666` |
| Supply Chain Security | `@yangfei222666` |
| SBOM / Compliance | `@yangfei222666` |

## Audit Stop Rule

If any artifact above is missing, stale, unparsable, or not tied to the same
commit/image digest, the result is `blocked_release_evidence_incomplete`, not
an audit pass.
