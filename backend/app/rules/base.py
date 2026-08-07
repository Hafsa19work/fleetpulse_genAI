"""Domain value objects and the rule contract.

This module and everything else in `app/rules/` form the pure core described in
docs/03-architecture.md §3. Nothing here imports SQLAlchemy, FastAPI or reads the
clock — the evaluation timestamp arrives as `EvalContext.now`. That property is
what lets the AI-generated tests in backend/tests/test_rules_*.py construct a
context literal and assert on the result with no mocks and no database.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from ..enums import Severity, VehicleType

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Reading:
    """One telemetry sample, detached from the ORM."""

    recorded_at: datetime
    latitude: float
    longitude: float
    speed_kph: float
    heading_deg: float | None = None
    engine_temp_c: float | None = None
    fuel_pct: float | None = None
    cargo_temp_c: float | None = None
    odometer_km: float | None = None

    @property
    def position(self) -> Point:
        return (self.latitude, self.longitude)


@dataclass(frozen=True, slots=True)
class StopCtx:
    sequence: int
    name: str
    latitude: float
    longitude: float
    scheduled_offset_s: int

    @property
    def position(self) -> Point:
        return (self.latitude, self.longitude)


@dataclass(frozen=True, slots=True)
class RouteCtx:
    code: str
    speed_limit_kph: float
    corridor_half_width_m: float
    polyline: tuple[Point, ...] = ()
    stops: tuple[StopCtx, ...] = ()


@dataclass(frozen=True, slots=True)
class VehicleCtx:
    code: str
    label: str
    vehicle_type: VehicleType
    cargo_temp_min_c: float | None = None
    cargo_temp_max_c: float | None = None
    trip_started_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AlertCandidate:
    """A rule's verdict. Carries everything the alert row needs, nothing more."""

    rule_code: str
    severity: Severity
    message: str
    measured_value: float | None = None
    threshold_value: float | None = None


@dataclass(frozen=True, slots=True)
class EvalContext:
    """Everything a rule is allowed to see."""

    reading: Reading
    vehicle: VehicleCtx
    now: datetime
    thresholds: "Thresholds"  # noqa: F821 — app.config.Thresholds, imported lazily below
    route: RouteCtx | None = None
    previous: Reading | None = None


# A rule is a pure function from context to zero or more candidates.
RuleFn = Callable[[EvalContext], list[AlertCandidate]]


@dataclass(frozen=True, slots=True)
class Rule:
    """A registered rule plus the vehicle types it applies to.

    Gating is data rather than an `if` inside the engine, so adding a
    truck-only rule never touches the engine (docs/03-architecture.md §6).
    """

    code: str
    fn: RuleFn
    applies_to: frozenset[VehicleType] = field(
        default_factory=lambda: frozenset(VehicleType)
    )
    description: str = ""

    def applicable(self, vehicle_type: VehicleType) -> bool:
        return vehicle_type in self.applies_to
