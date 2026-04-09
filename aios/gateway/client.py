"""
Gateway internal SDK — unified client for TaijiOS services.
Usage:
    from aios.gateway.client import GatewayClient
    gw = GatewayClient()
    text = gw.complete_simple("hello")
    resp = gw.complete(model="qwen2.5:3b", messages=[...])
    models = gw.models()
"""
from __future__ import annotations

import json
import logging
import os
import requests
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("gateway.client")

_DEFAULT_BASE = "http://127.0.0.1:9200"


@dataclass
class GatewayResult:
    """Structured result from a Gateway call."""
    success: bool = False
    content: str = ""
    model: str = ""
    provider: str = ""
    reason_code: str = ""
    error: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict = field(default_factory=dict)


@dataclass
class GatewayContext:
    """TaijiOS context fields injected into every request."""
    caller_type: str = ""       # e.g. "queued_router", "bridge", "quiz_grader"
    task_id: str = ""
    task_type: str = ""
    agent_id: str = ""
    session_id: str = ""
    run_id: str = ""
    route_profile: str = ""     # e.g. "default", "fast", "cheap"


class GatewayClient:
    """Sync HTTP client for the TaijiOS LLM Gateway."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_token: Optional[str] = None,
        timeout_s: int = 120,
    ):
        self.base_url = (
            base_url
            or os.getenv("TAIJIOS_GATEWAY_URL", _DEFAULT_BASE)
        ).rstrip("/")
        self.token = api_token or os.getenv("TAIJIOS_API_TOKEN", "")
        self.timeout = timeout_s

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def health(self) -> dict:
        """Check gateway health."""
        resp = requests.get(self._url("/health"), timeout=5)
        return resp.json()

    def is_available(self) -> bool:
        """Return True if gateway is reachable and healthy."""
        try:
            h = self.health()
            return h.get("status") in ("ok", "degraded")
        except Exception:
            return False

    def models(self) -> list[dict]:
        """List available models. Returns list of {id, owned_by}."""
        try:
            resp = requests.get(self._url("/v1/models"), headers=self._headers(), timeout=5)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            log.warning(f"models() failed: {e}")
            return []

    def _parse_error(self, resp: requests.Response) -> GatewayResult:
        """Parse a non-200 response into a GatewayResult with reason_code."""
        reason_code = ""
        error_msg = f"HTTP {resp.status_code}"
        try:
            body = resp.json()
            err = body.get("error", {})
            error_msg = err.get("message", error_msg)
            reason_code = err.get("code", "")
        except Exception:
            pass
        return GatewayResult(
            success=False, error=error_msg, reason_code=reason_code,
            raw={"status_code": resp.status_code},
        )

    def _inject_context(self, body: dict, ctx: GatewayContext | None):
        """Inject TaijiOS context fields as x- extensions."""
        if ctx is None:
            return
        if ctx.caller_type:
            body["x-caller"] = ctx.caller_type
        if ctx.task_id:
            body["x-task-id"] = ctx.task_id
        if ctx.session_id:
            body["x-session-id"] = ctx.session_id
        if ctx.agent_id:
            body.setdefault("x-agent-id", ctx.agent_id)
        if ctx.task_type:
            body.setdefault("x-task-type", ctx.task_type)
        if ctx.run_id:
            body.setdefault("x-run-id", ctx.run_id)
        if ctx.route_profile:
            body.setdefault("x-route-profile", ctx.route_profile)

    def chat_completions(
        self,
        model: str = "qwen2.5:3b",
        messages: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        ctx: GatewayContext | None = None,
        **kwargs,
    ) -> GatewayResult:
        """
        Context-aware chat completion. Returns structured GatewayResult.
        Preferred over complete() for internal TaijiOS calls.
        """
        body: dict = {
            "model": model,
            "messages": messages or [],
            "stream": stream,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        self._inject_context(body, ctx)
        body.update(kwargs)

        try:
            resp = requests.post(
                self._url("/v1/chat/completions"),
                json=body,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.ConnectionError:
            return GatewayResult(success=False, error="Gateway unreachable",
                                reason_code="gateway.provider.unavailable")
        except requests.Timeout:
            return GatewayResult(success=False, error="Gateway timeout",
                                reason_code="gateway.provider.timeout")

        if resp.status_code != 200:
            return self._parse_error(resp)

        data = resp.json()
        choices = data.get("choices", [])
        content = ""
        if choices:
            content = choices[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return GatewayResult(
            success=True,
            content=content,
            model=data.get("model", model),
            reason_code="OK.OK.OK",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            raw=data,
        )

    def complete(
        self,
        model: str = "qwen2.5:3b",
        messages: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs,
    ) -> dict:
        """
        Send a chat completion request. Returns the full OpenAI-format dict.
        Raises requests.HTTPError on non-200.
        """
        body: dict = {
            "model": model,
            "messages": messages or [],
            "stream": stream,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        body.update(kwargs)

        resp = requests.post(
            self._url("/v1/chat/completions"),
            json=body,
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def complete_simple(
        self,
        prompt: str,
        model: str = "qwen2.5:3b",
        system: str = "",
        **kwargs,
    ) -> str:
        """
        Convenience: send a single user message, return the assistant text.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data = self.complete(model=model, messages=messages, **kwargs)
        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")
