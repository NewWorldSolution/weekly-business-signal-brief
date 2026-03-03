"""Tests for the rules engine."""
from __future__ import annotations

from wbsb.domain.models import RunConfig
from wbsb.rules.engine import evaluate_rules

BASE_CONFIG = {
    "defaults": {"min_prev_net_revenue": 3000, "volume_threshold": 5},
    "rules": [
        {
            "id": "A1",
            "metric_id": "net_revenue",
            "severity": "WARN",
            "condition": "delta_pct_lte",
            "threshold": -0.15,
            "requires_min_prev_net_revenue": True,
        },
        {
            "id": "F1",
            "metric_id": "bookings_total",
            "severity": "WARN",
            "condition": "hybrid_delta_pct_lte",
            "threshold_pct": -0.20,
            "threshold_abs": -3,
            "volume_metric": "bookings_total",
        },
        {
            "id": "H1",
            "metric_id": "gross_margin",
            "severity": "WARN",
            "condition": "absolute_lt",
            "threshold": 0.50,
            "requires_current_net_revenue_gt": 0,
        },
    ],
}

RUN_CONFIG = RunConfig(min_prev_net_revenue=3000, volume_threshold=5)


def test_net_revenue_warn_fires():
    curr = {"net_revenue": 7000.0, "bookings_total": 50.0, "gross_margin": 0.60}
    prev = {"net_revenue": 9000.0, "bookings_total": 52.0, "leads_paid": 10.0,
            "new_clients_paid": 5.0}
    deltas = {
        "net_revenue": (-2000.0, -0.2222),
        "bookings_total": (-2.0, -0.038),
        "gross_margin": (0.0, 0.0),
    }
    signals = evaluate_rules(curr, prev, deltas, BASE_CONFIG, RUN_CONFIG, "ok")
    rule_ids = [s.rule_id for s in signals]
    assert "A1" in rule_ids


def test_net_revenue_no_fire_above_threshold():
    curr = {"net_revenue": 9500.0, "bookings_total": 50.0, "gross_margin": 0.60}
    prev = {"net_revenue": 9000.0, "bookings_total": 52.0, "leads_paid": 10.0,
            "new_clients_paid": 5.0}
    deltas = {
        "net_revenue": (500.0, 0.0556),
        "bookings_total": (-2.0, -0.038),
        "gross_margin": (0.0, 0.0),
    }
    signals = evaluate_rules(curr, prev, deltas, BASE_CONFIG, RUN_CONFIG, "ok")
    rule_ids = [s.rule_id for s in signals]
    assert "A1" not in rule_ids


def test_hybrid_low_volume_abs_fires():
    """Low volume: use absolute threshold."""
    curr = {"net_revenue": 5000.0, "bookings_total": 1.0, "gross_margin": 0.60}
    prev = {"net_revenue": 5000.0, "bookings_total": 4.0, "leads_paid": 10.0,
            "new_clients_paid": 5.0}
    deltas = {
        "net_revenue": (0.0, 0.0),
        "bookings_total": (-3.0, -0.75),
        "gross_margin": (0.0, 0.0),
    }
    signals = evaluate_rules(curr, prev, deltas, BASE_CONFIG, RUN_CONFIG, "ok")
    rule_ids = [s.rule_id for s in signals]
    assert "F1" in rule_ids


def test_hybrid_low_volume_abs_no_fire():
    """Low volume: delta_abs = -2, threshold = -3, should NOT fire."""
    curr = {"net_revenue": 5000.0, "bookings_total": 2.0, "gross_margin": 0.60}
    prev = {"net_revenue": 5000.0, "bookings_total": 4.0, "leads_paid": 10.0,
            "new_clients_paid": 5.0}
    deltas = {
        "net_revenue": (0.0, 0.0),
        "bookings_total": (-2.0, -0.5),
        "gross_margin": (0.0, 0.0),
    }
    signals = evaluate_rules(curr, prev, deltas, BASE_CONFIG, RUN_CONFIG, "ok")
    rule_ids = [s.rule_id for s in signals]
    assert "F1" not in rule_ids


def test_hybrid_high_volume_pct_fires():
    """High volume: use pct threshold."""
    curr = {"net_revenue": 5000.0, "bookings_total": 40.0, "gross_margin": 0.60}
    prev = {"net_revenue": 5000.0, "bookings_total": 51.0, "leads_paid": 10.0,
            "new_clients_paid": 5.0}
    deltas = {
        "net_revenue": (0.0, 0.0),
        "bookings_total": (-11.0, -0.2157),
        "gross_margin": (0.0, 0.0),
    }
    signals = evaluate_rules(curr, prev, deltas, BASE_CONFIG, RUN_CONFIG, "ok")
    rule_ids = [s.rule_id for s in signals]
    assert "F1" in rule_ids


