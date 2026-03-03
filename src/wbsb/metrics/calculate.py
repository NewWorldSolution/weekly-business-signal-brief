"""Deterministic metric calculation from a single-week row."""
from __future__ import annotations

from typing import Any, Optional

from wbsb.utils.hash import safe_div


def compute_metrics(row: dict[str, Any]) -> dict[str, Optional[float]]:
    """Compute all metrics from a single week data row.

    Args:
        row: Dictionary of column values for a single week.

    Returns:
        Dictionary mapping metric_id to computed value (None if not computable).
    """
    ad_spend_total: float = row.get("ad_spend_total", 0.0) or 0.0
    leads_paid: float = row.get("leads_paid", 0.0) or 0.0
    new_clients_paid: float = row.get("new_clients_paid", 0.0) or 0.0
    new_clients_total: float = row.get("new_clients_total", 0.0) or 0.0
    returning_clients: float = row.get("returning_clients", 0.0) or 0.0
    bookings_total: float = row.get("bookings_total", 0.0) or 0.0
    appointments_completed: float = row.get("appointments_completed", 0.0) or 0.0
    appointments_cancelled: float = row.get("appointments_cancelled", 0.0) or 0.0
    gross_revenue: float = row.get("gross_revenue", 0.0) or 0.0
    net_revenue: float = row.get("net_revenue", 0.0) or 0.0
    variable_cost: float = row.get("variable_cost", 0.0) or 0.0

    return {
        # Acquisition
        "cac_paid": safe_div(ad_spend_total, new_clients_paid),
        "paid_lead_to_client": safe_div(new_clients_paid, leads_paid),
        "paid_share_new_clients": safe_div(new_clients_paid, new_clients_total),
        "cost_per_paid_lead": safe_div(ad_spend_total, leads_paid),
        # Operational
        "show_rate": safe_div(appointments_completed, bookings_total),
        "cancel_rate": safe_div(appointments_cancelled, bookings_total),
        "rev_per_completed_appt": safe_div(gross_revenue, appointments_completed),
        # Revenue / Mix
        "net_revenue": net_revenue,
        "new_client_ratio": safe_div(
            new_clients_total, new_clients_total + returning_clients
        ),
        # Financial health
        "gross_margin": safe_div(net_revenue - variable_cost, net_revenue),
        "marketing_pct_revenue": safe_div(ad_spend_total, net_revenue),
        "contribution_after_marketing": (
            net_revenue - variable_cost - ad_spend_total
            if net_revenue is not None
            else None
        ),
        # Raw counts used in hybrid rules
        "bookings_total": bookings_total,
        "new_clients_total": new_clients_total,
    }
