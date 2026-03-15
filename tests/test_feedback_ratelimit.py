from __future__ import annotations

from collections import deque
from unittest.mock import patch

from wbsb.feedback.ratelimit import RateLimiter, RateLimitOutcome


def test_rate_limiter_allows_normal_traffic() -> None:
    limiter = RateLimiter()

    results = [limiter.check("10.0.0.1") for _ in range(10)]

    assert results == [RateLimitOutcome.allowed] * 10


def test_rate_limiter_burst_within_limit() -> None:
    limiter = RateLimiter()

    results = [limiter.check("10.0.0.1") for _ in range(13)]

    assert results[-1] == RateLimitOutcome.allowed


def test_rate_limiter_per_ip_exceeded() -> None:
    limiter = RateLimiter()

    for _ in range(13):
        assert limiter.check("10.0.0.1") == RateLimitOutcome.allowed

    assert limiter.check("10.0.0.1") == RateLimitOutcome.per_ip_exceeded


def test_rate_limiter_global_exceeded() -> None:
    limiter = RateLimiter()

    for i in range(100):
        source_ip = f"10.0.{i // 256}.{i % 256}"
        assert limiter.check(source_ip) == RateLimitOutcome.allowed

    assert limiter.check("10.0.0.250") == RateLimitOutcome.global_exceeded


def test_rate_limiter_window_resets() -> None:
    limiter = RateLimiter()

    with patch("wbsb.feedback.ratelimit.time.time", side_effect=[1000.0] * 14 + [1061.0]):
        for _ in range(13):
            assert limiter.check("10.0.0.1") == RateLimitOutcome.allowed
        assert limiter.check("10.0.0.1") == RateLimitOutcome.per_ip_exceeded
        assert limiter.check("10.0.0.1") == RateLimitOutcome.allowed


def test_rate_limiter_different_ips_independent() -> None:
    limiter = RateLimiter()

    for _ in range(13):
        assert limiter.check("10.0.0.1") == RateLimitOutcome.allowed

    assert limiter.check("10.0.0.2") == RateLimitOutcome.allowed


def test_rate_limiter_fail_open() -> None:
    limiter = RateLimiter()
    limiter._global_window = None  # type: ignore[assignment]

    assert limiter.check("10.0.0.1") == RateLimitOutcome.allowed


def test_rate_limiter_evicts_empty_ip_windows() -> None:
    limiter = RateLimiter()
    limiter._ip_windows["10.0.0.1"] = deque([1.0])

    with patch("wbsb.feedback.ratelimit.time.time", return_value=100.0):
        assert limiter.check("10.0.0.2") == RateLimitOutcome.allowed

    assert "10.0.0.1" not in limiter._ip_windows
