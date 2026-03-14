from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class DeliveryTarget(str, Enum):  # noqa: UP042
    teams = "teams"
    slack = "slack"


class DeliveryStatus(str, Enum):  # noqa: UP042
    success = "success"
    skipped = "skipped"
    failed = "failed"


class DeliveryResult(BaseModel):
    target: DeliveryTarget
    status: DeliveryStatus
    http_status_code: int | None
    error: str | None
    delivered_at: str | None
