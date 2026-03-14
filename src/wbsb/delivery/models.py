from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class DeliveryTarget(StrEnum):
    teams = "teams"
    slack = "slack"


class DeliveryStatus(StrEnum):
    success = "success"
    skipped = "skipped"
    failed = "failed"


class DeliveryResult(BaseModel):
    target: DeliveryTarget
    status: DeliveryStatus
    http_status_code: int | None
    error: str | None
    delivered_at: str | None
