"""Domain enumerations.

Deliberately in their own module with no third-party imports: the pure rule layer
(app/rules/) needs these values but must never import SQLAlchemy. models.py maps
them to columns; rules compare against them.
"""

from __future__ import annotations

import enum


class VehicleType(str, enum.Enum):
    BUS = "bus"
    TRUCK = "truck"


class VehicleStatus(str, enum.Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class Severity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.CRITICAL: 2,
}


def is_more_severe(candidate: Severity, existing: Severity) -> bool:
    return SEVERITY_ORDER[candidate] > SEVERITY_ORDER[existing]
