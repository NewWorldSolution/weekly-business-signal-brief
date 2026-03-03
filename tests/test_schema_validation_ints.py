"""Tests for non-integer value detection in INT_COLUMNS."""
import pandas as pd

from wbsb.validate.schema import validate_dataframe


def _make_row(**overrides):
    base = {
        "week_start_date": "2024-01-01",
        "ad_spend_google": 100.0,
        "ad_spend_meta": 50.0,
        "ad_spend_other": 0.0,
        "impressions_total": 1000,
        "clicks_total": 50,
        "leads_paid": 10,
        "leads_organic": 5,
        "bookings_total": 8,
        "appointments_completed": 7,
        "appointments_cancelled": 1,
        "new_clients_paid": 3,
        "new_clients_organic": 2,
        "returning_clients": 4,
        "gross_revenue": 2000.0,
        "refunds": 0.0,
        "variable_cost": 500.0,
    }
    base.update(overrides)
    return base


def test_non_integer_value_emits_audit_event():
    df = pd.DataFrame([_make_row(leads_paid=2.7)])
    events, _ = validate_dataframe(df)
    types = [e.event_type for e in events]
    assert "non_integer_value" in types


def test_non_integer_event_contains_column_name():
    df = pd.DataFrame([_make_row(leads_paid=3.14)])
    events, _ = validate_dataframe(df)
    hit = next(e for e in events if e.event_type == "non_integer_value")
    assert hit.column == "leads_paid"
    assert "leads_paid" in hit.message


def test_integer_value_does_not_emit_non_integer_event():
    df = pd.DataFrame([_make_row(leads_paid=10)])
    events, _ = validate_dataframe(df)
    types = [e.event_type for e in events]
    assert "non_integer_value" not in types
