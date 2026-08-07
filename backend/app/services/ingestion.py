"""Telemetry ingestion (UC-1): persist, evaluate, raise, broadcast.

This is the orchestration layer. It owns the database session, the clock and the
WebSocket side effects, so that the rule engine underneath it can stay pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Thresholds, get_thresholds
from ..database import ensure_utc, utcnow
from ..enums import Severity
from ..models import Alert, Telemetry, Vehicle
from ..rules import Reading
from ..rules.offline import CODE as OFFLINE_CODE
from . import alerts as alert_service
from . import monitoring
from .hub import hub


class VehicleNotFound(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(f"unknown vehicle code '{code}'")
        self.code = code


@dataclass(slots=True)
class Metrics:
    started_at: datetime = field(default_factory=utcnow)
    readings_ingested: int = 0
    alerts_raised: int = 0

    @property
    def uptime_seconds(self) -> float:
        return (utcnow() - self.started_at).total_seconds()


metrics = Metrics()


@dataclass(slots=True)
class IngestOutcome:
    vehicle: Vehicle
    reading_row: Telemetry | None
    duplicate: bool
    evaluated: bool
    created: list[Alert]
    updated: list[Alert]
    failed_rules: dict[str, str]


def _get_vehicle(session: Session, code: str) -> Vehicle:
    vehicle = session.execute(
        select(Vehicle).where(Vehicle.code == code)
    ).scalar_one_or_none()
    if vehicle is None:
        raise VehicleNotFound(code)
    return vehicle


def _previous_reading(session: Session, vehicle_id: int, before: datetime) -> Telemetry | None:
    stmt = (
        select(Telemetry)
        .where(Telemetry.vehicle_id == vehicle_id, Telemetry.recorded_at < before)
        .order_by(Telemetry.recorded_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def _existing_reading(session: Session, vehicle_id: int, at: datetime) -> Telemetry | None:
    stmt = select(Telemetry).where(
        Telemetry.vehicle_id == vehicle_id, Telemetry.recorded_at == at
    )
    return session.execute(stmt).scalar_one_or_none()


def ingest(
    session: Session,
    payload,  # schemas.TelemetryCreate — untyped to keep this layer schema-agnostic
    *,
    now: datetime | None = None,
    thresholds: Thresholds | None = None,
    broadcast: bool = True,
) -> IngestOutcome:
    now = now or utcnow()
    thresholds = thresholds or get_thresholds()
    recorded_at = ensure_utc(payload.recorded_at)

    vehicle = _get_vehicle(session, payload.vehicle_code)

    duplicate_row = _existing_reading(session, vehicle.id, recorded_at)
    if duplicate_row is not None:
        # FR-13: idempotent. Do not re-evaluate — that would double-count occurrences.
        return IngestOutcome(vehicle, duplicate_row, True, False, [], [], {})

    previous_row = _previous_reading(session, vehicle.id, recorded_at)

    row = Telemetry(
        vehicle_id=vehicle.id,
        recorded_at=recorded_at,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed_kph=payload.speed_kph,
        heading_deg=payload.heading_deg,
        engine_temp_c=payload.engine_temp_c,
        fuel_pct=payload.fuel_pct,
        cargo_temp_c=payload.cargo_temp_c,
        odometer_km=payload.odometer_km,
        received_at=now,
    )
    session.add(row)
    session.flush()
    metrics.readings_ingested += 1

    if not monitoring.is_evaluable(vehicle):
        # FR-04: stored for the record, but a vehicle in the workshop raises nothing.
        session.commit()
        if broadcast:
            _broadcast_vehicle(vehicle, row)
        return IngestOutcome(vehicle, row, False, False, [], [], {})

    ctx = monitoring.build_context(
        vehicle=vehicle,
        reading=monitoring.to_reading(row),
        now=now,
        thresholds=thresholds,
        previous=monitoring.to_reading(previous_row) if previous_row else None,
    )
    result = monitoring.evaluate(ctx)

    outcome = alert_service.raise_candidates(
        session,
        vehicle=vehicle,
        candidates=result.candidates,
        now=now,
        cooldown_s=thresholds.alert_cooldown_s,
        telemetry_id=row.id,
    )

    # US-02: a vehicle that starts reporting again is no longer offline.
    if (now - recorded_at).total_seconds() <= thresholds.heartbeat_timeout_s:
        alert_service.auto_resolve(
            session, vehicle_id=vehicle.id, rule_code=OFFLINE_CODE, now=now
        )

    metrics.alerts_raised += len(outcome.created)
    session.commit()

    if broadcast:
        _broadcast_vehicle(vehicle, row)
        for alert in outcome.created:
            _broadcast_alert(vehicle, alert)

    return IngestOutcome(
        vehicle, row, False, True, outcome.created, outcome.updated, result.failed_rules
    )


def sweep_offline(
    session: Session, *, now: datetime | None = None, thresholds: Thresholds | None = None
) -> list[Alert]:
    """Periodic detection of vehicles past the heartbeat timeout (D-7).

    Evaluates only the offline rule, against each active vehicle's last known
    reading. A vehicle that has never reported at all is skipped: it has not gone
    offline, it has never been online.
    """
    from ..enums import VehicleStatus
    from ..rules import offline as offline_rule

    now = now or utcnow()
    thresholds = thresholds or get_thresholds()
    created: list[Alert] = []

    vehicles = session.execute(
        select(Vehicle).where(Vehicle.status == VehicleStatus.ACTIVE)
    ).scalars().all()

    for vehicle in vehicles:
        last = session.execute(
            select(Telemetry)
            .where(Telemetry.vehicle_id == vehicle.id)
            .order_by(Telemetry.recorded_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if last is None:
            continue
        ctx = monitoring.build_context(
            vehicle=vehicle,
            reading=monitoring.to_reading(last),
            now=now,
            thresholds=thresholds,
        )
        candidates = offline_rule.evaluate(ctx)
        if not candidates:
            continue
        outcome = alert_service.raise_candidates(
            session,
            vehicle=vehicle,
            candidates=candidates,
            now=now,
            cooldown_s=thresholds.alert_cooldown_s,
            telemetry_id=None,
        )
        created.extend(outcome.created)
        for alert in outcome.created:
            _broadcast_alert(vehicle, alert)

    if created:
        metrics.alerts_raised += len(created)
    session.commit()
    return created


# --------------------------------------------------------------------- broadcasts


def _broadcast_vehicle(vehicle: Vehicle, row: Telemetry) -> None:
    hub.broadcast_soon(
        {
            "type": "vehicle_update",
            "vehicle": {
                "code": vehicle.code,
                "label": vehicle.label,
                "vehicle_type": vehicle.vehicle_type.value,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "speed_kph": row.speed_kph,
                "heading_deg": row.heading_deg,
                "engine_temp_c": row.engine_temp_c,
                "fuel_pct": row.fuel_pct,
                "cargo_temp_c": row.cargo_temp_c,
                "last_seen_at": ensure_utc(row.recorded_at).isoformat(),
            },
        }
    )


def _broadcast_alert(vehicle: Vehicle, alert: Alert) -> None:
    hub.broadcast_soon(
        {
            "type": "alert_raised",
            "alert": {
                "id": alert.id,
                "vehicle_code": vehicle.code,
                "rule_code": alert.rule_code,
                "severity": Severity(alert.severity).value,
                "message": alert.message,
                "measured_value": alert.measured_value,
                "threshold_value": alert.threshold_value,
                "occurrences": alert.occurrences,
                "raised_at": ensure_utc(alert.raised_at).isoformat(),
            },
        }
    )
