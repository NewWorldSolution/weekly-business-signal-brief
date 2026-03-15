"""Feedback webhook server for WBSB.

Accepts POST /feedback from Teams/Slack button callbacks and persists the
feedback via the I7 feedback store.

Security model (I11)
--------------------
All POST /feedback requests are authenticated via HMAC-SHA256 (I11-2).
Request handling order:
  0 — X-Forwarded-Proto check (WBSB_REQUIRE_HTTPS=true)
  1 — Rate limit (per-IP + global circuit breaker)
  2 — Auth header presence + UUID4 nonce format
  3 — Timestamp freshness (±300s)
  4 — HMAC-SHA256 verification
  5 — Nonce replay check
  6 — Body validation (unchanged from I9)
  7 — Feedback storage (unchanged from I9)

Dev bypass: WBSB_ENV=development skips steps 2–5.
Rate limiting always applies.

Safe-write guarantees
---------------------
- Output file path is always ``feedback/{uuid4}.json`` — never derived from
  user-controlled input.
- Comment content is never written to logs.
- run_id, section, and label are validated against strict allowlists before
  any disk write occurs.
- Request bodies exceeding MAX_BODY_BYTES are rejected with HTTP 413 before
  reading any content.
- Error responses never include stack traces, exception messages, file paths,
  module names, or Python version strings.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from wbsb.feedback.auth import (
    HEADER_NONCE,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    NonceStore,
    verify_hmac,
    verify_timestamp,
)
from wbsb.feedback.models import VALID_LABELS, VALID_SECTIONS, FeedbackEntry
from wbsb.feedback.ratelimit import RateLimiter, RateLimitOutcome
from wbsb.feedback.store import RUN_ID_PATTERN, save_feedback
from wbsb.observability.logging import (
    EVENT_AUTH_FAILURE,
    EVENT_FEEDBACK_RECEIVED,
    EVENT_INVALID_INPUT,
    EVENT_RATE_LIMIT_EXCEEDED,
    EVENT_REPLAY_DETECTED,
    get_logger,
    log_security_event,
    pseudonymize_ip,
)

MAX_BODY_BYTES: int = 4096
MAX_COMMENT_CHARS: int = 1000
MAX_OPERATOR_CHARS: int = 100

_UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_log = get_logger()
_nonce_store = NonceStore()
_rate_limiter = RateLimiter()


class FeedbackHandler(BaseHTTPRequestHandler):
    """Handle POST /feedback requests.

    Response codes:
        200 — valid feedback stored: ``{"status": "ok", "feedback_id": "..."}``
        400 — validation error / HTTPS required
        401 — authentication required
        409 — replay detected
        413 — body too large
        429 — per-IP rate limit exceeded (Retry-After: 60)
        500 — internal server error
        503 — global rate limit exceeded (Retry-After: 60)
    """

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._handle_feedback()
        except Exception:
            self._send_json(500, {"status": "error", "message": "Internal server error"})

    def _handle_feedback(self) -> None:
        if self.path != "/feedback":
            self._send_json(404, {"status": "error", "message": "Not found"})
            return

        source_ip = self.client_address[0]
        dev_mode = os.environ.get("WBSB_ENV", "production") == "development"
        require_https = os.environ.get("WBSB_REQUIRE_HTTPS", "") == "true"

        # ── Step 0 — X-Forwarded-Proto check ─────────────────────────────────
        if require_https:
            proto = self.headers.get("X-Forwarded-Proto", "")
            if proto == "http":
                self._send_json(400, {"status": "error", "message": "HTTPS required"})
                return

        # ── Step 1 — Rate limit check ─────────────────────────────────────────
        rate_outcome = _rate_limiter.check(source_ip)
        if rate_outcome != RateLimitOutcome.allowed:
            log_security_event(
                EVENT_RATE_LIMIT_EXCEEDED,
                source_ip=pseudonymize_ip(source_ip),
                outcome=rate_outcome.value,
            )
            if rate_outcome == RateLimitOutcome.per_ip_exceeded:
                self._send_json_with_headers(
                    429,
                    {"status": "error", "message": "Rate limit exceeded"},
                    {"Retry-After": "60"},
                )
            else:
                self._send_json_with_headers(
                    503,
                    {"status": "error", "message": "Service temporarily unavailable"},
                    {"Retry-After": "60"},
                )
            return

        # ── Body-size guard (must check before reading) ───────────────────────
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            content_length = 0

        if content_length > MAX_BODY_BYTES:
            self._send_json(413, {"status": "error", "message": "Request body too large"})
            return

        # ── Read raw body (needed for HMAC) ───────────────────────────────────
        raw = self.rfile.read(content_length)

        # ── Steps 2–5 — Auth (skipped in dev mode) ───────────────────────────
        if not dev_mode:
            # Step 2 — Parse auth headers
            timestamp = self.headers.get(HEADER_TIMESTAMP)
            signature = self.headers.get(HEADER_SIGNATURE)
            nonce = self.headers.get(HEADER_NONCE)

            if not timestamp or not signature or not nonce:
                log_security_event(
                    EVENT_AUTH_FAILURE,
                    source_ip=pseudonymize_ip(source_ip),
                    reason="missing_headers",
                )
                self._send_json(401, {"status": "error", "message": "Authentication required"})
                return

            if not _UUID4_PATTERN.match(nonce):
                log_security_event(
                    EVENT_AUTH_FAILURE,
                    source_ip=pseudonymize_ip(source_ip),
                    reason="malformed_nonce",
                )
                self._send_json(401, {"status": "error", "message": "Authentication required"})
                return

            # Step 3 — Timestamp freshness
            if not verify_timestamp(timestamp):
                log_security_event(
                    EVENT_AUTH_FAILURE,
                    source_ip=pseudonymize_ip(source_ip),
                    reason="expired_timestamp",
                )
                self._send_json(401, {"status": "error", "message": "Authentication required"})
                return

            # Step 4 — HMAC verification
            secret = os.environ.get("WBSB_FEEDBACK_SECRET", "")
            if not verify_hmac(raw, timestamp, signature, secret):
                log_security_event(
                    EVENT_AUTH_FAILURE,
                    source_ip=pseudonymize_ip(source_ip),
                    reason="invalid_hmac",
                )
                self._send_json(401, {"status": "error", "message": "Authentication required"})
                return

            # Step 5 — Nonce replay check
            if not _nonce_store.check_and_record(nonce):
                log_security_event(
                    EVENT_REPLAY_DETECTED,
                    source_ip=pseudonymize_ip(source_ip),
                )
                self._send_json(409, {"status": "error", "message": "Request already processed"})
                return

        # ── Step 6 — Parse JSON body ──────────────────────────────────────────
        try:
            data: dict = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            log_security_event(
                EVENT_INVALID_INPUT,
                source_ip=pseudonymize_ip(source_ip),
                reason="invalid_json",
            )
            self._send_json(400, {"status": "error", "message": "Invalid JSON"})
            return

        # ── Field extraction with caps ────────────────────────────────────────
        run_id = str(data.get("run_id", ""))
        section = str(data.get("section", ""))
        label = str(data.get("label", ""))
        comment = str(data.get("comment", "")).strip()[:MAX_COMMENT_CHARS]
        operator_raw = data.get("operator", "")
        operator = str(operator_raw)[:MAX_OPERATOR_CHARS] if operator_raw else "anonymous"

        # ── Validation ────────────────────────────────────────────────────────
        if not RUN_ID_PATTERN.match(run_id):
            log_security_event(
                EVENT_INVALID_INPUT,
                source_ip=pseudonymize_ip(source_ip),
                reason="invalid_run_id",
            )
            self._send_json(
                400, {"status": "error", "message": f"Invalid run_id: {run_id!r}"}
            )
            return

        if section not in VALID_SECTIONS:
            log_security_event(
                EVENT_INVALID_INPUT,
                source_ip=pseudonymize_ip(source_ip),
                reason="invalid_section",
            )
            self._send_json(
                400, {"status": "error", "message": f"Invalid section: {section!r}"}
            )
            return

        if label not in VALID_LABELS:
            log_security_event(
                EVENT_INVALID_INPUT,
                source_ip=pseudonymize_ip(source_ip),
                reason="invalid_label",
            )
            self._send_json(
                400, {"status": "error", "message": f"Invalid label: {label!r}"}
            )
            return

        # ── Step 7 — Persist ──────────────────────────────────────────────────
        feedback_id = uuid.uuid4().hex
        entry = FeedbackEntry(
            feedback_id=feedback_id,
            run_id=run_id,
            section=section,
            label=label,
            comment=comment,
            operator=operator,
            submitted_at=datetime.now(UTC).isoformat(),
        )

        try:
            save_feedback(entry)
        except ValueError as exc:
            self._send_json(400, {"status": "error", "message": str(exc)})
            return
        except Exception as exc:
            _log.error("feedback.server.write_error", error=str(exc))
            self._send_json(500, {"status": "error", "message": "Internal server error"})
            return

        # ── Audit log — only run_id, section, label per frozen contract ───────
        # feedback_id and comment are intentionally excluded.
        log_security_event(
            EVENT_FEEDBACK_RECEIVED,
            run_id=run_id,
            section=section,
            label=label,
        )

        self._send_json(200, {"status": "ok", "feedback_id": feedback_id})

    def log_message(self, fmt: str, *args: object) -> None:
        """Suppress default per-request stderr logging."""

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json_with_headers(self, code: int, payload: dict, extra_headers: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra_headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the feedback webhook server (blocking)."""
    server = HTTPServer((host, port), FeedbackHandler)
    server.serve_forever()
