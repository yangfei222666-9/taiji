#!/usr/bin/env python3
"""Build a local-only GLM-5.2 candidate-review request envelope from stdin.

This script intentionally does not call a provider. It reads sanitized text from
stdin and emits a JSON candidate-review envelope that can be used in a later,
separately authorized provider-call gate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from typing import Any


DEFAULT_MODEL = "glm-5.2"
DEFAULT_MAX_INPUT_CHARS = 120_000
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD)\s*=\s*[^#\s][^\s]{8,}", re.I),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read sanitized text from stdin and emit a local-only "
            "candidate_review JSON envelope."
        ),
        epilog=(
            "Examples:\n"
            "  printf 'diff summary...' | python3 tools/glm52_candidate_review.py\n"
            "  git diff --stat | python3 tools/glm52_candidate_review.py --task pr_review\n\n"
            "Boundary:\n"
            "  Reads stdin only.\n"
            "  Does not read repository files.\n"
            "  Does not write files.\n"
            "  Does not read API keys.\n"
            "  Does not call provider APIs.\n"
            "  Output remains candidate evidence, not canonical truth."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--task", default="candidate_review", help="Review task label.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Target provider model label.")
    parser.add_argument(
        "--max-input-chars",
        type=int,
        default=DEFAULT_MAX_INPUT_CHARS,
        help="Reject stdin longer than this many characters.",
    )
    return parser


def detect_secret_like(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(pattern.pattern)
    return findings


def make_review_prompt(task: str, text: str) -> str:
    return (
        "You are a readonly candidate reviewer for an AI agent reliability gate.\n"
        "Review only the sanitized input below. Do not infer unstated facts.\n"
        "Return JSON with: verdict, risks, missing_evidence, overclaim_risks, "
        "recommended_next_gate, cannot_claim.\n\n"
        f"task={task}\n"
        "sanitized_input_begin\n"
        f"{text}\n"
        "sanitized_input_end\n"
    )


def base_envelope(args: argparse.Namespace, text: str) -> dict[str, Any]:
    return {
        "schema": "glm52_candidate_review_envelope_v1",
        "created_at": utc_now(),
        "provider_called": False,
        "api_key_read": False,
        "repo_files_read": False,
        "files_written": False,
        "input_source": "stdin",
        "model": args.model,
        "task": args.task,
        "input_chars": len(text),
        "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "candidate_review": {
            "status": "DRY_RUN_ONLY",
            "verdict": "UNVERIFIED",
            "risks": [],
            "missing_evidence": [],
            "overclaim_risks": [
                "provider output is candidate evidence only",
                "local review does not prove remote CI or runtime readiness",
            ],
            "recommended_next_gate": "explicit_provider_call_with_sanitized_stdin_only",
            "cannot_claim": [
                "provider_ready",
                "runtime_ready",
                "truth_promotion",
                "long_task_ready",
                "repo_pass",
            ],
        },
    }


def main() -> int:
    args = build_parser().parse_args()
    text = sys.stdin.read()
    envelope = base_envelope(args, text)

    if not text.strip():
        envelope["candidate_review"]["status"] = "BLOCKED"
        envelope["candidate_review"]["verdict"] = "BLOCKED_EMPTY_STDIN"
        envelope["candidate_review"]["risks"].append("stdin was empty")
        envelope["candidate_review"]["recommended_next_gate"] = "provide_sanitized_stdin"
        print(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    if len(text) > args.max_input_chars:
        envelope["candidate_review"]["status"] = "BLOCKED"
        envelope["candidate_review"]["verdict"] = "BLOCKED_INPUT_TOO_LARGE"
        envelope["candidate_review"]["risks"].append(
            f"stdin length {len(text)} exceeds max_input_chars {args.max_input_chars}"
        )
        envelope["candidate_review"]["recommended_next_gate"] = "summarize_or_chunk_sanitized_input"
        print(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    secret_findings = detect_secret_like(text)
    if secret_findings:
        envelope["candidate_review"]["status"] = "BLOCKED"
        envelope["candidate_review"]["verdict"] = "BLOCKED_SECRET_LIKE_INPUT"
        envelope["candidate_review"]["risks"].append("secret-like pattern detected in stdin")
        envelope["candidate_review"]["missing_evidence"].append("sanitized input proof")
        envelope["candidate_review"]["recommended_next_gate"] = "redact_input_then_retry"
        print(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    prompt = make_review_prompt(args.task, text)
    envelope["provider_request_candidate"] = {
        "model": args.model,
        "messages": [
            {
                "role": "system",
                "content": "You are a readonly candidate reviewer. Output JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    print(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
