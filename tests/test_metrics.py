"""Tests for metric calculations."""
from __future__ import annotations

import pytest

from wbsb.metrics.calculate import compute_metrics


SAMPLE_ROW = {
    "ad_spend_total": 2100.0,
    "leads_paid": 28.0,
    "new_clients_paid": 18.0,
    "new_clients_total": 29.0,
    "returning_clients": 50.0,
    "bookings_total": 42.0,
    "appointments_completed": 35.0,
    "appointments_cancelled": 10.0,
    "gross_revenue": 8500.0,
    "net_revenue": 8000.0,
    "variable_cost": 4200.0,
}


def test_cac_paid():
    m = compute_metrics(SAMPLE_ROW)
    assert m["cac_paid"] == pytest.approx(2100.0 / 18.0)


def test_show_rate():
    m = compute_metrics(SAMPLE_ROW)
    assert m["show_rate"] == pytest.approx(35.0 / 42.0)


def test_cancel_rate():
    m = compute_metrics(SAMPLE_ROW)
    assert m["cancel_rate"] == pytest.approx(10.0 / 42.0)


def test_gross_margin():
    m = compute_metrics(SAMPLE_ROW)
    # (net_revenue - variable_cost) / net_revenue = (8000 - 4200) / 8000
    assert m["gross_margin"] == pytest.approx(3800.0 / 8000.0)


def test_marketing_pct_revenue():
    m = compute_metrics(SAMPLE_ROW)
    assert m["marketing_pct_revenue"] == pytest.approx(2100.0 / 8000.0)


def test_contribution_after_marketing():
    m = compute_metrics(SAMPLE_ROW)
    # net_revenue - variable_cost - ad_spend_total = 8000 - 4200 - 2100
    assert m["contribution_after_marketing"] == pytest.approx(1700.0)


def test_zero_division_safety():
    row = {**SAMPLE_ROW, "leads_paid": 0.0, "new_clients_paid": 0.0, "bookings_total": 0.0}
    m = compute_metrics(row)
    assert m["cac_paid"] is None
    assert m["show_rate"] is None
    assert m["paid_lead_to_client"] is None


def test_net_revenue_passthrough():
    m = compute_metrics(SAMPLE_ROW)
    assert m["net_revenue"] == pytest.approx(8000.0)
