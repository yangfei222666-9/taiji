#!/usr/bin/env python3
"""Build a local-only proof bundle from an existing TaijiOS run artifact."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path
from typing import Any


SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_]*(API_KEY|TOKEN)\s*=\s*[^#\s][^\s]{12,}", re.IGNORECASE),
)


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


def parse_jsonl(path: Path) -> int:
    count = 0
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        json.loads(line)
        count += 1
    return count


def collect_files(run_dir: Path) -> list[Path]:
    return sorted(path for path in run_dir.rglob("*") if path.is_file())


def scan_secret_like(files: list[Path], root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(
                    {
                        "path": str(path.relative_to(root)),
                        "type": "secret_like_pattern",
                    }
                )
                break
    return findings


def write_checksums(bundle_dir: Path) -> Path:
    checksum_path = bundle_dir / "checksums" / "SHA256SUMS"
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(p for p in bundle_dir.rglob("*") if p.is_file()):
        if path == checksum_path:
            continue
        rows.append(f"{sha256_file(path)}  {path.relative_to(bundle_dir).as_posix()}")
    checksum_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return checksum_path


def build(args: argparse.Namespace) -> dict[str, Any]:
    base_dir = Path(args.base_dir).resolve()
    run_dir = (base_dir / args.run_dir).resolve()
    out_dir = (base_dir / args.out_dir).resolve()
    run_id = args.run_id or run_dir.name
    bundle_dir = out_dir / f"proof-bundle-{run_id}"

    summary: dict[str, Any] = {
        "schema_version": "taijios.local_proof_bundle.v1",
        "generated_at": utc_now(),
        "verdict": "blocked",
        "failure_cause": [],
        "base_dir": str(base_dir),
        "run_dir": str(run_dir),
        "run_id": run_id,
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

    if not run_dir.exists():
        summary["failure_cause"].append("run_dir_missing")
        return summary
    if not is_relative_to(run_dir, base_dir):
        summary["failure_cause"].append("run_dir_outside_base_dir")
        return summary
    if out_dir.exists() and any(out_dir.iterdir()):
        summary["failure_cause"].append("out_dir_already_exists_non_empty")
        summary["out_dir"] = str(out_dir)
        return summary
    if bundle_dir.exists():
        summary["failure_cause"].append("bundle_dir_already_exists")
        summary["bundle_dir"] = str(bundle_dir)
        return summary

    source_summary_path = run_dir / "summary.json"
    source_events_path = run_dir / "event_flow.jsonl"
    if not source_summary_path.exists() or not source_events_path.exists():
        summary["failure_cause"].append("required_source_files_missing")
        return summary

    source_summary = json.loads(source_summary_path.read_text(encoding="utf-8"))
    event_flow_lines = parse_jsonl(source_events_path)
    files = collect_files(run_dir)
    findings = scan_secret_like(files, base_dir)
    if findings:
        summary["failure_cause"].append("secret_like_findings_present")
        summary["secret_like_findings"] = findings
        return summary

    bundle_dir.mkdir(parents=True, exist_ok=False)
    copied: list[dict[str, Any]] = []
    evidence_root = bundle_dir / "evidence" / run_dir.name
    for src in files:
        dst = evidence_root / src.relative_to(run_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(
            {
                "source": str(src),
                "bundle_path": str(dst.relative_to(bundle_dir)),
                "sha256": sha256_file(dst),
            }
        )

    manifest = {
        "schema_version": "taijios.local_proof_bundle.manifest.v1",
        "generated_at": utc_now(),
        "source_run_dir": str(run_dir),
        "source_summary_verdict": source_summary.get("verdict"),
        "event_flow_lines": event_flow_lines,
        "copied_files": copied,
    }
    write_json(bundle_dir / "manifest.json", manifest)
    (bundle_dir / "README.md").write_text(
        "\n".join(
            [
                "# TaijiOS Local Proof Bundle",
                "",
                f"- run_id: `{run_id}`",
                f"- source_summary_verdict: `{source_summary.get('verdict')}`",
                f"- event_flow_lines: `{event_flow_lines}`",
                "",
                "## Verify",
                "",
                "```bash",
                "shasum -a 256 -c checksums/SHA256SUMS",
                "```",
                "",
                "Boundary: local-only; no network, provider, secret env, GitHub, kubectl, or cosign calls.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    checksum_path = write_checksums(bundle_dir)
    archive_path = out_dir / f"proof-bundle-{run_id}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname=bundle_dir.name)
    archive_sha256 = sha256_file(archive_path)
    archive_sha_path = archive_path.with_name(f"{archive_path.name}.sha256")
    archive_sha_path.write_text(f"{archive_sha256}  {archive_path.name}\n", encoding="utf-8")

    summary.update(
        {
            "verdict": "ok_local_proof_bundle_created",
            "failure_cause": [],
            "source_summary_verdict": source_summary.get("verdict"),
            "event_flow_lines": event_flow_lines,
            "source_file_count": len(files),
            "copied_file_count": len(copied),
            "secret_like_findings_count": 0,
            "bundle_dir": str(bundle_dir),
            "archive_path": str(archive_path),
            "archive_sha256": archive_sha256,
            "archive_sha256_path": str(archive_sha_path),
            "checksums_path": str(checksum_path),
        }
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local-only TaijiOS proof bundle.")
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out-dir", default="runs/ops_check/local_proof_bundle")
    parser.add_argument("--run-id", default=None)
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
    summary = build(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "summary.json", summary)
    events = [
        {"ts": utc_now(), "event": "local_proof_bundle_done", "verdict": summary["verdict"]},
    ]
    (out_dir / "event_flow.jsonl").write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )
    print(json.dumps({"verdict": summary["verdict"], "summary_path": str(out_dir / "summary.json")}, ensure_ascii=False, indent=2))
    return 0 if summary["verdict"].startswith("ok_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
