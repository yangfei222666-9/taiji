import asyncio

from aios.gateway import app as gateway
from aios.gateway.auth import CallerIdentity
from aios.gateway.reason_codes import GRC


class _State:
    request_id = "request-1"


class _Request:
    state = _State()

    async def json(self):
        return {
            "model": "qwen-test",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        }


class _Router:
    def select(self, model):
        return object()


class _BeforeFirstChunkFailure:
    name = "broken"

    def stream(self, req):
        raise RuntimeError("upstream failed before first chunk")
        yield


class _MidStreamFailure:
    name = "broken"

    def stream(self, req):
        yield 'data: {"delta":"prefix"}\n\n'
        raise RuntimeError("upstream failed after first chunk")


class _SuccessfulStream:
    name = "healthy"

    def stream(self, req):
        yield 'data: {"delta":"complete"}\n\n'
        yield "data: [DONE]\n\n"


def _dispatch(monkeypatch, provider):
    audits = []
    stats = []

    monkeypatch.setattr(
        gateway,
        "verify_request",
        lambda request: CallerIdentity("caller", "api_key", "operator"),
    )
    monkeypatch.setattr(gateway, "enforce_policy", lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway, "_router", _Router())
    monkeypatch.setattr(gateway, "create_provider", lambda config: provider)
    monkeypatch.setattr(gateway, "audit_request", lambda **entry: audits.append(entry))
    monkeypatch.setattr(
        gateway,
        "_record_stat",
        lambda model, provider_name, caller, status, latency_ms, tokens=0: stats.append(status),
    )
    monkeypatch.setattr(gateway, "sse_response", lambda stream: stream)

    stream = asyncio.run(gateway.chat_completions(_Request()))
    return stream, audits, stats


def test_failure_before_first_chunk_is_not_audited_as_ok(monkeypatch):
    stream, audits, stats = _dispatch(monkeypatch, _BeforeFirstChunkFailure())

    assert audits == []
    chunks = list(stream)

    assert any("stream_error" in chunk for chunk in chunks)
    assert len(audits) == 1
    assert audits[0]["status_code"] == 502
    assert audits[0]["reason_code"] == GRC.STREAM_UPSTREAM_ERROR
    assert stats == [502]


def test_failure_after_first_chunk_is_not_audited_as_ok(monkeypatch):
    stream, audits, stats = _dispatch(monkeypatch, _MidStreamFailure())

    assert audits == []
    chunks = list(stream)

    assert "prefix" in chunks[0]
    assert any("stream_error" in chunk for chunk in chunks[1:])
    assert len(audits) == 1
    assert audits[0]["status_code"] == 502
    assert audits[0]["reason_code"] == GRC.STREAM_UPSTREAM_ERROR
    assert stats == [502]


def test_success_is_audited_once_after_stream_exhaustion(monkeypatch):
    stream, audits, stats = _dispatch(monkeypatch, _SuccessfulStream())

    assert audits == []
    chunks = list(stream)

    assert chunks[-1] == "data: [DONE]\n\n"
    assert len(audits) == 1
    assert audits[0]["status_code"] == 200
    assert audits[0]["reason_code"] == GRC.OK
    assert stats == [200]
