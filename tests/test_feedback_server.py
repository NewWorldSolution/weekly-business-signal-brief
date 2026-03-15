"""Tests for wbsb.feedback.server (POST /feedback webhook)."""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wbsb.feedback.auth import NonceStore
from wbsb.feedback.ratelimit import RateLimiter, RateLimitOutcome
from wbsb.feedback.server import MAX_BODY_BYTES, FeedbackHandler

# ---------------------------------------------------------------------------
# Valid payload fixture
# ---------------------------------------------------------------------------

_VALID_PAYLOAD = {
    "run_id": "20260310T090000Z_abc123",
    "section": "situation",
    "label": "expected",
    "comment": "Looks right.",
    "operator": "tester",
}

_TEST_SECRET = "test-secret"


# ---------------------------------------------------------------------------
# Auth header helper
# ---------------------------------------------------------------------------


def make_auth_headers(body: bytes, secret: str = _TEST_SECRET) -> dict:
    """Build valid X-WBSB-* auth headers for a request body."""
    ts = str(int(time.time()))
    nonce = str(uuid.uuid4())
    signing = f"{ts}.{body.decode()}"
    sig = hmac.new(secret.encode(), signing.encode(), hashlib.sha256).hexdigest()
    return {
        "X-WBSB-Timestamp": ts,
        "X-WBSB-Signature": sig,
        "X-WBSB-Nonce": nonce,
    }


# ---------------------------------------------------------------------------
# Server fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def feedback_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Dev-mode server — auth bypassed. All I9 tests use this fixture."""
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setattr("wbsb.feedback.store.FEEDBACK_DIR", feedback_dir)
    monkeypatch.setenv("WBSB_ENV", "development")

    import wbsb.feedback.server as server_mod

    monkeypatch.setattr(server_mod, "_nonce_store", NonceStore())
    monkeypatch.setattr(server_mod, "_rate_limiter", RateLimiter())

    srv = HTTPServer(("127.0.0.1", 0), FeedbackHandler)
    host, port = srv.server_address
    thread = threading.Thread(target=srv.serve_forever)
    thread.daemon = True
    thread.start()

    yield f"http://{host}:{port}", feedback_dir

    srv.shutdown()
    thread.join(timeout=2)


@pytest.fixture()
def feedback_server_prod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Production-mode server — HMAC auth enforced, known test secret."""
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setattr("wbsb.feedback.store.FEEDBACK_DIR", feedback_dir)
    monkeypatch.setenv("WBSB_ENV", "production")
    monkeypatch.setenv("WBSB_FEEDBACK_SECRET", _TEST_SECRET)

    import wbsb.feedback.server as server_mod

    monkeypatch.setattr(server_mod, "_nonce_store", NonceStore())
    monkeypatch.setattr(server_mod, "_rate_limiter", RateLimiter())

    srv = HTTPServer(("127.0.0.1", 0), FeedbackHandler)
    host, port = srv.server_address
    thread = threading.Thread(target=srv.serve_forever)
    thread.daemon = True
    thread.start()

    yield f"http://{host}:{port}", feedback_dir

    srv.shutdown()
    thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post(url: str, payload: dict) -> tuple[int, dict]:
    """POST JSON to url; return (status_code, response_dict)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _post_h(
    url: str,
    payload: dict | None = None,
    extra_headers: dict | None = None,
    raw_body: bytes | None = None,
) -> tuple[int, dict, dict]:
    """POST with custom headers; return (status_code, response_dict, response_headers)."""
    body = raw_body if raw_body is not None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read()), dict(exc.headers)


# ---------------------------------------------------------------------------
# I9 regression tests (dev-mode fixture — unchanged behaviour)
# ---------------------------------------------------------------------------


def test_valid_feedback_returns_200(feedback_server) -> None:
    """Valid payload → HTTP 200 with a feedback_id in the response."""
    url, _ = feedback_server
    status, body = _post(f"{url}/feedback", _VALID_PAYLOAD)

    assert status == 200
    assert body["status"] == "ok"
    assert "feedback_id" in body
    assert body["feedback_id"]  # non-empty


