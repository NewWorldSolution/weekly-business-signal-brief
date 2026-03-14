"""Tests for wbsb.feedback.server (POST /feedback webhook)."""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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


# ---------------------------------------------------------------------------
# Server fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def feedback_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Start a real HTTPServer in a daemon thread; patch FEEDBACK_DIR to tmp_path."""
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setattr("wbsb.feedback.store.FEEDBACK_DIR", feedback_dir)

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


# ---------------------------------------------------------------------------
# Required tests
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
