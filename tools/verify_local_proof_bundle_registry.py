#!/usr/bin/env python3
"""Verify a local TaijiOS proof-bundle registry."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import tarfile
import tempfile
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def sidecar_sha(path: Path) -> str | None:
    if not path.exists():
        return None
    line = path.read_text(encoding="utf-8").splitlines()[0].strip()
    return line.split()[0] if line else None


def verify_internal_checksums(bundle_root: Path) -> list[dict[str, Any]]:
    checksum_path = bundle_root / "checksums" / "SHA256SUMS"
    if not checksum_path.exists():
        return [{"failure": "checksums_file_missing"}]
    failures: list[dict[str, Any]] = []
    for line_no, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            expected, rel = line.split(None, 1)
        except ValueError:
            failures.append({"line": line_no, "failure": "checksum_line_parse_failed"})
            continue
        target = bundle_root / rel.strip()
        if not target.exists():
            failures.append({"line": line_no, "failure": "checksummed_file_missing", "path": rel.strip()})
            continue
        actual = sha256_file(target)
        if actual != expected:
            failures.append({"line": line_no, "failure": "checksum_mismatch", "path": rel.strip()})
    return failures


def verify_archive(base_dir: Path, item: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "archive_path": item.get("archive_path"),
        "expected_sha256": item.get("archive_sha256"),
        "ok": False,
        "failures": [],
    }
    archive_rel = item.get("archive_path")
    if not archive_rel:
        result["failures"].append("archive_path_missing")
        return result
    archive = (base_dir / archive_rel).resolve()
    if not is_relative_to(archive, base_dir):
        result["failures"].append("archive_outside_base_dir")
        return result
    if not archive.exists():
        result["failures"].append("archive_missing")
        return result

    actual_sha = sha256_file(archive)
    result["actual_sha256"] = actual_sha
    if item.get("archive_sha256") != actual_sha:
        result["failures"].append("archive_sha256_mismatch")

    sidecar = archive.with_name(f"{archive.name}.sha256")
    sidecar_value = sidecar_sha(sidecar)
    result["sha256_sidecar_present"] = sidecar.exists()
    if sidecar_value != actual_sha:
        result["failures"].append("sha256_sidecar_mismatch")

    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            unsafe = [member.name for member in members if member.name.startswith("/") or ".." in Path(member.name).parts]
            if unsafe:
                result["failures"].append("unsafe_tar_member_path")
            with tempfile.TemporaryDirectory(prefix="taiji-proof-verify-") as tmp:
                tmp_path = Path(tmp)
                tar.extractall(tmp_path)
                roots = [path for path in tmp_path.iterdir() if path.is_dir()]
                if len(roots) != 1:
                    result["failures"].append("unexpected_extracted_root_count")
                else:
                    bundle_root = roots[0]
                    manifest_path = bundle_root / "manifest.json"
                    if not manifest_path.exists():
                        result["failures"].append("manifest_missing")
                    else:
                        json.loads(manifest_path.read_text(encoding="utf-8"))
                    checksum_failures = verify_internal_checksums(bundle_root)
                    if checksum_failures:
                        result["failures"].append("internal_checksum_failures_present")
                        result["internal_checksum_failures"] = checksum_failures[:20]
    except Exception as exc:  # noqa: BLE001
        result["failures"].append("tar_verify_failed")
        result["tar_error"] = type(exc).__name__

    result["ok"] = not result["failures"]
    return result


def verify(args: argparse.Namespace) -> dict[str, Any]:
    base_dir = Path(args.base_dir).resolve()
    registry_path = (base_dir / args.registry).resolve()
    summary: dict[str, Any] = {
        "schema_version": "taijios.local_proof_bundle_registry_verifier.v1",
        "generated_at": utc_now(),
        "verdict": "blocked",
        "failure_cause": [],
        "base_dir": str(base_dir),
        "registry_path": str(registry_path),
        "network_call_performed": False,
        "provider_call_performed": False,
        "secret_env_read": False,
        "secret_value_emitted": False,
        "git_operation": False,
        "judgment": False,
        "paper_buy": False,
        "trade": False,
        "promote": False,
    }
    if not registry_path.exists():
        summary["failure_cause"].append("registry_missing")
        return summary
    if not is_relative_to(registry_path, base_dir):
        summary["failure_cause"].append("registry_outside_base_dir")
        return summary

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    items = registry.get("items")
    if not isinstance(items, list):
        summary["failure_cause"].append("registry_items_not_list")
        return summary

    archive_results = [verify_archive(base_dir, item) for item in items]
    failed = [item for item in archive_results if not item["ok"]]
    summary.update(
        {
            "registry_item_count": len(items),
            "verified_archive_count": len(archive_results),
            "failed_archive_count": len(failed),
            "archive_results": archive_results,
        }
    )
    if failed:
        summary["failure_cause"].append("archive_verification_failures_present")
        summary["verdict"] = "blocked_local_proof_bundle_registry_verification_failed"
    else:
        summary["verdict"] = "ok_local_proof_bundle_registry_verified"
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a local TaijiOS proof-bundle registry.")
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--out-dir", default="runs/ops_check/local_proof_bundle_registry_verification")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = (Path(args.base_dir).resolve() / args.out_dir).resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        print(
            json.dumps(
                {
                    "verdict": "blocked_out_dir_already_exists",
                    "out_dir": str(out_dir),
                    "failure_cause": ["out_dir_already_exists_non_empty"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    summary = verify(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "summary.json", summary)
    events = [{"ts": utc_now(), "event": "local_proof_bundle_registry_verification_done", "verdict": summary["verdict"]}]
    (out_dir / "event_flow.jsonl").write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )
    print(json.dumps({"verdict": summary["verdict"], "summary_path": str(out_dir / "summary.json")}, ensure_ascii=False, indent=2))
    return 0 if summary["verdict"].startswith("ok_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
