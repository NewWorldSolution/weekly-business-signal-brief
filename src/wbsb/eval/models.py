"""Pydantic models for the WBSB evaluation framework."""
from __future__ import annotations

from pydantic import BaseModel


class HallucinationViolation(BaseModel):
    """A single structural hallucination detected in LLM output."""

    type: str
    severity: str  # "critical" | "major" | "minor"
    detail: str


class EvalScores(BaseModel):
    """Evaluation scores computed for a single LLM response."""

    schema_version: str = "1.0"
    grounding: float | None
    grounding_reason: str | None
    flagged_numbers: list[str]
    signal_coverage: float
    group_coverage: float
    hallucination_risk: int
    hallucination_violations: list[HallucinationViolation]
    model: str
    evaluated_at: str