def test_invalid_run_id_returns_400(feedback_server) -> None:
    """run_id not matching regex → HTTP 400."""
    url, _ = feedback_server
    payload = {**_VALID_PAYLOAD, "run_id": "not-a-valid-run-id"}
    status, body = _post(f"{url}/feedback", payload)

    assert status == 400
    assert body["status"] == "error"


def test_invalid_section_returns_400(feedback_server) -> None:
    """section not in VALID_SECTIONS → HTTP 400."""
    url, _ = feedback_server
    payload = {**_VALID_PAYLOAD, "section": "nonexistent_section"}
    status, body = _post(f"{url}/feedback", payload)

    assert status == 400
    assert body["status"] == "error"


def test_invalid_label_returns_400(feedback_server) -> None:
    """label not in VALID_LABELS → HTTP 400."""
    url, _ = feedback_server
    payload = {**_VALID_PAYLOAD, "label": "wrong_label"}
    status, body = _post(f"{url}/feedback", payload)

    assert status == 400
    assert body["status"] == "error"


def test_body_too_large_returns_413(feedback_server) -> None:
    """Body exceeding MAX_BODY_BYTES → HTTP 413 before reading content."""
    url, _ = feedback_server
    oversized_body = b"x" * (MAX_BODY_BYTES + 1)
    req = urllib.request.Request(
        f"{url}/feedback",
        data=oversized_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req):
            pytest.fail("Expected HTTPError 413")
    except urllib.error.HTTPError as exc:
        assert exc.code == 413


def test_comment_truncated_silently(feedback_server) -> None:
    """A 2000-char comment is accepted and stored as exactly 1000 chars."""
    url, feedback_dir = feedback_server
    long_comment = "A" * 2000
    payload = {**_VALID_PAYLOAD, "comment": long_comment}
    status, body = _post(f"{url}/feedback", payload)

    assert status == 200

    # Read stored file and verify truncation
    feedback_files = list(feedback_dir.glob("*.json"))
    assert len(feedback_files) == 1
    stored = json.loads(feedback_files[0].read_text())
    assert len(stored["comment"]) == 1000


