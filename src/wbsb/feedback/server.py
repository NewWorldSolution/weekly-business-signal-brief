"""Feedback webhook server for WBSB.

Accepts POST /feedback from Teams/Slack button callbacks and persists the
feedback via the I7 feedback store.

Security model
--------------
No authentication for MVP.  This server MUST be run behind a firewall or VPN
and MUST NOT be exposed to the public internet without adding an auth layer
(e.g. a shared secret header or API key).  See docs/iterations/i9/tasks.md
for the planned auth story in a future iteration.

Safe-write guarantees
---------------------
- Output file path is always ``feedback/{uuid4}.json`` — never derived from
  user-controlled input.
- Comment content is never written to logs.
- run_id, section, and label are validated against strict allowlists before
  any disk write occurs.
- Request bodies exceeding MAX_BODY_BYTES are rejected with HTTP 413 before
  reading any content.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from wbsb.feedback.models import VALID_LABELS, VALID_SECTIONS, FeedbackEntry
from wbsb.feedback.store import RUN_ID_PATTERN, save_feedback
from wbsb.observability.logging import get_logger

MAX_BODY_BYTES: int = 4096
MAX_COMMENT_CHARS: int = 1000
MAX_OPERATOR_CHARS: int = 100

_log = get_logger()


class FeedbackHandler(BaseHTTPRequestHandler):
    """Handle POST /feedback requests.

    Response codes:
        200 — valid feedback stored: ``{"status": "ok", "feedback_id": "..."}``
        400 — validation error:      ``{"status": "error", "message": "..."}``
        413 — body too large:        ``{"status": "error", "message": "..."}``
        404 — unknown path:          ``{"status": "error", "message": "..."}``
    """

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/feedback":
            self._send_json(404, {"status": "error", "message": "Not found"})
            return

        # ── Body-size guard (must check before reading) ──────────────────────
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            content_length = 0

        if content_length > MAX_BODY_BYTES:
            self._send_json(413, {"status": "error", "message": "Request body too large"})
            return

        # ── Parse JSON body ───────────────────────────────────────────────────
        try:
            raw = self.rfile.read(content_length)
            data: dict = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            self._send_json(400, {"status": "error", "message": f"Invalid JSON: {exc}"})
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
            self._send_json(
                400, {"status": "error", "message": f"Invalid run_id: {run_id!r}"}
            )
            return

        if section not in VALID_SECTIONS:
            self._send_json(
                400, {"status": "error", "message": f"Invalid section: {section!r}"}
            )
            return

        if label not in VALID_LABELS:
            self._send_json(
                400, {"status": "error", "message": f"Invalid label: {label!r}"}
            )
            return

        # ── Persist — file path is always feedback/{uuid4}.json ──────────────
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

        # ── Audit log — only run_id, section, label per frozen contract ─────────
        # feedback_id and comment are intentionally excluded.
        _log.info(
            "feedback_received",
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


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the feedback webhook server (blocking)."""
    server = HTTPServer((host, port), FeedbackHandler)
    server.serve_forever()
