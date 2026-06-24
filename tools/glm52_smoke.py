#!/usr/bin/env python3
"""GLM-5.2 smoke probe with provider-call gating.

Default mode is dry-run: it does not read API keys and does not call providers.
Use --call only after opening a separate provider-call gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


DEFAULT_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_MODEL = "glm-5.2"
DEFAULT_KEY_ENVS = ("GLM_API_KEY", "BIGMODEL_API_KEY", "ZHIPUAI_API_KEY", "ZAI_API_KEY")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run or explicitly call a minimal GLM-5.2 smoke request.",
        epilog=(
            "Examples:\n"
            "  python3 tools/glm52_smoke.py\n"
            "  GLM_API_KEY=... python3 tools/glm52_smoke.py --call\n\n"
            "Boundary:\n"
            "  Dry-run mode does not read API keys and does not call providers.\n"
            "  --call sends only the configured smoke message, never repository content.\n"
            "  Provider output remains candidate evidence, not canonical truth."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--call", action="store_true", help="Actually call the provider API.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Chat completions endpoint.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name.")
    parser.add_argument("--message", default="ping", help="Smoke-test user message.")
    parser.add_argument("--max-tokens", type=int, default=16, help="Maximum output tokens.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds.")
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
    parser.add_argument(
        "--api-key-env",
        action="append",
        default=[],
        help=(
            "Environment variable to check for the API key when --call is used. "
            "Can be repeated. Defaults: GLM_API_KEY, BIGMODEL_API_KEY, ZHIPUAI_API_KEY, ZAI_API_KEY."
        ),
    )
    return parser


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": args.model,
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


def find_api_key(env_names: list[str]) -> tuple[str, str]:
    for name in env_names:
        value = os.environ.get(name)
        if value:
            return name, value
    raise RuntimeError(
        "missing_api_key_env: set one of "
        + ",".join(env_names)
        + " before running with --call"
    )


def redact(text: str, secret: str | None) -> str:
    if secret:
        text = text.replace(secret, "[REDACTED_API_KEY]")
    return text


def print_dry_run(args: argparse.Namespace, payload: dict[str, Any], env_names: list[str]) -> None:
    print("provider_called=false")
    print("api_key_read=false")
    print(f"endpoint={args.endpoint}")
    print(f"model={args.model}")
    print(f"api_key_env_candidates={','.join(env_names)}")
    print("request_payload=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))
    print("next_gate=run_with_explicit_provider_call_authorization")


def call_provider(args: argparse.Namespace, payload: dict[str, Any], env_names: list[str]) -> int:
    key_name, api_key = find_api_key(env_names)
    request = urllib.request.Request(
        args.endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            data = json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print("provider_called=true")
        print("api_key_printed=false")
        print(f"api_key_source={key_name}")
        print(f"http_status={exc.code}")
        print("verdict=FAIL_HTTP")
        print("error_body=" + redact(body[:1000], api_key))
        return 1
    except Exception as exc:
        print("provider_called=true")
        print("api_key_printed=false")
        print(f"api_key_source={key_name}")
        print("verdict=FAIL_EXCEPTION")
        print("error=" + redact(str(exc), api_key))
        return 1

    content = ""
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = str(message.get("content", ""))

    print("provider_called=true")
    print("api_key_printed=false")
    print(f"api_key_source={key_name}")
    print("http_status=200")
    print(f"response_model={data.get('model', '')}")
    print(f"choices_count={len(choices) if isinstance(choices, list) else 0}")
    print("response_preview=" + content[:200].replace("\n", "\\n"))
    print("verdict=PASS_SCOPED_PROVIDER_SMOKE_ONLY")
    print("cannot_claim=provider_ready,runtime_ready,truth_promotion,long_task_ready")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    env_names = args.api_key_env or list(DEFAULT_KEY_ENVS)
    payload = build_payload(args)

    if not args.call:
        print_dry_run(args, payload, env_names)
        return 0

    return call_provider(args, payload, env_names)


if __name__ == "__main__":
    sys.exit(main())
