"""Feedback storage functions for WBSB operator feedback."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from wbsb.feedback.models import VALID_LABELS, VALID_SECTIONS, FeedbackEntry
from wbsb.observability.logging import get_logger

FEEDBACK_DIR = Path("feedback")

RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z_[a-f0-9]{6}$")

_log = get_logger()


def save_feedback(entry: FeedbackEntry) -> Path:
    """
    Validate and persist a FeedbackEntry as JSON.

    Validation (raises ValueError on failure):
        - run_id must match RUN_ID_PATTERN
        - section must be in VALID_SECTIONS
        - label must be in VALID_LABELS

    Truncation (silent, no exception):
        - comment is truncated to 1000 characters

    Auto-generation:
        - feedback_id is set to uuid.uuid4().hex if entry.feedback_id is falsy

    Returns:
        Path to the written file: FEEDBACK_DIR / f"{entry.feedback_id}.json"
    """
    if not RUN_ID_PATTERN.match(entry.run_id):
        raise ValueError(
            f"Invalid run_id {entry.run_id!r}. "
            "Expected format: YYYYMMDDTHHMMSSZ_xxxxxx (e.g. 20260312T120000Z_3a1b2c)"
        )
    if entry.section not in VALID_SECTIONS:
        raise ValueError(
            f"Invalid section {entry.section!r}. Must be one of: {sorted(VALID_SECTIONS)}"
        )
    if entry.label not in VALID_LABELS:
        raise ValueError(
            f"Invalid label {entry.label!r}. Must be one of: {sorted(VALID_LABELS)}"
        )

    entry = entry.model_copy(update={"comment": entry.comment[:1000]})

    if not entry.feedback_id:
        entry = entry.model_copy(update={"feedback_id": uuid.uuid4().hex})

    FEEDBACK_DIR.mkdir(exist_ok=True)
    path = FEEDBACK_DIR / f"{entry.feedback_id}.json"
    path.write_text(entry.model_dump_json(indent=2))
    return path


def _load_all_entries() -> list[FeedbackEntry]:
    """Load all FeedbackEntry objects from FEEDBACK_DIR. Skips unparseable files."""
    if not FEEDBACK_DIR.exists():
        return []
    entries: list[FeedbackEntry] = []
    for path in FEEDBACK_DIR.glob("*.json"):
        try:
            entries.append(FeedbackEntry.model_validate_json(path.read_text()))
        except Exception as exc:
            _log.error("feedback.store.parse_error", path=str(path), error=str(exc))
    return entries


def list_feedback(limit: int = 50) -> list[FeedbackEntry]:
    """
    Load and return all FeedbackEntry objects from FEEDBACK_DIR,
    sorted by submitted_at descending (newest first).
    Returns up to `limit` entries.
    """
    entries = sorted(_load_all_entries(), key=lambda e: e.submitted_at, reverse=True)
    return entries[:limit]


def summarize_feedback() -> dict:
    """
    Return aggregated counts from all feedback entries.

    Returns:
        {
            "total": int,
            "by_label": {"expected": int, "unexpected": int, "incorrect": int},
            "by_section": {
                "situation": int,
                "key_story": int,
                "group_narratives": int,
                "watch_signals": int,
            },
        }
    """
    entries = _load_all_entries()
    by_label = {label: 0 for label in sorted(VALID_LABELS)}
    by_section = {section: 0 for section in sorted(VALID_SECTIONS)}
    for e in entries:
        if e.label in by_label:
            by_label[e.label] += 1
        if e.section in by_section:
            by_section[e.section] += 1
    return {"total": len(entries), "by_label": by_label, "by_section": by_section}


def export_feedback(run_id: str) -> list[FeedbackEntry]:
    """
    Return all FeedbackEntry objects for a specific run_id.
    Sorted by submitted_at ascending (chronological order).
    """
    entries = [e for e in _load_all_entries() if e.run_id == run_id]
    return sorted(entries, key=lambda e: e.submitted_at)