def test_gross_margin_absolute_fires():
    curr = {"net_revenue": 5000.0, "bookings_total": 50.0, "gross_margin": 0.45}
    prev = {"net_revenue": 5000.0, "bookings_total": 52.0, "leads_paid": 10.0,
            "new_clients_paid": 5.0}
    deltas = {
        "net_revenue": (0.0, 0.0),
        "bookings_total": (-2.0, -0.038),
        "gross_margin": (-0.05, -0.10),
    }
    signals = evaluate_rules(curr, prev, deltas, BASE_CONFIG, RUN_CONFIG, "ok")
    rule_ids = [s.rule_id for s in signals]
    assert "H1" in rule_ids


def test_signals_sorted_by_rule_id():
    """Signals must be returned sorted by rule_id."""
    curr = {"net_revenue": 7000.0, "bookings_total": 40.0, "gross_margin": 0.40}
    prev = {"net_revenue": 9000.0, "bookings_total": 52.0, "leads_paid": 10.0,
            "new_clients_paid": 5.0}
    deltas = {
        "net_revenue": (-2000.0, -0.2222),
        "bookings_total": (-12.0, -0.2308),
        "gross_margin": (-0.1, -0.20),
    }
    signals = evaluate_rules(curr, prev, deltas, BASE_CONFIG, RUN_CONFIG, "ok")
    ids = [s.rule_id for s in signals]
    assert ids == sorted(ids)


def test_low_reliability_skips_min_prev_rule():
    """When prev_net_revenue < min, rules with requires_min_prev_net_revenue should not fire."""
    curr = {"net_revenue": 1000.0, "bookings_total": 50.0, "gross_margin": 0.60}
    prev = {"net_revenue": 1500.0, "bookings_total": 52.0, "leads_paid": 10.0,
            "new_clients_paid": 5.0}  # prev_net_revenue < 3000
    deltas = {
        "net_revenue": (-500.0, -0.333),
        "bookings_total": (-2.0, -0.038),
        "gross_margin": (0.0, 0.0),
    }
    signals = evaluate_rules(curr, prev, deltas, BASE_CONFIG, RUN_CONFIG, "low")
    rule_ids = [s.rule_id for s in signals]
    assert "A1" not in rule_ids  # Requires min prev net revenue, should be skipped


# Config with volume_metric pointing to a DIFFERENT metric than metric_id
VOLUME_METRIC_CROSS_CONFIG = {
    "defaults": {"min_prev_net_revenue": 3000, "volume_threshold": 5},
    "rules": [
        {
            "id": "X1",
            "metric_id": "show_rate",
            "severity": "WARN",
            "condition": "hybrid_delta_pct_lte",
            "threshold_pct": -0.20,
            "threshold_abs": -3,
            "volume_metric": "bookings_total",  # Different from metric_id
        },
    ],
}


def test_hybrid_volume_metric_low_volume_abs_fires():
    """volume_metric (bookings_total) < threshold → absolute mode → fires."""
    curr = {"net_revenue": 5000.0, "show_rate": 6.0, "bookings_total": 1.0}
    prev = {"net_revenue": 5000.0, "show_rate": 10.0, "bookings_total": 4.0}  # 4 < 5
    deltas = {"show_rate": (-4.0, -0.40), "bookings_total": (-3.0, -0.75)}
    signals = evaluate_rules(curr, prev, deltas, VOLUME_METRIC_CROSS_CONFIG, RUN_CONFIG, "ok")
    assert "X1" in [s.rule_id for s in signals]


def test_hybrid_volume_metric_high_volume_pct_fires():
    """volume_metric (bookings_total) >= threshold → pct mode → fires."""
    curr = {"net_revenue": 5000.0, "show_rate": 7.0, "bookings_total": 50.0}
    prev = {"net_revenue": 5000.0, "show_rate": 10.0, "bookings_total": 50.0}  # 50 >= 5
    deltas = {"show_rate": (-3.0, -0.30), "bookings_total": (0.0, 0.0)}
    signals = evaluate_rules(curr, prev, deltas, VOLUME_METRIC_CROSS_CONFIG, RUN_CONFIG, "ok")
    assert "X1" in [s.rule_id for s in signals]


def test_hybrid_no_volume_metric_fallback_fires():
    """Rule without volume_metric falls back to metric_id for volume check."""
    config_no_volume_metric = {
        "defaults": {"min_prev_net_revenue": 3000, "volume_threshold": 5},
        "rules": [
            {
                "id": "Y1",
                "metric_id": "bookings_total",
                "severity": "WARN",
                "condition": "hybrid_delta_pct_lte",
                "threshold_pct": -0.20,
                "threshold_abs": -3,
                # No volume_metric key at all
            },
        ],
    }
    curr = {"net_revenue": 5000.0, "bookings_total": 1.0}
    prev = {"net_revenue": 5000.0, "bookings_total": 4.0}  # 4 < 5
    deltas = {"bookings_total": (-3.0, -0.75)}
    signals = evaluate_rules(curr, prev, deltas, config_no_volume_metric, RUN_CONFIG, "ok")
    assert "Y1" in [s.rule_id for s in signals]
