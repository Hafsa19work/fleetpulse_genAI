"""The rule engine and the ORM → domain adapters.

`evaluate` itself is pure. The adapters below (`to_reading`, `to_vehicle_ctx`,
`to_route_ctx`) are the only place where SQLAlchemy objects are converted into the
frozen dataclasses the rules consume — the boundary between Layer 4 and Layer 3 in
docs/03-architecture.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..config import Thresholds
from ..database import ensure_utc
from ..enums import VehicleStatus
from ..models import Route, Telemetry, Vehicle
from ..rules import RULES, AlertCandidate, EvalContext, Reading, RouteCtx, StopCtx, VehicleCtx


@dataclass(slots=True)
class EvaluationResult:
    candidates: list[AlertCandidate] = field(default_factory=list)
    skipped_rules: list[str] = field(default_factory=list)
    failed_rules: dict[str, str] = field(default_factory=dict)


def evaluate(ctx: EvalContext, rules=RULES) -> EvaluationResult:
    """Run every applicable rule. Pure: no I/O, no clock.

    A rule that raises is recorded in `failed_rules` and the remaining rules still
    run (NFR-09). A bug in the cargo rule must never be able to suppress an
    overheating alert.
    """
    result = EvaluationResult()
    for rule in rules:
        if not rule.applicable(ctx.vehicle.vehicle_type):
            result.skipped_rules.append(rule.code)
            continue
        try:
            result.candidates.extend(rule.fn(ctx))
        except Exception as exc:  # noqa: BLE001 — isolation is the point
            result.failed_rules[rule.code] = f"{type(exc).__name__}: {exc}"
    return result


# --------------------------------------------------------------------------
# ORM -> domain adapters
# --------------------------------------------------------------------------


def to_reading(row: Telemetry) -> Reading:
    return Reading(
        recorded_at=ensure_utc(row.recorded_at),
        latitude=row.latitude,
        longitude=row.longitude,
        speed_kph=row.speed_kph,
        heading_deg=row.heading_deg,
        engine_temp_c=row.engine_temp_c,
        fuel_pct=row.fuel_pct,
        cargo_temp_c=row.cargo_temp_c,
        odometer_km=row.odometer_km,
    )


def to_vehicle_ctx(vehicle: Vehicle) -> VehicleCtx:
    return VehicleCtx(
        code=vehicle.code,
        label=vehicle.label,
        vehicle_type=vehicle.vehicle_type,
        cargo_temp_min_c=vehicle.cargo_temp_min_c,
        cargo_temp_max_c=vehicle.cargo_temp_max_c,
        trip_started_at=ensure_utc(vehicle.trip_started_at),
    )


def to_route_ctx(route: Route | None) -> RouteCtx | None:
    if route is None:
        return None
    return RouteCtx(
        code=route.code,
        speed_limit_kph=route.speed_limit_kph,
        corridor_half_width_m=route.corridor_half_width_m,
        polyline=tuple((w.latitude, w.longitude) for w in route.waypoints),
        stops=tuple(
            StopCtx(
                sequence=s.sequence,
                name=s.name,
                latitude=s.latitude,
                longitude=s.longitude,
                scheduled_offset_s=s.scheduled_offset_s,
            )
            for s in route.stops
        ),
    )


def build_context(
    *,
    vehicle: Vehicle,
    reading: Reading,
    now: datetime,
    thresholds: Thresholds,
    previous: Reading | None = None,
) -> EvalContext:
    return EvalContext(
        reading=reading,
        vehicle=to_vehicle_ctx(vehicle),
        now=now,
        thresholds=thresholds,
        route=to_route_ctx(vehicle.route),
        previous=previous,
    )


def is_evaluable(vehicle: Vehicle) -> bool:
    """FR-04: rules do not run for vehicles that are not in service."""
    return vehicle.status is VehicleStatus.ACTIVE
