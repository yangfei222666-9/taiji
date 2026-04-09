"""
SSE streaming helper — wraps provider stream into FastAPI StreamingResponse.
"""
from __future__ import annotations

import logging
from typing import Generator

from fastapi.responses import StreamingResponse

log = logging.getLogger("gateway.streaming")


def sse_response(sse_generator: Generator[str, None, None]) -> StreamingResponse:
    """Wrap an SSE generator into a FastAPI StreamingResponse."""
    return StreamingResponse(
        sse_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
