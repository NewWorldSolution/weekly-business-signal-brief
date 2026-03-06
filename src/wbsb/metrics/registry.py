"""Registry of metric definitions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDef:
    """Definition of a metric."""

    id: str
    name: str
    unit: str  # currency | ratio | count | pct
    format_hint: str
    category: str
    category_order: int
    display_order: int


METRIC_REGISTRY: list[MetricDef] = [
    MetricDef("cac_paid", "CAC (Paid)", "currency", "currency", "acquisition", 2, 1),
    MetricDef(
        "paid_lead_to_client",
        "Paid Lead-to-Client Rate",
        "ratio",
        "percent",
        "acquisition",
        2,
        3,
    ),
    MetricDef(
        "paid_share_new_clients",
        "Paid Share of New Clients",
        "ratio",
        "percent",
        "acquisition",
        2,
        4,
    ),
    MetricDef(
        "cost_per_paid_lead",
        "Cost per Paid Lead",
        "currency",
        "currency",
        "acquisition",
        2,
        2,
    ),
    MetricDef("show_rate", "Show Rate", "ratio", "percent", "operations", 3, 1),
    MetricDef("cancel_rate", "Cancel Rate", "ratio", "percent", "operations", 3, 2),
    MetricDef(
        "rev_per_completed_appt",
        "Revenue per Completed Appointment",
        "currency",
        "currency",
        "operations",
        3,
        3,
    ),
    MetricDef("net_revenue", "Net Revenue", "currency", "currency", "revenue", 1, 1),
    MetricDef("new_client_ratio", "New Client Ratio", "ratio", "percent", "revenue", 1, 2),
    MetricDef("gross_margin", "Gross Margin", "ratio", "percent", "financial_health", 4, 1),
    MetricDef(
        "marketing_pct_revenue",
        "Marketing % of Revenue",
        "ratio",
        "percent",
        "financial_health",
        4,
        2,
    ),
    MetricDef(
        "contribution_after_marketing",
        "Contribution After Marketing",
        "currency",
        "currency",
        "financial_health",
        4,
        3,
    ),
    MetricDef("bookings_total", "Total Bookings", "count", "integer", "operations", 3, 4),
    MetricDef("new_clients_total", "Total New Clients", "count", "integer", "acquisition", 2, 5),
]

METRIC_REGISTRY_BY_ID: dict[str, MetricDef] = {m.id: m for m in METRIC_REGISTRY}
