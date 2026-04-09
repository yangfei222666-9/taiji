"""
TaijiOS LLM Gateway — FastAPI application.
"""
from __future__ import annotations

import asyncio
import time
import uuid
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import load_config, GatewayConfig
from .schemas import (
    ModelInfo, ModelListResponse, ErrorResponse, ErrorDetail,
    ChatCompletionRequest,
)
from .auth import verify_request
from .router import ProviderRouter
from .providers import create_provider
from .streaming import sse_response
from .errors import (
    GatewayError, AuthError, ModelNotFoundError, register_error_handlers,
    ProviderError, ProviderTimeoutError, ProviderUnavailableError,
)
from .reason_codes import GRC
from .policy import enforce_policy
from .audit import audit_request

import threading
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [gateway] %(levelname)s %(message)s")
log = logging.getLogger("gateway")

# ── Config ───────────────────────────────────────────────────────
_cfg: GatewayConfig | None = None


def get_config() -> GatewayConfig:
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg


# ── App ──────────────────────────────────────────────────────────
app = FastAPI(title="TaijiOS LLM Gateway", version="0.1.0")

cfg = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

register_error_handlers(app)

_start_time = time.time()
_router = ProviderRouter(cfg)

# ── Request stats ───────────────────────────────────────────────
_stats_lock = threading.Lock()
_stats = {
    "total_requests": 0,
    "total_errors": 0,
    "total_tokens": 0,
    "by_model": defaultdict(int),
    "by_provider": defaultdict(int),
    "by_caller": defaultdict(int),
    "by_status": defaultdict(int),
    "latency_sum_ms": 0.0,
}


def _record_stat(model: str, provider: str, caller: str, status: int, latency_ms: float, tokens: int = 0):
    with _stats_lock:
        _stats["total_requests"] += 1
        if status >= 400:
            _stats["total_errors"] += 1
        _stats["total_tokens"] += tokens
        _stats["by_model"][model] += 1
        _stats["by_provider"][provider] += 1
        _stats["by_caller"][caller] += 1
        _stats["by_status"][str(status)] += 1
        _stats["latency_sum_ms"] += latency_ms


