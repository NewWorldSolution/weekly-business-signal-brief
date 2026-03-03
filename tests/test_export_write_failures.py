from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from wbsb.domain.models import Findings, Periods, RunMeta
from wbsb.export.write import write_artifacts


def _make_findings() -> Findings:
    return Findings(
        run=RunMeta(
            run_id="test_run",
            generated_at=datetime.now(UTC),
            input_file="test.csv",
            input_sha256="abc123",
            config_sha256="def456",
        ),
        periods=Periods(
            current_week_start=date(2024, 1, 8),
            current_week_end=date(2024, 1, 14),
            previous_week_start=date(2024, 1, 1),
            previous_week_end=date(2024, 1, 7),
        ),
        metrics=[],
        signals=[],
        audit=[],
    )


def test_write_artifacts_raises_on_write_failure(tmp_path, monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("simulated disk full")

    monkeypatch.setattr(Path, "write_text", _raise)

    with pytest.raises(OSError, match="simulated disk full"):
        write_artifacts(
            run_dir=tmp_path,
            findings=_make_findings(),
            brief_md="# Test",
            elapsed_seconds=1.0,
            run_id="test_run",
            input_path=Path("test.csv"),
            input_hash="abc123",
            config_hash="def456",
        )
