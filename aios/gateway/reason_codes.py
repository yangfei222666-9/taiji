"""
Gateway reason codes — structured failure classification.
Format: gateway.category.subcode
"""


class GRC:
    OK = "OK.OK.OK"

    # Auth
    AUTH_MISSING_KEY = "gateway.auth.missing_key"
    AUTH_INVALID_KEY = "gateway.auth.invalid_key"
    AUTH_EXPIRED_KEY = "gateway.auth.expired_key"
    AUTH_RBAC_DENIED = "gateway.auth.rbac_denied"

    # Policy
    POLICY_MODEL_DENIED = "gateway.policy.model_not_allowed"
    POLICY_BUDGET_EXCEEDED = "gateway.policy.budget_exceeded"
    POLICY_RATE_LIMITED = "gateway.policy.rate_limited"

    # Provider
    PROV_TIMEOUT = "gateway.provider.timeout"
    PROV_HTTP_ERROR = "gateway.provider.http_error"
    PROV_RATE_LIMIT = "gateway.provider.rate_limit"
    PROV_UNAVAILABLE = "gateway.provider.unavailable"
    PROV_FAILOVER = "gateway.provider.failover_triggered"

    # Request
    REQ_INVALID_BODY = "gateway.request.invalid_body"
    REQ_MODEL_NOT_FOUND = "gateway.request.model_not_found"
    REQ_TOO_LARGE = "gateway.request.body_too_large"

    # Streaming
    STREAM_CLIENT_DISCONNECT = "gateway.stream.client_disconnect"
    STREAM_UPSTREAM_ERROR = "gateway.stream.upstream_error"


def exc_to_reason_code(exc: Exception) -> str:
    """Map common exceptions to gateway reason codes."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()

    if "timeout" in name or "timeout" in msg:
        return GRC.PROV_TIMEOUT
    if "429" in msg or "rate" in msg:
        return GRC.PROV_RATE_LIMIT
    if "connection" in name or "connection" in msg:
        return GRC.PROV_UNAVAILABLE
    if "json" in msg or "validation" in msg:
        return GRC.REQ_INVALID_BODY
    return GRC.PROV_HTTP_ERROR
