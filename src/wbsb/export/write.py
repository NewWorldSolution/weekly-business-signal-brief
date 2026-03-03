"""Write run artifacts to disk."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from wbsb.domain.models import Findings, Manifest
from wbsb.utils.hash import file_sha256


def write_artifacts(
    run_dir: Path,
    findings: Findings,
    brief_md: str,
    elapsed_seconds: float,
    run_id: str,
    input_path: Path,
    input_hash: str,
    config_hash: str,
) -> None:
    """Write all run artifacts to run_dir.

    Artifacts:
        - findings.json
        - brief.md
        - manifest.json

    Args:
        run_dir: Directory for this run's artifacts.
        findings: Computed Findings document.
        brief_md: Rendered brief markdown.
        elapsed_seconds: Pipeline elapsed time.
        run_id: Unique run identifier.
        input_path: Path to input file.
        input_hash: SHA-256 of input file.
        config_hash: SHA-256 of config.
    """
    findings_path = run_dir / "findings.json"
    brief_path = run_dir / "brief.md"
    manifest_path = run_dir / "manifest.json"

    # Write findings.json
    findings_json = findings.model_dump_json(indent=2)
    findings_path.write_text(findings_json, encoding="utf-8")

    # Write brief.md
    brief_path.write_text(brief_md, encoding="utf-8")

    # Compute artifact hashes
    findings_hash = file_sha256(findings_path)
    brief_hash = file_sha256(brief_path)

    # Write manifest.json
    manifest = Manifest(
        run_id=run_id,
        generated_at=datetime.now(UTC),
        input_file=input_path.name,
        input_sha256=input_hash,
        config_sha256=config_hash,
        elapsed_seconds=round(elapsed_seconds, 3),
        artifacts={
            "findings.json": findings_hash,
            "brief.md": brief_hash,
        },
    )
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
