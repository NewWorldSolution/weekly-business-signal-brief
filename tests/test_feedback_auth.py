from __future__ import annotations

import hashlib
import hmac
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import wbsb.feedback.auth as auth_mod
from wbsb.feedback.auth import NonceStore, verify_hmac, verify_timestamp


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


def test_nonce_store_new_nonce() -> None:
    store = NonceStore()

    assert store.check_and_record("nonce-1") is True


def test_nonce_store_replay() -> None:
    store = NonceStore()

    assert store.check_and_record("nonce-1") is True
    assert store.check_and_record("nonce-1") is False


def test_nonce_store_expiry() -> None:
    store = NonceStore()

    with patch.object(auth_mod.time, "time", return_value=1_710_000_000):
        assert store.check_and_record("nonce-1") is True

    with patch.object(auth_mod.time, "time", return_value=1_710_000_601):
        assert store.check_and_record("nonce-1") is True


def test_nonce_store_different_nonces() -> None:
    store = NonceStore()

    assert store.check_and_record("nonce-1") is True
    assert store.check_and_record("nonce-2") is True


def test_nonce_store_capacity_eviction() -> None:
    store = NonceStore()

    with patch.object(auth_mod.time, "time", return_value=20_000):
        for i in range(10_001):
            assert store.check_and_record(f"nonce-{i}") is True

    assert len(store._store) == 10_000
    assert "nonce-0" not in store._store
    assert "nonce-1" in store._store
    assert "nonce-10000" in store._store


def test_nonce_store_thread_safety() -> None:
    store = NonceStore()
    results: list[bool] = []
    result_lock = threading.Lock()

    def _worker() -> None:
        result = store.check_and_record("shared-nonce")
        with result_lock:
            results.append(result)

    threads = [threading.Thread(target=_worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(True) == 1
    assert results.count(False) == 9
