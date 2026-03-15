from __future__ import annotations

import hashlib
import hmac

import pytest

import wbsb.feedback.auth as auth_mod
from wbsb.feedback.auth import verify_hmac, verify_timestamp


def _sign(body: bytes, timestamp: str, secret: str) -> str:
    signing_string = f"{timestamp}.{body.decode('utf-8')}"
    return hmac.new(
        secret.encode("utf-8"),
        signing_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def test_verify_hmac_valid() -> None:
    body = b'{"ok":true}'
    timestamp = "1710000000"
    secret = "super-secret"
    signature = _sign(body, timestamp, secret)

    assert verify_hmac(body, timestamp, signature, secret) is True


def test_verify_hmac_wrong_secret() -> None:
    body = b'{"ok":true}'
    timestamp = "1710000000"
    signature = _sign(body, timestamp, "correct-secret")

    assert verify_hmac(body, timestamp, signature, "wrong-secret") is False


def test_verify_hmac_tampered_body() -> None:
    original_body = b'{"ok":true}'
    tampered_body = b'{"ok":false}'
    timestamp = "1710000000"
    secret = "super-secret"
    signature = _sign(original_body, timestamp, secret)

    assert verify_hmac(tampered_body, timestamp, signature, secret) is False


def test_verify_hmac_tampered_timestamp() -> None:
    body = b'{"ok":true}'
    original_timestamp = "1710000000"
    tampered_timestamp = "1710000001"
    secret = "super-secret"
    signature = _sign(body, original_timestamp, secret)

    assert verify_hmac(body, tampered_timestamp, signature, secret) is False


def test_verify_hmac_malformed_signature() -> None:
    body = b'{"ok":true}'
    timestamp = "1710000000"
    secret = "super-secret"

    assert verify_hmac(body, timestamp, "not-a-hex-signature", secret) is False


def test_verify_hmac_empty_body() -> None:
    body = b""
    timestamp = "1710000000"
    secret = "super-secret"
    signature = _sign(body, timestamp, secret)

    assert verify_hmac(body, timestamp, signature, secret) is True


def test_verify_timestamp_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod.time, "time", lambda: 1_710_000_000)
    timestamp = str(1_710_000_000 - 60)

    assert verify_timestamp(timestamp) is True


def test_verify_timestamp_at_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod.time, "time", lambda: 1_710_000_000)
    timestamp = str(1_710_000_000 - 300)

    assert verify_timestamp(timestamp) is True


def test_verify_timestamp_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod.time, "time", lambda: 1_710_000_000)
    timestamp = str(1_710_000_000 - 301)

    assert verify_timestamp(timestamp) is False


def test_verify_timestamp_future(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod.time, "time", lambda: 1_710_000_000)
    timestamp = str(1_710_000_000 + 301)

    assert verify_timestamp(timestamp) is False


def test_verify_timestamp_non_integer() -> None:
    assert verify_timestamp("abc") is False
