"""Alert deduplication and lifecycle (FR-24 … FR-28, UC-3, UC-4).

The cooldown window is measured from `last_seen_at`, not from `raised_at`. With a
5-second telemetry interval and a 180-second cooldown, measuring from `raised_at`
would create a fresh alert every three minutes for a condition that never stopped;
measuring from `last_seen_at` keeps one alert alive for as long as the fault
persists and only starts a new one after the fault has genuinely been quiet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import ensure_utc
from ..enums import AlertStatus, Severity, is_more_severe
from ..models import Alert, Vehicle
from ..rules import AlertCandidate

OPEN_STATES = (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED)


class AlertTransitionError(Exception):
    """Raised for an illegal lifecycle transition (mapped to HTTP 409)."""


@dataclass(slots=True)
class RaiseOutcome:
    created: list[Alert]
    updated: list[Alert]

    @property
    def all(self) -> list[Alert]:
        return [*self.created, *self.updated]


def find_open_alert(
    session: Session,
    *,
    vehicle_id: int,
    rule_code: str,
    now: datetime,
    cooldown_s: float,
) -> Alert | None:
    cutoff = now - timedelta(seconds=cooldown_s)
    stmt = (
        select(Alert)
        .where(
            Alert.vehicle_id == vehicle_id,
            Alert.rule_code == rule_code,
            Alert.status.in_(OPEN_STATES),
        )
        .order_by(Alert.last_seen_at.desc())
        .limit(1)
    )
    candidate = session.execute(stmt).scalar_one_or_none()
    if candidate is None:
        return None
    if ensure_utc(candidate.last_seen_at) < cutoff:
        return None
    return candidate


def raise_candidates(
    session: Session,
    *,
    vehicle: Vehicle,
    candidates: list[AlertCandidate],
    now: datetime,
    cooldown_s: float,
    telemetry_id: int | None = None,
) -> RaiseOutcome:
    outcome = RaiseOutcome(created=[], updated=[])
    for candidate in candidates:
        existing = find_open_alert(
            session,
            vehicle_id=vehicle.id,
            rule_code=candidate.rule_code,
            now=now,
            cooldown_s=cooldown_s,
        )
        if existing is None:
            alert = Alert(
                vehicle_id=vehicle.id,
                telemetry_id=telemetry_id,
                rule_code=candidate.rule_code,
                severity=candidate.severity,
                status=AlertStatus.OPEN,
                message=candidate.message,
                measured_value=candidate.measured_value,
                threshold_value=candidate.threshold_value,
                occurrences=1,
                raised_at=now,
                last_seen_at=now,
            )
            session.add(alert)
            outcome.created.append(alert)
            continue

        existing.occurrences += 1
        existing.last_seen_at = now
        existing.measured_value = candidate.measured_value
        # The message always tracks the latest reading — the feed must show what the
        # vehicle is doing now, not what it was doing when the alert first fired.
        existing.message = candidate.message
        # Severity, by contrast, ratchets: an operator who saw "critical" must not
        # find it quietly downgraded to "warning" underneath them.
        if is_more_severe(candidate.severity, existing.severity):
            existing.severity = candidate.severity
        outcome.updated.append(existing)

    session.flush()
    return outcome


def acknowledge(alert: Alert, now: datetime) -> Alert:
    if alert.status is AlertStatus.RESOLVED:
        raise AlertTransitionError("a resolved alert cannot be acknowledged")
    if alert.status is AlertStatus.ACKNOWLEDGED:
        return alert  # idempotent
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = now
    return alert


def resolve(alert: Alert, now: datetime) -> Alert:
    if alert.status is AlertStatus.RESOLVED:
        raise AlertTransitionError("alert is already resolved")
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = now
    return alert


def auto_resolve(
    session: Session, *, vehicle_id: int, rule_code: str, now: datetime
) -> list[Alert]:
    """Close every open alert for a rule whose condition has demonstrably cleared.

    Used when an offline vehicle starts reporting again (US-02). Only applied to
    rules where recovery is observable; a past overspeed event is history, not a
    condition that clears.
    """
    stmt = select(Alert).where(
        Alert.vehicle_id == vehicle_id,
        Alert.rule_code == rule_code,
        Alert.status.in_(OPEN_STATES),
    )
    resolved: list[Alert] = []
    for alert in session.execute(stmt).scalars():
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = now
        resolved.append(alert)
    if resolved:
        session.flush()
    return resolved


def duration_seconds(alert: Alert) -> float | None:
    """Derived, never stored — a second copy would drift (docs/04 §5)."""
    resolved_at = ensure_utc(alert.resolved_at)
    if resolved_at is None:
        return None
    return (resolved_at - ensure_utc(alert.raised_at)).total_seconds()


def severity_rank(severity: Severity) -> int:
    from ..enums import SEVERITY_ORDER

    return SEVERITY_ORDER[severity]
