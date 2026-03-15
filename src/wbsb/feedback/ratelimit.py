from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from enum import Enum


class RateLimitOutcome(str, Enum):  # noqa: UP042 - matches the frozen I11 contract
    allowed = "allowed"
    per_ip_exceeded = "per_ip_exceeded"  # HTTP 429
    global_exceeded = "global_exceeded"  # HTTP 503


class RateLimiter:
    """
    Per-IP: 10 req/60s sliding window + burst 3.
    Global: 100 req/60s circuit breaker.
    In-memory only. Does not survive restart.
    Thread-safe via threading.Lock.
    Fail-open: on internal error returns allowed and logs.
    """

    _PER_IP_LIMIT = 10
    _PER_IP_BURST = 3
    _GLOBAL_LIMIT = 100
    _WINDOW = 60.0
    _EVICTION_WINDOW = 120.0

    def __init__(self) -> None:
        self._ip_windows: dict[str, deque[float]] = defaultdict(deque)
        self._global_window: deque[float] = deque()
        self._lock = threading.Lock()
        self._log = logging.getLogger(__name__)

    def check(self, source_ip: str) -> RateLimitOutcome:
        """Never raises. Returns outcome; caller decides HTTP response."""
        try:
            with self._lock:
                now = time.time()
                cutoff = now - self._WINDOW

                self._purge_window(self._global_window, cutoff)
                if len(self._global_window) >= self._GLOBAL_LIMIT:
                    return RateLimitOutcome.global_exceeded

                self._purge_stale_ips(now - self._EVICTION_WINDOW)
                ip_window = self._ip_windows[source_ip]
                self._purge_window(ip_window, cutoff)
                if len(ip_window) >= self._PER_IP_LIMIT + self._PER_IP_BURST:
                    return RateLimitOutcome.per_ip_exceeded

                self._global_window.append(now)
                ip_window.append(now)
                return RateLimitOutcome.allowed
        except Exception:
            self._log.exception("feedback.ratelimit.check_failed")
            return RateLimitOutcome.allowed

    @staticmethod
    def _purge_window(window: deque[float], cutoff: float) -> None:
        while window and window[0] < cutoff:
            window.popleft()

    def _purge_stale_ips(self, cutoff: float) -> None:
        stale_ips: list[str] = []
        for source_ip, window in self._ip_windows.items():
            self._purge_window(window, cutoff)
            if not window:
                stale_ips.append(source_ip)
        for source_ip in stale_ips:
            del self._ip_windows[source_ip]
