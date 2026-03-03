"""Registry of metric definitions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDef:
    """Definition of a metric."""

    id: str
    name: str
    unit: str  # currency | ratio | count | pct


METRIC_REGISTRY: list[MetricDef] = [
    MetricDef("cac_paid", "CAC (Paid)", "currency"),
    MetricDef("paid_lead_to_client", "Paid Lead-to-Client Rate", "ratio"),
    MetricDef("paid_share_new_clients", "Paid Share of New Clients", "ratio"),
    MetricDef("cost_per_paid_lead", "Cost per Paid Lead", "currency"),
    MetricDef("show_rate", "Show Rate", "ratio"),
    MetricDef("cancel_rate", "Cancel Rate", "ratio"),
    MetricDef("rev_per_completed_appt", "Revenue per Completed Appointment", "currency"),
    MetricDef("net_revenue", "Net Revenue", "currency"),
    MetricDef("new_client_ratio", "New Client Ratio", "ratio"),
    MetricDef("gross_margin", "Gross Margin", "ratio"),
    MetricDef("marketing_pct_revenue", "Marketing % of Revenue", "ratio"),
    MetricDef("contribution_after_marketing", "Contribution After Marketing", "currency"),
    MetricDef("bookings_total", "Total Bookings", "count"),
    MetricDef("new_clients_total", "Total New Clients", "count"),
]

METRIC_REGISTRY_BY_ID: dict[str, MetricDef] = {m.id: m for m in METRIC_REGISTRY}
