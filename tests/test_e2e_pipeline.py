import json
from pathlib import Path

from wbsb.pipeline import execute


def test_e2e_pipeline_produces_artifacts(tmp_path):
    exit_code = execute(
        input_path=Path("examples/sample_weekly.csv"),
        output_dir=tmp_path,
        llm_mode="off",
        config_path=Path("config/rules.yaml"),
        target_week=None,
    )

    assert exit_code == 0

    run_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1

    run_dir = run_dirs[0]
    assert (run_dir / "findings.json").exists()
    assert (run_dir / "brief.md").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "logs.jsonl").exists()

    findings = json.loads((run_dir / "findings.json").read_text())
    assert findings["schema_version"] == "1.1"
    assert isinstance(findings["metrics"], list) and len(findings["metrics"]) > 0
    assert "signals" in findings

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert "signals_warn_count" in manifest
    assert "signals_info_count" in manifest
    assert "audit_events_count" in manifest
    assert manifest["render_mode"] == "off"
    assert isinstance(manifest["config_version"], str)
