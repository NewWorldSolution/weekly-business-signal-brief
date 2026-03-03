from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from wbsb.domain.models import RunConfig
from wbsb.findings.build import build_findings


def test_missing_week_raises_value_error():
    week_a = date(2024, 1, 1)
    week_b = date(2024, 1, 8)
    missing_week = date(2024, 1, 15)

    df = pd.DataFrame({
        "week_start_date": pd.to_datetime([week_a, week_b]),
    })

    with pytest.raises(ValueError, match="2024-01-15"):
        build_findings(
            df=df,
            week_start=missing_week,
            prev_week_start=week_a,
            run_id="test-run-001",
            input_path=Path("test.csv"),
            input_hash="abc123",
            config_hash="def456",
            config_path=Path("config/rules.yaml"),
            raw_config={},
            run_config=RunConfig(),
            audit_events=[],
        )
