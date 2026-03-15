from __future__ import annotations

import hashlib
import hmac
import threading
import time

HEADER_TIMESTAMP = "X-WBSB-Timestamp"
HEADER_SIGNATURE = "X-WBSB-Signature"
HEADER_NONCE = "X-WBSB-Nonce"


def verify_hmac(
    body: bytes,
    timestamp: str,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify HMAC-SHA256 signature. Uses hmac.compare_digest — constant-time.
    Returns False (never raises) if inputs are malformed.
    Signing string: f"{timestamp}.{body.decode('utf-8')}"
    """
    try:
        signing_string = f"{timestamp}.{body.decode('utf-8')}"
        expected = hmac.new(
            secret.encode("utf-8"),
            signing_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def verify_timestamp(timestamp: str, max_age_seconds: int = 300) -> bool:
    """
    Returns True if abs(now - timestamp) <= max_age_seconds.
    Returns False if timestamp is non-integer or out of window.
    """
    try:
        parsed = int(timestamp)
    except Exception:
        return False
    return abs(time.time() - parsed) <= max_age_seconds


class NonceStore:
    """
    In-memory nonce deduplication. TTL = 10 minutes. Max 10,000 entries (LRU eviction).
    Thread-safe via threading.Lock.
    Does not survive process restart — timestamp freshness window is the fallback.
    On restart, verify_timestamp() provides the only replay protection for the
    first 5 minutes until the TTL window catches up again.
    """

    def __init__(self) -> None:
        self._store: dict[str, float] = {}
        self._lock = threading.Lock()

    def check_and_record(self, nonce: str) -> bool:
        """
        Returns True if nonce is new (allow).
        Returns False if nonce was seen within TTL window (replay — reject).
        Side effect: records the nonce if new.
        """
        with self._lock:
            now = time.time()
            expired = [key for key, expiry in self._store.items() if expiry < now]
            for key in expired:
                del self._store[key]

            if nonce in self._store:
                return False

            if len(self._store) >= 10_000:
                oldest_key = min(self._store, key=lambda key: self._store[key])
                del self._store[oldest_key]

            self._store[nonce] = now + 600
            return True
