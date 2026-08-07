"""Health, statistics and maintenance endpoints (NFR-06, NFR-08)."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from .. import __version__
from ..config import settings
from ..database import get_session, utcnow
from ..enums import AlertStatus, VehicleStatus
from ..models import Alert, Telemetry, Vehicle
from ..schemas import HealthRead, PruneResult, StatsRead
from ..services.hub import hub
from ..services.ingestion import metrics

router = APIRouter(prefix="/api", tags=["ops"])


@router.get("/health", response_model=HealthRead)
def health(session: Session = Depends(get_session)) -> HealthRead:
    try:
        session.execute(text("SELECT 1"))
        db_state = "ok"
        overall = "ok"
    except Exception as exc:  # noqa: BLE001
        db_state = f"error: {type(exc).__name__}"
        overall = "degraded"

    return HealthRead(
        status=overall,
        version=__version__,
        database=db_state,
        uptime_seconds=metrics.uptime_seconds,
        readings_ingested=metrics.readings_ingested,
        alerts_raised=metrics.alerts_raised,
        websocket_clients=hub.client_count,
    )


@router.get("/stats", response_model=StatsRead)
def stats(session: Session = Depends(get_session)) -> StatsRead:
    total_vehicles = session.execute(select(func.count()).select_from(Vehicle)).scalar_one()
    active_vehicles = session.execute(
        select(func.count()).select_from(Vehicle).where(Vehicle.status == VehicleStatus.ACTIVE)
    ).scalar_one()
    telemetry_rows = session.execute(select(func.count()).select_from(Telemetry)).scalar_one()

    open_states = (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED)
    open_alerts = session.execute(
        select(func.count()).select_from(Alert).where(Alert.status.in_(open_states))
    ).scalar_one()

    by_severity = {
        str(sev.value if hasattr(sev, "value") else sev): count
        for sev, count in session.execute(
            select(Alert.severity, func.count())
            .where(Alert.status.in_(open_states))
            .group_by(Alert.severity)
        ).all()
    }
    by_rule = {
        code: count
        for code, count in session.execute(
            select(Alert.rule_code, func.count()).group_by(Alert.rule_code)
        ).all()
    }

    return StatsRead(
        vehicles=total_vehicles,
        active_vehicles=active_vehicles,
        telemetry_rows=telemetry_rows,
        open_alerts=open_alerts,
        alerts_by_severity=by_severity,
        alerts_by_rule=by_rule,
    )


@router.delete("/maintenance/prune", response_model=PruneResult)
def prune_telemetry(
    older_than_days: int = Query(default=None, ge=1, le=365),
    session: Session = Depends(get_session),
) -> PruneResult:
    """Delete aged telemetry (NFR-08). Alerts are never pruned — they are the audit trail."""
    days = older_than_days or settings.retention_days
    cutoff = utcnow() - timedelta(days=days)
    result = session.execute(delete(Telemetry).where(Telemetry.recorded_at < cutoff))
    session.commit()
    return PruneResult(deleted_rows=result.rowcount or 0, older_than_days=days)
