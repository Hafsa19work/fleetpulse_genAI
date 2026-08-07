"""Fleet snapshot — the dashboard's initial paint (FR-29, UC-5)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from ..config import get_thresholds
from ..database import ensure_utc, get_session, utcnow
from ..enums import AlertStatus, Severity, VehicleStatus
from ..models import Alert, Route, Telemetry, Vehicle
from ..schemas import FleetSnapshot, VehicleSnapshot

router = APIRouter(prefix="/api/fleet", tags=["fleet"])

_STATE_BY_SEVERITY = {
    Severity.CRITICAL: "critical",
    Severity.WARNING: "warning",
    Severity.INFO: "info",
}


@router.get("/snapshot", response_model=FleetSnapshot)
def snapshot(session: Session = Depends(get_session)) -> FleetSnapshot:
    now = utcnow()
    timeout = get_thresholds().heartbeat_timeout_s

    # Last reading per vehicle, in one round trip rather than N+1 queries.
    latest_ts = (
        select(
            Telemetry.vehicle_id.label("vehicle_id"),
            func.max(Telemetry.recorded_at).label("max_ts"),
        )
        .group_by(Telemetry.vehicle_id)
        .subquery()
    )
    latest_rows = session.execute(
        select(Telemetry).join(
            latest_ts,
            (Telemetry.vehicle_id == latest_ts.c.vehicle_id)
            & (Telemetry.recorded_at == latest_ts.c.max_ts),
        )
    ).scalars()
    latest: dict[int, Telemetry] = {row.vehicle_id: row for row in latest_rows}

    open_counts: dict[int, int] = {}
    worst: dict[int, Severity] = {}
    alert_rows = session.execute(
        select(Alert.vehicle_id, Alert.severity, func.count())
        .where(Alert.status.in_((AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED)))
        .group_by(Alert.vehicle_id, Alert.severity)
    ).all()
    from ..enums import SEVERITY_ORDER

    for vehicle_id, severity, count in alert_rows:
        severity = Severity(severity)
        open_counts[vehicle_id] = open_counts.get(vehicle_id, 0) + count
        if vehicle_id not in worst or SEVERITY_ORDER[severity] > SEVERITY_ORDER[worst[vehicle_id]]:
            worst[vehicle_id] = severity

    vehicles = list(session.execute(select(Vehicle).order_by(Vehicle.code)).scalars())
    routes = list(session.execute(select(Route).order_by(Route.code)).scalars())
    route_codes = {route.id: route.code for route in routes}

    snapshots: list[VehicleSnapshot] = []
    counts = {"total": 0, "reporting": 0, "critical": 0, "warning": 0, "info": 0, "offline": 0, "ok": 0}

    for vehicle in vehicles:
        row = latest.get(vehicle.id)
        age = None
        if row is not None:
            age = (now - ensure_utc(row.recorded_at)).total_seconds()

        if vehicle.status is not VehicleStatus.ACTIVE:
            state = "offline"
        elif row is None or (age is not None and age > timeout):
            state = "offline"
        else:
            state = _STATE_BY_SEVERITY.get(worst.get(vehicle.id), "ok")

        counts["total"] += 1
        counts[state] = counts.get(state, 0) + 1
        if row is not None and age is not None and age <= timeout:
            counts["reporting"] += 1

        snapshots.append(
            VehicleSnapshot(
                code=vehicle.code,
                label=vehicle.label,
                vehicle_type=vehicle.vehicle_type,
                status=vehicle.status,
                route_code=route_codes.get(vehicle.route_id) if vehicle.route_id else None,
                state=state,
                latitude=row.latitude if row else None,
                longitude=row.longitude if row else None,
                speed_kph=row.speed_kph if row else None,
                heading_deg=row.heading_deg if row else None,
                engine_temp_c=row.engine_temp_c if row else None,
                fuel_pct=row.fuel_pct if row else None,
                cargo_temp_c=row.cargo_temp_c if row else None,
                last_seen_at=ensure_utc(row.recorded_at) if row else None,
                seconds_since_report=age,
                open_alerts=open_counts.get(vehicle.id, 0),
                worst_severity=worst.get(vehicle.id),
            )
        )

    return FleetSnapshot(generated_at=now, vehicles=snapshots, routes=routes, counts=counts)
