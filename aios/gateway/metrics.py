"""
Gateway metrics — lightweight counters/gauges compatible with TaijiOS observability.
Integrates with aios.observability.metrics if available, otherwise standalone.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from threading import Lock

log = logging.getLogger("gateway.metrics")


class GatewayMetrics:
    """In-process metrics for the gateway. Thread-safe."""

    def __init__(self):
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._start = time.time()

    def inc(self, name: str, value: int = 1):
        with self._lock:
            self._counters[name] += value

    def gauge(self, name: str, value: float):
        with self._lock:
            self._gauges[name] = value

    def observe(self, name: str, value: float):
        with self._lock:
            h = self._histograms[name]
            h.append(value)
            if len(h) > 10000:
                self._histograms[name] = h[-5000:]

    def snapshot(self) -> dict:
        with self._lock:
            hist_summary = {}
            for name, values in self._histograms.items():
                if values:
                    s = sorted(values)
                    n = len(s)
                    hist_summary[name] = {
                        "count": n,
                        "p50": s[n // 2],
                        "p95": s[int(n * 0.95)],
                        "p99": s[int(n * 0.99)],
                        "max": s[-1],
                    }
            return {
                "uptime_s": round(time.time() - self._start, 1),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": hist_summary,
            }
