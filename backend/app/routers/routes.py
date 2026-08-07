"""Route registry endpoints (FR-05 … FR-08, UC-6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Route, Stop, Waypoint
from ..schemas import RouteCreate, RouteRead

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.post("", response_model=RouteRead, status_code=status.HTTP_201_CREATED)
def create_route(payload: RouteCreate, session: Session = Depends(get_session)) -> Route:
    existing = session.execute(
        select(Route).where(Route.code == payload.code)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"route code '{payload.code}' already exists"
        )

    route = Route(
        code=payload.code,
        name=payload.name,
        vehicle_type=payload.vehicle_type,
        speed_limit_kph=payload.speed_limit_kph,
        corridor_half_width_m=payload.corridor_half_width_m,
    )
    route.waypoints = [
        Waypoint(sequence=w.sequence, latitude=w.latitude, longitude=w.longitude)
        for w in sorted(payload.waypoints, key=lambda w: w.sequence)
    ]
    route.stops = [
        Stop(
            sequence=s.sequence,
            name=s.name,
            latitude=s.latitude,
            longitude=s.longitude,
            scheduled_offset_s=s.scheduled_offset_s,
        )
        for s in sorted(payload.stops, key=lambda s: s.sequence)
    ]
    session.add(route)
    session.commit()
    session.refresh(route)
    return route


@router.get("", response_model=list[RouteRead])
def list_routes(session: Session = Depends(get_session)) -> list[Route]:
    return list(session.execute(select(Route).order_by(Route.code)).scalars())


@router.get("/{code}", response_model=RouteRead)
def get_route(code: str, session: Session = Depends(get_session)) -> Route:
    route = session.execute(select(Route).where(Route.code == code)).scalar_one_or_none()
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no route '{code}'")
    return route


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(code: str, session: Session = Depends(get_session)) -> None:
    route = session.execute(select(Route).where(Route.code == code)).scalar_one_or_none()
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no route '{code}'")
    # Vehicles keep existing with route_id set to NULL (ON DELETE SET NULL);
    # route-dependent rules then skip, rather than the delete being blocked.
    session.delete(route)
    session.commit()
