"""Tests for delta computation."""
from __future__ import annotations

import pytest

from wbsb.compare.delta import compute_delta


def test_basic_positive_delta():
    delta_abs, delta_pct = compute_delta(110.0, 100.0)
    assert delta_abs == pytest.approx(10.0)
    assert delta_pct == pytest.approx(0.10)


def test_basic_negative_delta():
    delta_abs, delta_pct = compute_delta(85.0, 100.0)
    assert delta_abs == pytest.approx(-15.0)
    assert delta_pct == pytest.approx(-0.15)


def test_none_current():
    delta_abs, delta_pct = compute_delta(None, 100.0)
    assert delta_abs is None
    assert delta_pct is None


def test_none_previous():
    delta_abs, delta_pct = compute_delta(100.0, None)
    assert delta_abs is None
    assert delta_pct is None


def test_both_none():
    delta_abs, delta_pct = compute_delta(None, None)
    assert delta_abs is None
    assert delta_pct is None


def test_zero_previous():
    delta_abs, delta_pct = compute_delta(50.0, 0.0)
    assert delta_abs == pytest.approx(50.0)
    assert delta_pct is None  # Safe division


def test_zero_both():
    delta_abs, delta_pct = compute_delta(0.0, 0.0)
    assert delta_abs == pytest.approx(0.0)
    assert delta_pct is None
