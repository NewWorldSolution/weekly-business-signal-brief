"""History store — run index persistence and dataset-scoped metric queries.

This module provides the storage foundation for Iteration 6 historical memory.
It is the sole interface for writing run records to the index and for reading
prior metric values. All queries are scoped to a dataset_key to prevent
contamination across different business datasets.

Architecture constraints:
    - No trend computation here — this module is storage only.
    - No pipeline wiring here — pipeline integration is I6-3's responsibility.
    - No LLM dependency.
    - All writes are atomic (temp file + os.replace).
    - Missing files are skipped with a warning, never raised.
    - Duplicate run_id and missing findings_path raise loudly.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import TypedDict

from wbsb.domain.models import AuditEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RunRecord
# ---------------------------------------------------------------------------


class RunRecord(TypedDict):
    """A single entry in the history index."""

    run_id: str          # e.g. "20260309T094756Z_4c43f0"
    dataset_key: str     # e.g. "weekly_data" — primary isolation key
    input_file: str      # full path, for traceability
    week_start: str      # ISO date "2026-03-03"
    week_end: str        # ISO date "2026-03-09"
    signal_count: int
    findings_path: str   # full path to findings.json
    registered_at: str   # ISO datetime of registration


# ---------------------------------------------------------------------------
# derive_dataset_key
# ---------------------------------------------------------------------------

# Matches trailing date segments: _YYYY-MM-DD, -YYYY-MM-DD, _YYYYMMDD, -YYYYMMDD
_DATE_SUFFIX_RE = re.compile(r"[_\-]\d{4}-\d{2}-\d{2}$|[_\-]\d{8}$")


def derive_dataset_key(input_file: str | Path) -> str:
    """Return a stable dataset key derived from the input filename.

    Rules applied in order:
    1. Take the filename only — ignore directory components.
    2. Strip the file extension.
    3. Remove a trailing date segment matching _YYYY-MM-DD, -YYYY-MM-DD,
       _YYYYMMDD, or -YYYYMMDD.
    4. Strip any remaining trailing underscores or dashes.
    5. Return as lowercase string.

    This function is pure — no I/O, no side effects.

    Examples:
        weekly_data_2026-03-03.csv  →  weekly_data
        report_20260303.xlsx        →  report
        dataset_07_extreme_ad_spend.csv  →  dataset_07_extreme_ad_spend
    """
    stem = Path(input_file).stem
    stem = _DATE_SUFFIX_RE.sub("", stem)
    stem = stem.rstrip("_-")
    return stem.lower()


# ---------------------------------------------------------------------------
# register_run
# ---------------------------------------------------------------------------


def register_run(run: RunRecord, index_path: Path) -> None:
    """Append a completed pipeline run to the history index.

    The index is a JSON array stored at index_path. If the file does not
    exist it is created. Writes are atomic: the new content is written to a
    temp file in the same directory, then renamed over the target.

    An AuditEvent is logged after a successful write.

    Args:
        run: The run record to append.
        index_path: Path to the JSON index file (e.g. runs/index.json).

    Raises:
        FileNotFoundError: If run["findings_path"] does not exist.
        ValueError: If run["run_id"] is already present in the index.
    """
    findings_path = Path(run["findings_path"])
    if not findings_path.exists():
        raise FileNotFoundError(
            f"findings_path does not exist and cannot be registered: {findings_path}"
        )

    # Load existing index or start fresh
    if index_path.exists():
        entries: list[dict] = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        entries = []

    # Reject duplicates
    existing_ids = {entry["run_id"] for entry in entries}
    if run["run_id"] in existing_ids:
        raise ValueError(
            f"run_id already exists in history index: {run['run_id']!r}"
        )

    entries.append(dict(run))

    # Atomic write: temp file in same directory → os.replace
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=index_path.parent, suffix=".tmp", text=True
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        os.replace(tmp_path, index_path)
        tmp_path = None  # Successfully replaced — do not clean up
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError as exc:
                logger.warning(
                    "history.register_run.cleanup_failed: could not remove temp file %s: %s",
                    tmp_path,
                    exc,
                )

    # Emit audit event via logging
    audit_event = AuditEvent(
        event_type="history_registered",
        message=f"Run {run['run_id']!r} registered in history index",
        extra={"dataset_key": run["dataset_key"], "index_path": str(index_path)},
    )
    logger.info(
        "history.registered event_type=%r message=%s dataset_key=%r index_path=%s",
        audit_event.event_type,
        audit_event.message,
        run["dataset_key"],
        str(index_path),
    )


# ---------------------------------------------------------------------------
# HistoryReader
# ---------------------------------------------------------------------------


class HistoryReader:
    """Read-only access to the history index, scoped to a single dataset.

    All queries filter by dataset_key before any other operation.
    Runs from other datasets are never visible to this reader.
    """

    def __init__(self, index_path: Path, dataset_key: str) -> None:
        """Initialise the reader.

        Args:
            index_path: Path to the JSON index file. Need not exist yet.
            dataset_key: Only runs with this key will be returned.
        """
        self._index_path = index_path
        self._dataset_key = dataset_key

    def get_metric_history(
        self,
        metric_id: str,
        n_weeks: int = 4,
        before_week_start: str | None = None,
    ) -> list[tuple[str, float]]:
        """Return up to n_weeks of prior (week_start, metric_value) pairs.

        Results are ordered chronologically (oldest first).

        Args:
            metric_id: The metric ID to look up (e.g. "cac_paid").
            n_weeks: Maximum number of prior weeks to return.
            before_week_start: If given, only include runs with
                week_start strictly less than this ISO date string.

        Returns:
            List of (week_start, value) tuples ordered oldest-first.
            Empty list when no history exists or no matching entries found.
        """
        if not self._index_path.exists():
            return []

        entries: list[dict] = json.loads(
            self._index_path.read_text(encoding="utf-8")
        )

        # Dataset isolation — always the first filter
        entries = [e for e in entries if e["dataset_key"] == self._dataset_key]

        # Apply before_week_start filter
        if before_week_start is not None:
            entries = [e for e in entries if e["week_start"] < before_week_start]

        # Take the most recent n_weeks entries
        entries.sort(key=lambda e: e["week_start"], reverse=True)
        entries = entries[:n_weeks]

        # Resolve metric values from findings files
        results: list[tuple[str, float]] = []
        for entry in entries:
            findings_path = Path(entry["findings_path"])
            if not findings_path.exists():
                logger.warning(
                    "history.reader.missing_findings: run_id=%r findings_path=%s",
                    entry["run_id"],
                    str(findings_path),
                )
                continue

            findings_data = json.loads(findings_path.read_text(encoding="utf-8"))
            value: float | None = None
            for metric in findings_data.get("metrics", []):
                if metric.get("id") == metric_id:
                    raw = metric.get("current")
                    if raw is not None:
                        value = float(raw)
                    break

            if value is None:
                logger.warning(
                    "history.reader.missing_metric: run_id=%r metric_id=%r",
                    entry["run_id"],
                    metric_id,
                )
                continue

            results.append((entry["week_start"], value))

        # Return chronologically (oldest first)
        results.sort(key=lambda x: x[0])
        return results
