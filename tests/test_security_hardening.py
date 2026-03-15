from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wbsb.feedback import store as feedback_store
from wbsb.feedback.models import FeedbackEntry


def _entry(**kwargs) -> FeedbackEntry:
    defaults = {
        "feedback_id": "secure1",
        "run_id": "20260312T120000Z_3a1b2c",
        "section": "situation",
        "label": "expected",
        "comment": "looks good",
        "submitted_at": "2026-03-12T12:00:00Z",
    }
    defaults.update(kwargs)
    return FeedbackEntry(**defaults)


def test_feedback_artifact_permissions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path / "feedback")

    path = feedback_store.save_feedback(_entry())

    assert (path.stat().st_mode & 0o777) == 0o600


def test_feedback_dir_permissions(tmp_path: Path, monkeypatch) -> None:
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", feedback_dir)

    feedback_store.save_feedback(_entry(feedback_id="secure2"))

    assert (feedback_dir.stat().st_mode & 0o777) == 0o700
