"""Tests for wbsb.feedback.store."""
from __future__ import annotations

import pytest

from wbsb.feedback import store as feedback_store
from wbsb.feedback.models import FeedbackEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_RUN_ID = "20260312T120000Z_3a1b2c"


def _entry(**kwargs) -> FeedbackEntry:
    defaults = {
        "feedback_id": "",
        "run_id": VALID_RUN_ID,
        "section": "situation",
        "label": "expected",
        "comment": "looks good",
        "submitted_at": "2026-03-12T12:00:00Z",
    }
    defaults.update(kwargs)
    return FeedbackEntry(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_feedback_valid(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)
    entry = _entry(feedback_id="abc123")

    path = feedback_store.save_feedback(entry)

    assert path.exists()
    assert path == tmp_path / "abc123.json"
    loaded = FeedbackEntry.model_validate_json(path.read_text())
    assert loaded.run_id == VALID_RUN_ID
    assert loaded.section == "situation"
    assert loaded.label == "expected"
    assert loaded.comment == "looks good"


def test_save_feedback_invalid_run_id(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)
    entry = _entry(run_id="bad-run-id")

    with pytest.raises(ValueError, match="run_id"):
        feedback_store.save_feedback(entry)


def test_save_feedback_invalid_section(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)
    entry = _entry(section="not_a_section")

    with pytest.raises(ValueError, match="section"):
        feedback_store.save_feedback(entry)


def test_save_feedback_invalid_label(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)
    entry = _entry(label="not_a_label")

    with pytest.raises(ValueError, match="label"):
        feedback_store.save_feedback(entry)


def test_save_feedback_comment_truncated(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)
    entry = _entry(feedback_id="trunc1", comment="x" * 1500)

    path = feedback_store.save_feedback(entry)

    loaded = FeedbackEntry.model_validate_json(path.read_text())
    assert len(loaded.comment) == 1000


def test_list_feedback_sorted(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)

    feedback_store.save_feedback(_entry(feedback_id="e1", submitted_at="2026-03-10T10:00:00Z"))
    feedback_store.save_feedback(_entry(feedback_id="e2", submitted_at="2026-03-12T10:00:00Z"))
    feedback_store.save_feedback(_entry(feedback_id="e3", submitted_at="2026-03-11T10:00:00Z"))

    entries = feedback_store.list_feedback()

    assert len(entries) == 3
    assert entries[0].submitted_at == "2026-03-12T10:00:00Z"
    assert entries[1].submitted_at == "2026-03-11T10:00:00Z"
    assert entries[2].submitted_at == "2026-03-10T10:00:00Z"


def test_summarize_feedback_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)

    feedback_store.save_feedback(_entry(feedback_id="s1", label="expected"))
    feedback_store.save_feedback(_entry(feedback_id="s2", label="expected"))
    feedback_store.save_feedback(_entry(feedback_id="s3", label="unexpected"))

    summary = feedback_store.summarize_feedback()

    assert summary["total"] == 3
    assert summary["by_label"]["expected"] == 2
    assert summary["by_label"]["unexpected"] == 1
    assert summary["by_label"]["incorrect"] == 0
    # All keys present
    assert set(summary["by_label"].keys()) == {"expected", "unexpected", "incorrect"}
    assert set(summary["by_section"].keys()) == {
        "situation", "key_story", "group_narratives", "watch_signals"
    }


def test_export_feedback_by_run_id(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)

    run_a = "20260312T120000Z_aaaaaa"
    run_b = "20260312T120000Z_bbbbbb"

    feedback_store.save_feedback(_entry(feedback_id="x1", run_id=run_a))
    feedback_store.save_feedback(_entry(feedback_id="x2", run_id=run_a))
    feedback_store.save_feedback(_entry(feedback_id="x3", run_id=run_b))

    result = feedback_store.export_feedback(run_a)

    assert len(result) == 2
    assert all(e.run_id == run_a for e in result)
