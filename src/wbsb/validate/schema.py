"""Validate loaded DataFrame against expected schema."""
from __future__ import annotations

import pandas as pd

from wbsb.domain.models import AuditEvent

REQUIRED_COLUMNS: list[str] = [
    "week_start_date",
    "ad_spend_google",
    "ad_spend_meta",
    "ad_spend_other",
    "impressions_total",
    "clicks_total",
    "leads_paid",
    "leads_organic",
    "bookings_total",
    "appointments_completed",
    "appointments_cancelled",
    "new_clients_paid",
    "new_clients_organic",
    "returning_clients",
    "gross_revenue",
    "refunds",
    "variable_cost",
]

FLOAT_COLUMNS: list[str] = [
    "ad_spend_google",
    "ad_spend_meta",
    "ad_spend_other",
    "gross_revenue",
    "refunds",
    "variable_cost",
]

INT_COLUMNS: list[str] = [
    "impressions_total",
    "clicks_total",
    "leads_paid",
    "leads_organic",
    "bookings_total",
    "appointments_completed",
    "appointments_cancelled",
    "new_clients_paid",
    "new_clients_organic",
    "returning_clients",
]


def validate_dataframe(df: pd.DataFrame) -> tuple[list[AuditEvent], pd.DataFrame]:
    """Validate and coerce DataFrame columns.

    Returns:
        Tuple of (audit_events, validated_df).
    """
    events: list[AuditEvent] = []
    df = df.copy()

    # Check required columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Coerce numeric types
    for col in FLOAT_COLUMNS:
        original_nulls = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        new_nulls = df[col].isna().sum()
        if new_nulls > original_nulls:
            events.append(
                AuditEvent(
                    event_type="coerce_warning",
                    message=(
                        f"Column '{col}' had {new_nulls - original_nulls}"
                        " non-numeric values coerced to NaN"
                    ),
                    column=col,
                )
            )

    for col in INT_COLUMNS:
        original_nulls = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        new_nulls = df[col].isna().sum()
        if new_nulls > original_nulls:
            events.append(
                AuditEvent(
                    event_type="coerce_warning",
                    message=(
                        f"Column '{col}' had {new_nulls - original_nulls}"
                        " non-numeric values coerced to NaN"
                    ),
                    column=col,
                )
            )
        # Detect numeric-but-non-integer values
        numeric_vals = df[col].dropna()
        non_int_mask = numeric_vals % 1 != 0
        if non_int_mask.any():
            count = int(non_int_mask.sum())
            sample = numeric_vals[non_int_mask].iloc[0]
            events.append(
                AuditEvent(
                    event_type="non_integer_value",
                    message=(
                        f"Column '{col}' has {count} non-integer numeric value(s);"
                        f" e.g. {sample}"
                    ),
                    column=col,
                    extra={"count": count},
                )
            )

    # Add derived columns
    df["ad_spend_total"] = df["ad_spend_google"] + df["ad_spend_meta"] + df["ad_spend_other"]
    df["leads_total"] = df["leads_paid"] + df["leads_organic"]
    df["new_clients_total"] = df["new_clients_paid"] + df["new_clients_organic"]
    df["net_revenue"] = df["gross_revenue"] - df["refunds"]

    events.append(
        AuditEvent(
            event_type="info",
            message=f"Validated {len(df)} rows; derived columns added",
        )
    )

    return events, df
