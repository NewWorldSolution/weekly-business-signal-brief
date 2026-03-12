"""Numeric extraction and grounding helper utilities for eval scoring."""
from __future__ import annotations

import re

from wbsb.domain.models import Findings

_NUMBER_PATTERN = re.compile(r"-?\d[\d,]*(?:\.\d+)?%?")
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def extract_numbers_from_text(text: str) -> list[str]:
    """Extract numeric tokens from free text, excluding date-like values."""
    scrubbed = _DATE_PATTERN.sub(" ", text)
    tokens: list[str] = []

    for match in _NUMBER_PATTERN.finditer(scrubbed):
        start, end = match.span()
        prev_char = scrubbed[start - 1] if start > 0 else ""
        next_char = scrubbed[end] if end < len(scrubbed) else ""

        # Skip fragments embedded in alphanumeric tokens, e.g. "3485e2".
        if prev_char.isalpha() or next_char.isalpha():
            continue
        tokens.append(match.group(0))

    return tokens


def normalize_number(raw: str) -> float | None:
    """Normalize a raw numeric token into float or None if invalid."""
    cleaned = raw.strip().replace("%", "").replace(",", "").replace("$", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def candidate_values(raw: str, pct_normalization: bool) -> list[float]:
    """Build candidate numeric interpretations for a raw token."""
    normalized = normalize_number(raw)
    if normalized is None:
        return []
    if raw.strip().endswith("%") and pct_normalization:
        return [normalized, normalized / 100.0]
    return [normalized]


def build_evidence_allowlist(findings: Findings) -> set[float]:
    """Collect all numeric evidence values from findings metrics and signals."""
    allowlist: set[float] = set()

    for metric in findings.metrics:
        for field in ("current", "previous", "delta_abs", "delta_pct"):
            value = getattr(metric, field, None)
            if isinstance(value, (int, float)):
                allowlist.add(float(value))

    for signal in findings.signals:
        for field in ("current", "previous", "delta_abs", "delta_pct", "threshold"):
            value = getattr(signal, field, None)
            if isinstance(value, (int, float)):
                allowlist.add(float(value))

        evidence = getattr(signal, "evidence", {}) or {}
        if isinstance(evidence, dict):
            for key in ("current", "previous", "delta_abs", "delta_pct", "threshold"):
                value = evidence.get(key)
                if isinstance(value, (int, float)):
                    allowlist.add(float(value))

    return allowlist


def is_grounded(candidate: float, allowlist: set[float], cfg: dict) -> bool:
    """Return True when candidate is within configured tolerance of any value."""
    if not allowlist:
        return False

    abs_tol = cfg["grounding_tolerance_abs"]
    rel_tol = cfg["grounding_tolerance_rel"]

    for reference in allowlist:
        tolerance = abs_tol if abs(reference) < 1.0 else rel_tol * abs(reference)
        if abs(candidate - reference) <= tolerance:
            return True
    return False
