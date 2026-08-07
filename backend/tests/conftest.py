"""Shared fixtures.

AI-generated from prompts P-17 / P-18 (see PROMPT_LOG.md).
Manual corrections after generation:
  * the first generated version used the real on-disk database; replaced with an
    in-memory SQLite engine on a StaticPool so tests neither pollute nor depend on
    `fleetpulse.db`;
  * added the `reset_thresholds` autouse fixture — the threshold set is process
    global, so a test that tuned it via the API leaked into later tests.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

# Must be set before app modules import and build their engine.
os.environ.setdefault("FLEETPULSE_DATABASE_URL", "sqlite://")
os.environ.setdefault("FLEETPULSE_DISABLE_SWEEPER", "1")
# Forced, not defaulted: the Docker image sets FLEETPULSE_SERVE_STATIC=1, which
# mounts the SPA at "/" and would change what the API tests see there. The suite
# must assert the same behaviour whether it runs on a laptop or in the container.
os.environ["FLEETPULSE_SERVE_STATIC"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import Thresholds, reset_thresholds as _reset_thresholds  # noqa: E402
from app.database import Base, get_session  # noqa: E402
from app.enums import VehicleType  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Route, Stop, Vehicle, Waypoint  # noqa: E402
from app.rules import Reading, RouteCtx, StopCtx, VehicleCtx  # noqa: E402
from app.rules.base import EvalContext  # noqa: E402

T0 = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)

# A short straight corridor near Karachi, used by the geometry-sensitive rules.
LINE = [(24.8600, 67.0000), (24.8600, 67.0500)]


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def _override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_thresholds():
    """Thresholds are process-global; restore defaults around every test."""
    _reset_thresholds()
    yield
    _reset_thresholds()


@pytest.fixture
def thresholds() -> Thresholds:
    return Thresholds()


# --------------------------------------------------------------------------
# Pure-domain builders — no database involved, which is the whole point of the
# pure rule layer (docs/03-architecture.md §3).
# --------------------------------------------------------------------------


def make_reading(**overrides) -> Reading:
    data = {
        "recorded_at": T0,
        "latitude": 24.8600,
        "longitude": 67.0100,
        "speed_kph": 40.0,
        "heading_deg": 90.0,
        "engine_temp_c": 88.0,
        "fuel_pct": 70.0,
        "cargo_temp_c": None,
        "odometer_km": 12_345.0,
    }
    data.update(overrides)
    return Reading(**data)


def make_vehicle(**overrides) -> VehicleCtx:
    data = {
        "code": "BUS-01",
        "label": "Bus 01",
        "vehicle_type": VehicleType.BUS,
        "cargo_temp_min_c": None,
        "cargo_temp_max_c": None,
        "trip_started_at": None,
    }
    data.update(overrides)
    return VehicleCtx(**data)


def make_truck(**overrides) -> VehicleCtx:
    data = {
        "code": "TRK-01",
        "label": "Reefer 01",
        "vehicle_type": VehicleType.TRUCK,
        "cargo_temp_min_c": -20.0,
        "cargo_temp_max_c": -15.0,
    }
    data.update(overrides)
    return make_vehicle(**data)


def make_route(**overrides) -> RouteCtx:
    data = {
        "code": "R-1",
        "speed_limit_kph": 60.0,
        "corridor_half_width_m": 150.0,
        "polyline": tuple(LINE),
        "stops": (),
    }
    data.update(overrides)
    return RouteCtx(**data)


def make_ctx(**overrides) -> EvalContext:
    data = {
        "reading": make_reading(),
        "vehicle": make_vehicle(),
        "now": T0,
        "thresholds": Thresholds(),
        "route": make_route(),
        "previous": None,
    }
    data.update(overrides)
    return EvalContext(**data)


def make_stop(sequence: int, lat: float, lon: float, offset_s: int, name: str = "Stop") -> StopCtx:
    return StopCtx(
        sequence=sequence,
        name=name,
        latitude=lat,
        longitude=lon,
        scheduled_offset_s=offset_s,
    )


# --------------------------------------------------------------------------
# ORM builders for the integration tests
# --------------------------------------------------------------------------


def seed_route(session, code="R-1", vehicle_type=VehicleType.BUS, **kwargs) -> Route:
    route = Route(
        code=code,
        name=kwargs.pop("name", f"Route {code}"),
        vehicle_type=vehicle_type,
        speed_limit_kph=kwargs.pop("speed_limit_kph", 60.0),
        corridor_half_width_m=kwargs.pop("corridor_half_width_m", 150.0),
    )
    route.waypoints = [
        Waypoint(sequence=i, latitude=lat, longitude=lon)
        for i, (lat, lon) in enumerate(kwargs.pop("polyline", LINE))
    ]
    route.stops = [
        Stop(
            sequence=s.sequence,
            name=s.name,
            latitude=s.latitude,
            longitude=s.longitude,
            scheduled_offset_s=s.scheduled_offset_s,
        )
        for s in kwargs.pop("stops", [])
    ]
    session.add(route)
    session.commit()
    session.refresh(route)
    return route


def seed_vehicle(session, code="BUS-01", route=None, **kwargs) -> Vehicle:
    vehicle = Vehicle(
        code=code,
        label=kwargs.pop("label", code),
        vehicle_type=kwargs.pop("vehicle_type", VehicleType.BUS),
        route_id=route.id if route is not None else None,
        **kwargs,
    )
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle


def telemetry_payload(code="BUS-01", offset_s: float = 0.0, **overrides) -> dict:
    payload = {
        "vehicle_code": code,
        "recorded_at": (datetime.now(UTC) + timedelta(seconds=offset_s)).isoformat(),
        "latitude": 24.8600,
        "longitude": 67.0100,
        "speed_kph": 40.0,
        "heading_deg": 90.0,
        "engine_temp_c": 88.0,
        "fuel_pct": 70.0,
    }
    payload.update(overrides)
    return payload