def test_operator_default_and_cap(feedback_server) -> None:
    """operator defaults to 'anonymous' when absent; long operators are capped at 100 chars."""
    url, feedback_dir = feedback_server

    # Case 1: operator absent → stored as "anonymous"
    payload_no_op = {k: v for k, v in _VALID_PAYLOAD.items() if k != "operator"}
    status, _ = _post(f"{url}/feedback", payload_no_op)
    assert status == 200
    files = sorted(feedback_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    stored = json.loads(files[-1].read_text())
    assert stored["operator"] == "anonymous"

    # Case 2: operator > 100 chars → stored truncated to 100
    long_operator = "O" * 200
    payload_long_op = {**_VALID_PAYLOAD, "operator": long_operator}
    status, _ = _post(f"{url}/feedback", payload_long_op)
    assert status == 200
    files = sorted(feedback_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    stored = json.loads(files[-1].read_text())
    assert len(stored["operator"]) == 100


def test_audit_log_excludes_comment_and_feedback_id(
    feedback_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit log must emit only run_id, section, label — not comment or feedback_id."""
    url, _ = feedback_server

    logged: list[dict] = []

    import wbsb.feedback.server as server_mod

    original_event = server_mod.log_security_event

    def capturing_event(event: str, **kwargs: object) -> None:
        if event == "feedback_received":
            logged.append({"event": event, **kwargs})
        original_event(event, **kwargs)

    monkeypatch.setattr(server_mod, "log_security_event", capturing_event)

    payload = {**_VALID_PAYLOAD, "comment": "Secret comment that must not be logged."}
    status, _ = _post(f"{url}/feedback", payload)
    assert status == 200

    assert len(logged) == 1, "expected exactly one feedback_received log entry"
    entry = logged[0]
    assert "run_id" in entry
    assert "section" in entry
    assert "label" in entry
    assert "comment" not in entry, "comment must never appear in the audit log"
    assert "feedback_id" not in entry, "feedback_id must not appear in the audit log"


def test_feedback_id_not_derived_from_input(feedback_server) -> None:
    """The output file name must not contain run_id or section values."""
    url, feedback_dir = feedback_server
    payload = {
        **_VALID_PAYLOAD,
        "run_id": "20260310T090000Z_abc123",
        "section": "situation",
    }
    status, body = _post(f"{url}/feedback", payload)

    assert status == 200

    feedback_id = body["feedback_id"]
    # File path must be feedback/{uuid4}.json — no user input in the name
    assert "20260310T090000Z_abc123" not in feedback_id
    assert "situation" not in feedback_id

    # Verify the file on disk has the same safe name
    feedback_files = list(feedback_dir.glob("*.json"))
    assert len(feedback_files) == 1
    assert feedback_files[0].stem == feedback_id


# ---------------------------------------------------------------------------
# I11-5: Auth rejection tests
# ---------------------------------------------------------------------------


def test_post_feedback_missing_signature(feedback_server_prod) -> None:
    """Missing X-WBSB-Signature → HTTP 401."""
    url, _ = feedback_server_prod
    body = json.dumps(_VALID_PAYLOAD).encode()
    headers = make_auth_headers(body)
    del headers["X-WBSB-Signature"]
    status, resp, _ = _post_h(f"{url}/feedback", raw_body=body, extra_headers=headers)
    assert status == 401
    assert resp["status"] == "error"


def test_post_feedback_missing_timestamp(feedback_server_prod) -> None:
    """Missing X-WBSB-Timestamp → HTTP 401."""
    url, _ = feedback_server_prod
    body = json.dumps(_VALID_PAYLOAD).encode()
    headers = make_auth_headers(body)
    del headers["X-WBSB-Timestamp"]
    status, resp, _ = _post_h(f"{url}/feedback", raw_body=body, extra_headers=headers)
    assert status == 401
    assert resp["status"] == "error"


def test_post_feedback_missing_nonce(feedback_server_prod) -> None:
    """Missing X-WBSB-Nonce → HTTP 401."""
    url, _ = feedback_server_prod
    body = json.dumps(_VALID_PAYLOAD).encode()
    headers = make_auth_headers(body)
    del headers["X-WBSB-Nonce"]
    status, resp, _ = _post_h(f"{url}/feedback", raw_body=body, extra_headers=headers)
    assert status == 401
    assert resp["status"] == "error"


def test_post_feedback_malformed_nonce(feedback_server_prod) -> None:
    """X-WBSB-Nonce not UUID4 format → HTTP 401."""
    url, _ = feedback_server_prod
    body = json.dumps(_VALID_PAYLOAD).encode()
    headers = make_auth_headers(body)
    headers["X-WBSB-Nonce"] = "not-a-uuid"
    status, resp, _ = _post_h(f"{url}/feedback", raw_body=body, extra_headers=headers)
    assert status == 401
    assert resp["status"] == "error"


def test_post_feedback_invalid_hmac(feedback_server_prod) -> None:
    """Wrong HMAC signature → HTTP 401."""
    url, _ = feedback_server_prod
    body = json.dumps(_VALID_PAYLOAD).encode()
    headers = make_auth_headers(body, secret="wrong-secret")
    status, resp, _ = _post_h(f"{url}/feedback", raw_body=body, extra_headers=headers)
    assert status == 401
    assert resp["status"] == "error"


def test_post_feedback_expired_timestamp(feedback_server_prod, monkeypatch) -> None:
    """Timestamp >300s ago → HTTP 401."""
    url, _ = feedback_server_prod
    body = json.dumps(_VALID_PAYLOAD).encode()
    # Build headers with a timestamp 600s in the past
    old_ts = str(int(time.time()) - 600)
    signing = f"{old_ts}.{body.decode()}"
    sig = hmac.new(_TEST_SECRET.encode(), signing.encode(), hashlib.sha256).hexdigest()
    headers = {
        "X-WBSB-Timestamp": old_ts,
        "X-WBSB-Signature": sig,
        "X-WBSB-Nonce": str(uuid.uuid4()),
    }
    status, resp, _ = _post_h(f"{url}/feedback", raw_body=body, extra_headers=headers)
    assert status == 401
    assert resp["status"] == "error"


# ---------------------------------------------------------------------------
# I11-5: Replay test
# ---------------------------------------------------------------------------


def test_post_feedback_replay_nonce(feedback_server_prod) -> None:
    """Replayed nonce → HTTP 409 (not 401)."""
    url, _ = feedback_server_prod
    body = json.dumps(_VALID_PAYLOAD).encode()
    headers = make_auth_headers(body)

    # First request: accepted
    status1, _, _ = _post_h(f"{url}/feedback", raw_body=body, extra_headers=headers)
    assert status1 == 200

    # Second request with same nonce: replay
    status2, resp2, _ = _post_h(f"{url}/feedback", raw_body=body, extra_headers=headers)
    assert status2 == 409
    assert resp2["status"] == "error"
    assert resp2["message"] == "Request already processed"


# ---------------------------------------------------------------------------
# I11-5: Rate limit tests
# ---------------------------------------------------------------------------


def test_post_feedback_per_ip_rate_limit(feedback_server, monkeypatch) -> None:
    """Rate limiter returning per_ip_exceeded → HTTP 429 + Retry-After: 60."""
    url, _ = feedback_server
    import wbsb.feedback.server as server_mod

    monkeypatch.setattr(
        server_mod._rate_limiter, "check", lambda ip: RateLimitOutcome.per_ip_exceeded
    )

    status, resp, headers = _post_h(f"{url}/feedback", payload=_VALID_PAYLOAD)
    assert status == 429
    assert resp["status"] == "error"
    assert headers.get("Retry-After") == "60"


def test_post_feedback_global_rate_limit(feedback_server, monkeypatch) -> None:
    """Rate limiter returning global_exceeded → HTTP 503 + Retry-After: 60."""
    url, _ = feedback_server
    import wbsb.feedback.server as server_mod

    monkeypatch.setattr(
        server_mod._rate_limiter, "check", lambda ip: RateLimitOutcome.global_exceeded
    )

    status, resp, headers = _post_h(f"{url}/feedback", payload=_VALID_PAYLOAD)
    assert status == 503
    assert resp["status"] == "error"
    assert headers.get("Retry-After") == "60"


# ---------------------------------------------------------------------------
# I11-5: Error response format tests
# ---------------------------------------------------------------------------


def test_error_response_format(feedback_server) -> None:
    """All error responses must use {"status": "error", "message": "..."} format."""
    url, _ = feedback_server
    status, body = _post(f"{url}/feedback", {**_VALID_PAYLOAD, "run_id": "bad-id"})
    assert status == 400
    assert body["status"] == "error"
    assert isinstance(body["message"], str)
    assert len(body["message"]) > 0


def test_error_response_no_stack_trace(feedback_server, monkeypatch) -> None:
    """Unexpected exceptions must return HTTP 500 with no stack trace in response."""
    url, _ = feedback_server

    def explode(self: object) -> None:
        raise RuntimeError("unexpected internal error")

    monkeypatch.setattr(FeedbackHandler, "_handle_feedback", explode)

    status, resp, _ = _post_h(f"{url}/feedback", payload=_VALID_PAYLOAD)
    assert status == 500
    resp_text = json.dumps(resp)
    assert "traceback" not in resp_text.lower()
    assert "Traceback" not in resp_text
    assert "RuntimeError" not in resp_text
    assert "unexpected internal error" not in resp_text
    assert resp["status"] == "error"


# ---------------------------------------------------------------------------
# I11-5: X-Forwarded-Proto tests
# ---------------------------------------------------------------------------


def test_https_required_rejects_http_proto(feedback_server, monkeypatch) -> None:
    """WBSB_REQUIRE_HTTPS=true + X-Forwarded-Proto: http → HTTP 400."""
    url, _ = feedback_server
    monkeypatch.setenv("WBSB_REQUIRE_HTTPS", "true")

    status, resp, _ = _post_h(
        f"{url}/feedback",
        payload=_VALID_PAYLOAD,
        extra_headers={"X-Forwarded-Proto": "http"},
    )
    assert status == 400
    assert resp["message"] == "HTTPS required"


def test_https_required_allows_https_proto(feedback_server, monkeypatch) -> None:
    """WBSB_REQUIRE_HTTPS=true + X-Forwarded-Proto: https → allowed (passes to next step)."""
    url, _ = feedback_server
    monkeypatch.setenv("WBSB_REQUIRE_HTTPS", "true")

    status, resp, _ = _post_h(
        f"{url}/feedback",
        payload=_VALID_PAYLOAD,
        extra_headers={"X-Forwarded-Proto": "https"},
    )
    assert status == 200


def test_https_required_emits_security_event(feedback_server, monkeypatch) -> None:
    """HTTPS downgrade rejection must emit a log_security_event."""
    url, _ = feedback_server
    monkeypatch.setenv("WBSB_REQUIRE_HTTPS", "true")

    logged: list[dict] = []

    import wbsb.feedback.server as server_mod

    original = server_mod.log_security_event

    def capturing(event: str, **kwargs: object) -> None:
        logged.append({"event": event, **kwargs})
        original(event, **kwargs)

    monkeypatch.setattr(server_mod, "log_security_event", capturing)

    _post_h(
        f"{url}/feedback",
        payload=_VALID_PAYLOAD,
        extra_headers={"X-Forwarded-Proto": "http"},
    )

    assert any(
        e.get("reason") == "https_required" for e in logged
    ), "expected a security event with reason='https_required'"


def test_https_not_required_allows_http_proto(feedback_server, monkeypatch) -> None:
    """WBSB_REQUIRE_HTTPS not set → X-Forwarded-Proto: http is allowed."""
    url, _ = feedback_server
    monkeypatch.delenv("WBSB_REQUIRE_HTTPS", raising=False)

    status, resp, _ = _post_h(
        f"{url}/feedback",
        payload=_VALID_PAYLOAD,
        extra_headers={"X-Forwarded-Proto": "http"},
    )
    assert status == 200


# ---------------------------------------------------------------------------
# I11-5: Dev bypass test
# ---------------------------------------------------------------------------


def test_dev_bypass_skips_hmac(feedback_server) -> None:
    """WBSB_ENV=development → valid request accepted without auth headers."""
    url, _ = feedback_server  # already in dev mode
    status, resp, _ = _post_h(f"{url}/feedback", payload=_VALID_PAYLOAD)
    assert status == 200
    assert resp["status"] == "ok"


# ---------------------------------------------------------------------------
# I11-5: Startup check tests
# ---------------------------------------------------------------------------


def test_startup_fails_without_secret_in_prod(monkeypatch) -> None:
    """feedback_serve must exit(1) when WBSB_FEEDBACK_SECRET unset in production."""
    monkeypatch.delenv("WBSB_FEEDBACK_SECRET", raising=False)
    monkeypatch.setenv("WBSB_ENV", "production")

    from typer.testing import CliRunner

    from wbsb.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["feedback", "serve"])
    assert result.exit_code == 1
    assert "WBSB_FEEDBACK_SECRET" in result.output


def test_startup_ok_in_dev_without_secret(monkeypatch) -> None:
    """feedback_serve must NOT exit in dev mode even when secret is absent."""
    monkeypatch.delenv("WBSB_FEEDBACK_SECRET", raising=False)
    monkeypatch.setenv("WBSB_ENV", "development")

    with patch("wbsb.feedback.server.run_server"):
        from typer.testing import CliRunner

        from wbsb.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["feedback", "serve"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# I11-5: Happy path regression (production mode with valid auth)
# ---------------------------------------------------------------------------


def test_valid_authenticated_request_returns_200(feedback_server_prod) -> None:
    """Valid HMAC-authenticated request in production mode → HTTP 200."""
    url, _ = feedback_server_prod
    body = json.dumps(_VALID_PAYLOAD).encode()
    headers = make_auth_headers(body)
    status, resp, _ = _post_h(f"{url}/feedback", raw_body=body, extra_headers=headers)
    assert status == 200
    assert resp["status"] == "ok"
    assert "feedback_id" in resp
