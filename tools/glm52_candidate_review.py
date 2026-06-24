#!/usr/bin/env python3
"""Build a local-only GLM-5.2 candidate-review request envelope from stdin.

This script intentionally does not call a provider. It reads sanitized text from
stdin and emits a JSON candidate-review envelope that can be used in a later,
separately authorized provider-call gate.

Provider lock:
- provider SDK: zhipuai.ZhipuAI only
- model: glm-5.2 only
- API key env: ZHIPUAI_API_KEY only
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from typing import Any


LOCKED_PROVIDER = "zhipuai"
LOCKED_SDK = "zhipuai.ZhipuAI"
LOCKED_MODEL = "glm-5.2"
API_KEY_ENV = "ZHIPUAI_API_KEY"
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
            "candidate_review JSON envelope locked to GLM-5.2."
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
            "  Output remains candidate evidence, not canonical truth.\n"
            "  Provider request candidate is locked to zhipuai.ZhipuAI + glm-5.2."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--task", default="candidate_review", help="Review task label.")
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
        "locked_provider": LOCKED_PROVIDER,
        "locked_sdk": LOCKED_SDK,
        "locked_model": LOCKED_MODEL,
        "api_key_env": API_KEY_ENV,
        "dynamic_model_allowed": False,
        "dynamic_endpoint_allowed": False,
        "fallback_provider_allowed": False,
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
        "provider": LOCKED_PROVIDER,
        "sdk": LOCKED_SDK,
        "api_key_env": API_KEY_ENV,
        "model": LOCKED_MODEL,
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
