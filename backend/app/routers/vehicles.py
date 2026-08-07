"""Vehicle registry and telemetry history endpoints (FR-01 … FR-04, FR-12)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import ensure_utc, get_session
from ..models import Route, Telemetry, Vehicle
from ..schemas import TelemetryRead, VehicleCreate, VehicleRead, VehicleUpdate

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


def _get_vehicle_or_404(session: Session, code: str) -> Vehicle:
    vehicle = session.execute(
        select(Vehicle).where(Vehicle.code == code)
    ).scalar_one_or_none()
    if vehicle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no vehicle '{code}'")
    return vehicle


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, session: Session = Depends(get_session)) -> Vehicle:
    existing = session.execute(
        select(Vehicle).where(Vehicle.code == payload.code)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"vehicle code '{payload.code}' already exists",
        )
    if payload.route_id is not None and session.get(Route, payload.route_id) is None:
        raise HTTPException(
            422,
            detail=f"route id {payload.route_id} does not exist",
        )

    vehicle = Vehicle(**payload.model_dump())
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle


@router.get("", response_model=list[VehicleRead])
def list_vehicles(
    vehicle_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
) -> list[Vehicle]:
    stmt = select(Vehicle).order_by(Vehicle.code)
    if vehicle_type:
        stmt = stmt.where(Vehicle.vehicle_type == vehicle_type)
    if status_filter:
        stmt = stmt.where(Vehicle.status == status_filter)
    return list(session.execute(stmt).scalars())


@router.get("/{code}", response_model=VehicleRead)
def get_vehicle(code: str, session: Session = Depends(get_session)) -> Vehicle:
    return _get_vehicle_or_404(session, code)


@router.patch("/{code}", response_model=VehicleRead)
def update_vehicle(
    code: str, payload: VehicleUpdate, session: Session = Depends(get_session)
) -> Vehicle:
    vehicle = _get_vehicle_or_404(session, code)
    changes = payload.model_dump(exclude_unset=True)
    if "route_id" in changes and changes["route_id"] is not None:
        if session.get(Route, changes["route_id"]) is None:
            raise HTTPException(
                422,
                detail=f"route id {changes['route_id']} does not exist",
            )
    for key, value in changes.items():
        setattr(vehicle, key, value)
    session.commit()
    session.refresh(vehicle)
    return vehicle


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(code: str, session: Session = Depends(get_session)) -> None:
    vehicle = _get_vehicle_or_404(session, code)
    session.delete(vehicle)
    session.commit()


@router.get("/{code}/telemetry", response_model=list[TelemetryRead])
def vehicle_telemetry(
    code: str,
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[Telemetry]:
    """Most recent readings first (FR-12). Served by ix_telemetry_vehicle_time."""
    vehicle = _get_vehicle_or_404(session, code)
    rows = list(
        session.execute(
            select(Telemetry)
            .where(Telemetry.vehicle_id == vehicle.id)
            .order_by(Telemetry.recorded_at.desc())
            .limit(limit)
        ).scalars()
    )
    for row in rows:
        row.recorded_at = ensure_utc(row.recorded_at)
    return rows
