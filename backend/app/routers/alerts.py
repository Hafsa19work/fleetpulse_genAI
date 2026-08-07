"""Alert query and lifecycle endpoints (FR-24 … FR-28, UC-4)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import ensure_utc, get_session, utcnow
from ..enums import AlertStatus, Severity
from ..models import Alert, Vehicle
from ..schemas import AlertPage, AlertRead
from ..services import alerts as alert_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _to_read(alert: Alert, vehicle_code: str | None) -> AlertRead:
    for attr in ("raised_at", "last_seen_at", "acknowledged_at", "resolved_at"):
        setattr(alert, attr, ensure_utc(getattr(alert, attr)))
    data = AlertRead.model_validate(alert)
    return data.model_copy(
        update={
            "vehicle_code": vehicle_code,
            "duration_seconds": alert_service.duration_seconds(alert),
        }
    )


@router.get("", response_model=AlertPage)
def list_alerts(
    vehicle_code: str | None = None,
    severity: Severity | None = None,
    alert_status: AlertStatus | None = Query(default=None, alias="status"),
    rule_code: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> AlertPage:
    stmt = select(Alert, Vehicle.code).join(Vehicle, Alert.vehicle_id == Vehicle.id)
    count_stmt = select(func.count()).select_from(Alert).join(Vehicle, Alert.vehicle_id == Vehicle.id)

    def _apply(statement):  # noqa: ANN001, ANN202
        if vehicle_code:
            statement = statement.where(Vehicle.code == vehicle_code)
        if severity:
            statement = statement.where(Alert.severity == severity)
        if alert_status:
            statement = statement.where(Alert.status == alert_status)
        if rule_code:
            statement = statement.where(Alert.rule_code == rule_code)
        if since:
            statement = statement.where(Alert.raised_at >= since)
        if until:
            statement = statement.where(Alert.raised_at <= until)
        return statement

    total = session.execute(_apply(count_stmt)).scalar_one()
    rows = session.execute(
        _apply(stmt).order_by(Alert.raised_at.desc()).limit(limit).offset(offset)
    ).all()

    return AlertPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[_to_read(alert, code) for alert, code in rows],
    )


def _get_alert(session: Session, alert_id: int) -> tuple[Alert, str]:
    row = session.execute(
        select(Alert, Vehicle.code)
        .join(Vehicle, Alert.vehicle_id == Vehicle.id)
        .where(Alert.id == alert_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no alert {alert_id}")
    return row[0], row[1]


@router.get("/{alert_id}", response_model=AlertRead)
def get_alert(alert_id: int, session: Session = Depends(get_session)) -> AlertRead:
    alert, code = _get_alert(session, alert_id)
    return _to_read(alert, code)


@router.post("/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(alert_id: int, session: Session = Depends(get_session)) -> AlertRead:
    alert, code = _get_alert(session, alert_id)
    try:
        alert_service.acknowledge(alert, utcnow())
    except alert_service.AlertTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    session.commit()
    return _to_read(alert, code)


@router.post("/{alert_id}/resolve", response_model=AlertRead)
def resolve_alert(alert_id: int, session: Session = Depends(get_session)) -> AlertRead:
    alert, code = _get_alert(session, alert_id)
    try:
        alert_service.resolve(alert, utcnow())
    except alert_service.AlertTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    session.commit()
    return _to_read(alert, code)
