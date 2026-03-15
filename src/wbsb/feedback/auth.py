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
    raise NotImplementedError


def verify_timestamp(timestamp: str, max_age_seconds: int = 300) -> bool:
    """
    Returns True if abs(now - timestamp) <= max_age_seconds.
    Returns False if timestamp is non-integer or out of window.
    """
    raise NotImplementedError


class NonceStore:
    """
    In-memory nonce deduplication. TTL = 10 minutes. Max 10,000 entries (LRU eviction).
    Thread-safe via threading.Lock.
    Does not survive process restart — timestamp freshness window is the fallback.
    """

    def check_and_record(self, nonce: str) -> bool:
        """
        Returns True if nonce is new (allow).
        Returns False if nonce was seen within TTL window (replay — reject).
        Side effect: records the nonce if new.
        """
        raise NotImplementedError