# ── Request ID middleware ────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id", uuid.uuid4().hex[:12])
    request.state.request_id = request_id
    request.state.start_time = time.time()
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# ── Routes ───────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check — per-provider live status, no auth required."""
    config = get_config()
    checks = {}
    for p in config.providers:
        if not p.enabled:
            continue
        try:
            prov = create_provider(p)
            checks[p.name] = "ok" if prov.check_health() else "degraded"
        except Exception:
            checks[p.name] = "error"

    all_ok = all(v == "ok" for v in checks.values()) if checks else False
    result = {
        "status": "ok" if all_ok else "degraded",
        "service": "taijios-llm-gateway",
        "version": "0.1.0",
        "port": config.port,
        "uptime_s": round(time.time() - _start_time, 1),
        "checks": checks,
    }
    # Auto-dump for gate consumption
    try:
        import json as _json
        (DATA_DIR / "health_latest.json").write_text(
            _json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return result


@app.get("/v1/models")
async def list_models():
    """List available models in OpenAI format."""
    config = get_config()
    models = []
    for p in config.providers:
        if not p.enabled:
            continue
        for m in p.models:
            models.append(ModelInfo(id=m, owned_by=p.name))
    return ModelListResponse(data=models)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions — sync and streaming."""
    request_id = getattr(request.state, "request_id", "unknown")
    start = time.time()
    identity = None
    model = ""
    provider_name = ""
    stream = False

    try:
        # 1. Auth
        identity = verify_request(request)
        if identity is None:
            raise AuthError("Invalid or missing API key")

        # 2. Parse body
        try:
            body = await request.json()
            req = ChatCompletionRequest(**body)
        except Exception as e:
            raise GatewayError(f"Invalid request body: {e}", status_code=400, reason_code=GRC.REQ_INVALID_BODY)

        model = req.model
        stream = req.stream

        # 2.5. Refine caller_id from x-caller context (service_token only)
        if identity.caller_class == "service_token" and body.get("x-caller"):
            identity.caller_id = body["x-caller"]

        # 3. Policy (RBAC + model allowlist + rate limit + budget)
        enforce_policy(identity, req.model, stream=req.stream)

        # 4. Route + 5. Execute (with failover)
        provider_cfg = _router.select(req.model)
        if provider_cfg is None:
            raise ModelNotFoundError(f"No provider available for model: {req.model}")

        provider = create_provider(provider_cfg)
        provider_name = provider.name
        log.info(f"[{request_id}] {identity.caller_id} -> {provider.name}/{req.model} stream={req.stream}")

        loop = asyncio.get_event_loop()

        if req.stream:
            def _stream_gen():
                try:
                    yield from provider.stream(req)
                except Exception as e:
                    log.error(f"Stream error: {e}")
                    import json as _json
                    err = {"error": {"message": str(e), "type": "stream_error"}}
                    yield f"data: {_json.dumps(err)}\n\n"
                    yield "data: [DONE]\n\n"

            # Audit for streaming — record at dispatch time (tokens unknown)
            latency_ms = (time.time() - start) * 1000
            audit_request(
                request_id=request_id, identity=identity, model=model,
                provider=provider_name, stream=True, status_code=200,
                reason_code=GRC.OK, latency_ms=latency_ms,
            )
            _record_stat(model, provider_name, identity.caller_id, 200, latency_ms)
            return sse_response(_stream_gen())
        else:
            # Non-streaming with failover
            last_error = None
            tried_providers = []

            while provider_cfg is not None:
                provider = create_provider(provider_cfg)
                provider_name = provider.name
                tried_providers.append(provider_name)
                try:
                    response = await loop.run_in_executor(None, provider.complete, req)
                    latency_ms = (time.time() - start) * 1000
                    usage = response.usage
                    total_tok = (usage.prompt_tokens + usage.completion_tokens) if usage else 0
                    reason = GRC.OK
                    if len(tried_providers) > 1:
                        reason = GRC.PROV_FAILOVER
                        log.warning(f"[{request_id}] Failover succeeded: {' -> '.join(tried_providers)}")
                    audit_request(
                        request_id=request_id, identity=identity, model=model,
                        provider=provider_name, stream=False, status_code=200,
                        reason_code=reason, latency_ms=latency_ms,
                        prompt_tokens=usage.prompt_tokens if usage else 0,
                        completion_tokens=usage.completion_tokens if usage else 0,
                    )
                    _record_stat(model, provider_name, identity.caller_id, 200, latency_ms, total_tok)
                    return response.model_dump()
                except (ProviderError, ProviderTimeoutError, ProviderUnavailableError) as e:
                    if last_error is None:
                        last_error = e  # preserve first error as root cause
                    log.warning(f"[{request_id}] Provider {provider_name} failed: {e}, trying failover")
                    _router.mark_degraded(provider_name)
                    provider_cfg = _router.select(req.model)
                    # Don't retry same provider
                    if provider_cfg and provider_cfg.name in tried_providers:
                        provider_cfg = None
                except Exception as e:
                    # Unexpected provider error — wrap as ProviderError for consistent handling
                    from .reason_codes import exc_to_reason_code
                    rc = exc_to_reason_code(e)
                    wrapped = ProviderError(f"{provider_name}: {e}", reason_code=rc)
                    if last_error is None:
                        last_error = wrapped
                    log.warning(f"[{request_id}] Provider {provider_name} unexpected error: {e}, trying failover")
                    _router.mark_degraded(provider_name)
                    provider_cfg = _router.select(req.model)
                    if provider_cfg and provider_cfg.name in tried_providers:
                        provider_cfg = None

            # All providers failed — raise the last error
            if last_error and isinstance(last_error, GatewayError):
                raise last_error
            raise GatewayError(
                f"All providers failed: {', '.join(tried_providers)}",
                status_code=502,
                reason_code=GRC.PROV_UNAVAILABLE,
            )

    except GatewayError as e:
        latency_ms = (time.time() - start) * 1000
        if identity:
            audit_request(
                request_id=request_id, identity=identity, model=model,
                provider=provider_name, stream=stream, status_code=e.status_code,
                reason_code=e.reason_code, latency_ms=latency_ms, error=str(e),
            )
            _record_stat(model, provider_name, identity.caller_id, e.status_code, latency_ms)
        raise
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        log.error(f"Completion error: {e}")
        if identity:
            audit_request(
                request_id=request_id, identity=identity, model=model,
                provider=provider_name, stream=stream, status_code=502,
                reason_code=GRC.PROV_HTTP_ERROR, latency_ms=latency_ms, error=str(e),
            )
            _record_stat(model, provider_name, identity.caller_id, 502, latency_ms)
        raise GatewayError(f"Provider error: {e}", status_code=502)


@app.get("/stats")
async def stats():
    """Request statistics — no auth required (localhost-only anyway)."""
    with _stats_lock:
        total = _stats["total_requests"]
        avg_latency = (_stats["latency_sum_ms"] / total) if total > 0 else 0
        result = {
            "uptime_s": round(time.time() - _start_time, 1),
            "total_requests": total,
            "total_errors": _stats["total_errors"],
            "total_tokens": _stats["total_tokens"],
            "avg_latency_ms": round(avg_latency, 1),
            "by_model": dict(_stats["by_model"]),
            "by_provider": dict(_stats["by_provider"]),
            "by_caller": dict(_stats["by_caller"]),
            "by_status": dict(_stats["by_status"]),
        }
    # Auto-dump for gate consumption
    try:
        import json as _json
        (DATA_DIR / "stats_latest.json").write_text(
            _json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return result
