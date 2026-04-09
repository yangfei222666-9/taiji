"""
Upstream provider clients — call LLM providers and return OpenAI-format responses.
Uses requests (sync, run in thread pool) to avoid adding httpx dependency.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
import requests
from typing import Generator, Optional

from .config import ProviderConfig
from .schemas import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,
    ChoiceMessage, UsageInfo, ChatCompletionChunk, StreamChoice, DeltaMessage,
)
from .errors import ProviderError, ProviderTimeoutError, ProviderUnavailableError

log = logging.getLogger("gateway.providers")


class BaseProvider:
    """Base class for upstream providers."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name

    def complete(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        raise NotImplementedError

    def stream(self, req: ChatCompletionRequest) -> Generator[str, None, None]:
        """Yield SSE lines: 'data: {...}\n\n' and final 'data: [DONE]\n\n'."""
        raise NotImplementedError

    def check_health(self) -> bool:
        return False


class OllamaProvider(BaseProvider):
    """Ollama via its OpenAI-compatible endpoint (/v1/chat/completions)."""

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}{path}"

    def _build_body(self, req: ChatCompletionRequest, stream: bool) -> dict:
        body = {
            "model": req.model,
            "messages": [m.model_dump(exclude_none=True) for m in req.messages],
            "stream": stream,
        }
        if req.temperature is not None:
            body["temperature"] = req.temperature
        if req.max_tokens is not None:
            body["max_tokens"] = req.max_tokens
        if req.top_p is not None:
            body["top_p"] = req.top_p
        if req.stop is not None:
            body["stop"] = req.stop
        return body

    def complete(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        url = self._url("/v1/chat/completions")
        body = self._build_body(req, stream=False)
        try:
            resp = requests.post(url, json=body, timeout=self.config.timeout_s)
        except requests.ConnectionError:
            raise ProviderUnavailableError(f"Ollama not reachable at {self.config.base_url}")
        except requests.Timeout:
            raise ProviderTimeoutError(f"Ollama timeout after {self.config.timeout_s}s")

        if resp.status_code != 200:
            raise ProviderError(f"Ollama returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        return ChatCompletionResponse(
            id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:12]}"),
            model=data.get("model", req.model),
            choices=[
                ChatCompletionChoice(
                    index=c.get("index", 0),
                    message=ChoiceMessage(
                        role=c.get("message", {}).get("role", "assistant"),
                        content=c.get("message", {}).get("content", ""),
                    ),
                    finish_reason=c.get("finish_reason", "stop"),
                )
                for c in data.get("choices", [])
            ],
            usage=UsageInfo(
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
                total_tokens=data.get("usage", {}).get("total_tokens", 0),
            ),
        )

    def stream(self, req: ChatCompletionRequest) -> Generator[str, None, None]:
        url = self._url("/v1/chat/completions")
        body = self._build_body(req, stream=True)
        try:
            resp = requests.post(url, json=body, timeout=self.config.timeout_s, stream=True)
        except requests.ConnectionError:
            raise ProviderUnavailableError(f"Ollama not reachable at {self.config.base_url}")
        except requests.Timeout:
            raise ProviderTimeoutError(f"Ollama timeout after {self.config.timeout_s}s")

        if resp.status_code != 200:
            raise ProviderError(f"Ollama returned {resp.status_code}")

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    yield "data: [DONE]\n\n"
                    return
                yield f"data: {payload}\n\n"

        yield "data: [DONE]\n\n"

    def check_health(self) -> bool:
        try:
            resp = requests.get(self._url("/api/tags"), timeout=3)
            return resp.status_code == 200
        except Exception:
            return False


class OpenAICompatProvider(BaseProvider):
    """Generic OpenAI-compatible provider (DeepSeek, PGT relay, etc.)."""

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}{path}"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        key = self.config.api_key
        if key:
            h["Authorization"] = f"Bearer {key}"
        return h

    def _build_body(self, req: ChatCompletionRequest, stream: bool) -> dict:
        body = {
            "model": req.model,
            "messages": [m.model_dump(exclude_none=True) for m in req.messages],
            "stream": stream,
        }
        if req.temperature is not None:
            body["temperature"] = req.temperature
        if req.max_tokens is not None:
            body["max_tokens"] = req.max_tokens
        return body

    def complete(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        url = self._url("/v1/chat/completions")
        try:
            resp = requests.post(url, json=self._build_body(req, False),
                                 headers=self._headers(), timeout=self.config.timeout_s)
        except requests.Timeout:
            raise ProviderTimeoutError(f"{self.name} timeout after {self.config.timeout_s}s")
        except requests.ConnectionError as e:
            # Connect timeout on non-routable IPs may surface as ConnectionError
            err_str = str(e).lower()
            if "timeout" in err_str or "timed out" in err_str:
                raise ProviderTimeoutError(f"{self.name} connect timeout after {self.config.timeout_s}s")
            raise ProviderUnavailableError(f"{self.name} not reachable")

        if resp.status_code != 200:
            raise ProviderError(f"{self.name} returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        return ChatCompletionResponse(
            id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:12]}"),
            model=data.get("model", req.model),
            choices=[
                ChatCompletionChoice(
                    index=c.get("index", 0),
                    message=ChoiceMessage(
                        role=c.get("message", {}).get("role", "assistant"),
                        content=c.get("message", {}).get("content", ""),
                    ),
                    finish_reason=c.get("finish_reason", "stop"),
                )
                for c in data.get("choices", [])
            ],
            usage=UsageInfo(
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
                total_tokens=data.get("usage", {}).get("total_tokens", 0),
            ),
        )

    def stream(self, req: ChatCompletionRequest) -> Generator[str, None, None]:
        url = self._url("/v1/chat/completions")
        try:
            resp = requests.post(url, json=self._build_body(req, True),
                                 headers=self._headers(), timeout=self.config.timeout_s, stream=True)
        except (requests.ConnectionError, requests.Timeout) as e:
            raise ProviderUnavailableError(f"{self.name}: {e}")

        if resp.status_code != 200:
            raise ProviderError(f"{self.name} returned {resp.status_code}")

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    yield "data: [DONE]\n\n"
                    return
                yield f"data: {payload}\n\n"

        yield "data: [DONE]\n\n"

    def check_health(self) -> bool:
        return bool(self.config.api_key)


def create_provider(config: ProviderConfig) -> BaseProvider:
    """Factory: create the right provider client based on config name."""
    if config.name == "ollama":
        return OllamaProvider(config)
    return OpenAICompatProvider(config)
