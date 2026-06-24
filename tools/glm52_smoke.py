#!/usr/bin/env python3
"""GLM-5.2 smoke probe with provider-call gating and model lock.

Default mode is dry-run: it does not read API keys and does not call providers.
Use --call only after opening a separate provider-call gate.

Provider lock:
- provider SDK: zhipuai.ZhipuAI only
- model: glm-5.2 only
- API key env: ZHIPUAI_API_KEY only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


LOCKED_PROVIDER = "zhipuai"
LOCKED_SDK = "zhipuai.ZhipuAI"
LOCKED_MODEL = "glm-5.2"
API_KEY_ENV = "ZHIPUAI_API_KEY"


class ProviderLockError(RuntimeError):
    """Raised when the provider/model lock is violated."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run or explicitly call a minimal locked GLM-5.2 smoke request.",
        epilog=(
            "Examples:\n"
            "  python3 tools/glm52_smoke.py\n"
            "  ZHIPUAI_API_KEY=... python3 tools/glm52_smoke.py --call\n\n"
            "Boundary:\n"
            "  Dry-run mode does not read API keys and does not call providers.\n"
            "  --call sends only the configured smoke message, never repository content.\n"
            "  Provider output remains candidate evidence, not canonical truth.\n"
            "  Model is locked to glm-5.2; no endpoint/model/env fallback exists."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--call", action="store_true", help="Actually call the locked GLM-5.2 provider API.")
    parser.add_argument("--message", default="ping", help="Smoke-test user message.")
    parser.add_argument("--max-tokens", type=int, default=16, help="Maximum output tokens.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument(
        "--thinking",
        choices=("enabled", "disabled"),
        default="disabled",
        help="Whether to include GLM thinking mode in the request payload.",
    )
    parser.add_argument(
        "--reasoning-effort",
        default="max",
        help="Reasoning effort value used only when --thinking enabled.",
    )
    return parser


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": LOCKED_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a provider smoke-test responder. Return 'pong' only.",
            },
            {"role": "user", "content": args.message},
        ],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }
    if args.thinking == "enabled":
        payload["thinking"] = {"type": "enabled"}
        payload["reasoning_effort"] = args.reasoning_effort
    return payload


def require_api_key() -> str:
    value = os.environ.get(API_KEY_ENV)
    if not value:
        raise ProviderLockError(f"missing_api_key_env: set {API_KEY_ENV} before running with --call")
    return value


def redact(text: str, secret: str | None) -> str:
    if secret:
        text = text.replace(secret, "[REDACTED_API_KEY]")
    return text


def print_dry_run(payload: dict[str, Any]) -> None:
    print("provider_called=false")
    print("api_key_read=false")
    print(f"locked_provider={LOCKED_PROVIDER}")
    print(f"locked_sdk={LOCKED_SDK}")
    print(f"locked_model={LOCKED_MODEL}")
    print(f"api_key_env={API_KEY_ENV}")
    print("dynamic_model_allowed=false")
    print("dynamic_endpoint_allowed=false")
    print("fallback_provider_allowed=false")
    print("request_payload=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))
    print("next_gate=run_with_explicit_provider_call_authorization")


def get_attr_or_key(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def extract_message_content(choice: Any) -> str:
    message = get_attr_or_key(choice, "message")
    if isinstance(message, dict):
        return str(message.get("content", ""))
    if message is not None:
        return str(getattr(message, "content", ""))
    return ""


def call_provider(payload: dict[str, Any]) -> int:
    api_key = None
    try:
        api_key = require_api_key()
        from zhipuai import ZhipuAI  # type: ignore[import-not-found]

        client = ZhipuAI(api_key=api_key)
        response = client.chat.completions.create(**payload)
        response_model = str(get_attr_or_key(response, "model") or "")
        if response_model != LOCKED_MODEL:
            raise ProviderLockError(f"unexpected_model={response_model!r}; expected={LOCKED_MODEL!r}")

        choices = get_attr_or_key(response, "choices") or []
        content = extract_message_content(choices[0]) if choices else ""
    except Exception as exc:
        print("provider_called=true")
        print("api_key_printed=false")
        print(f"api_key_source={API_KEY_ENV}")
        print(f"locked_provider={LOCKED_PROVIDER}")
        print(f"locked_model={LOCKED_MODEL}")
        print("verdict=FAIL_PROVIDER_LOCKED_SMOKE")
        print("error=" + redact(str(exc), api_key))
        return 1

    print("provider_called=true")
    print("api_key_printed=false")
    print(f"api_key_source={API_KEY_ENV}")
    print(f"locked_provider={LOCKED_PROVIDER}")
    print(f"locked_sdk={LOCKED_SDK}")
    print(f"response_model={response_model}")
    print(f"choices_count={len(choices)}")
    print("response_preview=" + content[:200].replace("\n", "\\n"))
    print("verdict=PASS_SCOPED_PROVIDER_SMOKE_ONLY")
    print("cannot_claim=provider_ready,runtime_ready,truth_promotion,long_task_ready")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    payload = build_payload(args)

    if not args.call:
        print_dry_run(payload)
        return 0

    return call_provider(payload)


if __name__ == "__main__":
    sys.exit(main())
