"""Pydantic models for the WBSB operator feedback system."""
from __future__ import annotations

from pydantic import BaseModel

VALID_SECTIONS: frozenset[str] = frozenset(
    {"situation", "key_story", "group_narratives", "watch_signals"}
)

VALID_LABELS: frozenset[str] = frozenset({"expected", "unexpected", "incorrect"})


class FeedbackEntry(BaseModel):
    """A single piece of operator feedback on a report section."""

    schema_version: str = "1.0"
    feedback_id: str
    run_id: str
    section: str
    label: str
    comment: str
    operator: str = "anonymous"
    submitted_at: str
