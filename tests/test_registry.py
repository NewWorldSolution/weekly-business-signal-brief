"""Tests for metric registry metadata invariants."""
from __future__ import annotations

from wbsb.metrics.registry import METRIC_REGISTRY


def test_metric_format_hint_is_valid():
    allowed = {"currency", "percent", "integer", "decimal"}
    for metric in METRIC_REGISTRY:
        assert metric.format_hint
        assert metric.format_hint in allowed


def test_metric_category_is_valid():
    allowed = {"acquisition", "operations", "revenue", "financial_health"}
    for metric in METRIC_REGISTRY:
        assert metric.category
        assert metric.category in allowed


def test_metric_order_fields_are_positive_integers():
    for metric in METRIC_REGISTRY:
        assert isinstance(metric.category_order, int)
        assert isinstance(metric.display_order, int)
        assert metric.category_order > 0
        assert metric.display_order > 0


def test_category_display_order_pairs_are_unique():
    pairs = [(metric.category, metric.display_order) for metric in METRIC_REGISTRY]
    assert len(pairs) == len(set(pairs))
