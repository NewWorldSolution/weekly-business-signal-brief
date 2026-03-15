from enum import StrEnum


class RateLimitOutcome(StrEnum):
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

    def check(self, source_ip: str) -> RateLimitOutcome:
        """Never raises. Returns outcome; caller decides HTTP response."""
        raise NotImplementedError
