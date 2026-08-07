"""Pydantic v2 request/response schemas — the HTTP contract.

Validation that can be expressed declaratively (coordinate ranges, non-negative
speed, batch size) lives here so an invalid payload is rejected at the edge with a
422 and never reaches the database or the rule engine (FR-11).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import AlertStatus, DeliveryStatus, Severity, VehicleStatus, VehicleType

Lat = Field(ge=-90, le=90)
Lon = Field(ge=-180, le=180)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- routes


class WaypointIn(BaseModel):
    sequence: int = Field(ge=0)
    latitude: float = Lat
    longitude: float = Lon


class StopIn(BaseModel):
    sequence: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Lat
    longitude: float = Lon
    scheduled_offset_s: int = Field(ge=0)


class RouteCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    vehicle_type: VehicleType
    speed_limit_kph: float = Field(default=60.0, gt=0)
    corridor_half_width_m: float = Field(default=150.0, gt=0)
    waypoints: list[WaypointIn] = Field(default_factory=list)
    stops: list[StopIn] = Field(default_factory=list)

    @field_validator("waypoints")
    @classmethod
    def _unique_sequences(cls, value: list[WaypointIn]) -> list[WaypointIn]:
        seqs = [w.sequence for w in value]
        if len(seqs) != len(set(seqs)):
            raise ValueError("waypoint sequence values must be unique")
        return value


class WaypointRead(ORMModel):
    sequence: int
    latitude: float
    longitude: float


class StopRead(ORMModel):
    sequence: int
    name: str
    latitude: float
    longitude: float
    scheduled_offset_s: int


class RouteRead(ORMModel):
    id: int
    code: str
    name: str
    vehicle_type: VehicleType
    speed_limit_kph: float
    corridor_half_width_m: float
    waypoints: list[WaypointRead] = []
    stops: list[StopRead] = []


# ------------------------------------------------------------------------- vehicles


class VehicleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=120)
    vehicle_type: VehicleType
    status: VehicleStatus = VehicleStatus.ACTIVE
    route_id: int | None = None
    cargo_temp_min_c: float | None = None
    cargo_temp_max_c: float | None = None
    trip_started_at: datetime | None = None

    @field_validator("cargo_temp_max_c")
    @classmethod
    def _band_ordered(cls, value: float | None, info) -> float | None:  # noqa: ANN001
        lo = info.data.get("cargo_temp_min_c")
        if value is not None and lo is not None and value < lo:
            raise ValueError("cargo_temp_max_c must be >= cargo_temp_min_c")
        return value


class VehicleUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    status: VehicleStatus | None = None
    route_id: int | None = None
    cargo_temp_min_c: float | None = None
    cargo_temp_max_c: float | None = None
    trip_started_at: datetime | None = None


class VehicleRead(ORMModel):
    id: int
    code: str
    label: str
    vehicle_type: VehicleType
    status: VehicleStatus
    route_id: int | None
    cargo_temp_min_c: float | None
    cargo_temp_max_c: float | None
    trip_started_at: datetime | None


# ------------------------------------------------------------------------ telemetry


class TelemetryCreate(BaseModel):
    vehicle_code: str = Field(min_length=1, max_length=32)
    recorded_at: datetime
    latitude: float = Lat
    longitude: float = Lon
    speed_kph: float = Field(ge=0)
    heading_deg: float | None = Field(default=None, ge=0, le=360)
    engine_temp_c: float | None = None
    fuel_pct: float | None = Field(default=None, ge=0, le=100)
    cargo_temp_c: float | None = None
    odometer_km: float | None = Field(default=None, ge=0)


class TelemetryBatch(BaseModel):
    readings: list[TelemetryCreate] = Field(min_length=1, max_length=500)


class TelemetryRead(ORMModel):
    id: int
    vehicle_id: int
    recorded_at: datetime
    latitude: float
    longitude: float
    speed_kph: float
    heading_deg: float | None
    engine_temp_c: float | None
    fuel_pct: float | None
    cargo_temp_c: float | None
    odometer_km: float | None


# ----------------------------------------------------------------------- alerts


class AlertRead(ORMModel):
    id: int
    vehicle_id: int
    telemetry_id: int | None
    rule_code: str
    severity: Severity
    status: AlertStatus
    message: str
    measured_value: float | None
    threshold_value: float | None
    occurrences: int
    raised_at: datetime
    last_seen_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    vehicle_code: str | None = None
    duration_seconds: float | None = None


class AlertPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AlertRead]


# ---------------------------------------------------------------------- ingestion


class IngestResult(BaseModel):
    vehicle_code: str
    reading_id: int | None
    duplicate: bool = False
    evaluated: bool = True
    alerts_created: list[AlertRead] = []
    alerts_updated: list[AlertRead] = []
    failed_rules: dict[str, str] = {}


class BatchIngestResult(BaseModel):
    accepted: int
    duplicates: int
    rejected: int
    alerts_created: int
    errors: list[str] = []


# ------------------------------------------------------------------------- fleet


class VehicleSnapshot(BaseModel):
    code: str
    label: str
    vehicle_type: VehicleType
    status: VehicleStatus
    route_code: str | None = None
    state: str  # ok | info | warning | critical | offline
    latitude: float | None = None
    longitude: float | None = None
    speed_kph: float | None = None
    heading_deg: float | None = None
    engine_temp_c: float | None = None
    fuel_pct: float | None = None
    cargo_temp_c: float | None = None
    last_seen_at: datetime | None = None
    seconds_since_report: float | None = None
    open_alerts: int = 0
    worst_severity: Severity | None = None


class FleetSnapshot(BaseModel):
    generated_at: datetime
    vehicles: list[VehicleSnapshot]
    routes: list[RouteRead]
    counts: dict[str, int]


# ------------------------------------------------------------------------ config


class ThresholdsRead(BaseModel):
    overspeed_tolerance_kph: float
    engine_warn_c: float
    engine_critical_c: float
    fuel_low_pct: float
    fuel_critical_pct: float
    harsh_braking_delta_kph: float
    harsh_braking_window_s: float
    heartbeat_timeout_s: float
    schedule_grace_s: float
    schedule_min_speed_kph: float
    alert_cooldown_s: float


class ThresholdsUpdate(BaseModel):
    """Partial update — only the supplied fields change (FR-22)."""

    overspeed_tolerance_kph: float | None = Field(default=None, ge=0)
    engine_warn_c: float | None = None
    engine_critical_c: float | None = None
    fuel_low_pct: float | None = Field(default=None, ge=0, le=100)
    fuel_critical_pct: float | None = Field(default=None, ge=0, le=100)
    harsh_braking_delta_kph: float | None = Field(default=None, gt=0)
    harsh_braking_window_s: float | None = Field(default=None, gt=0)
    heartbeat_timeout_s: float | None = Field(default=None, gt=0)
    schedule_grace_s: float | None = Field(default=None, ge=0)
    schedule_min_speed_kph: float | None = Field(default=None, ge=0)
    alert_cooldown_s: float | None = Field(default=None, ge=0)


class RuleInfo(BaseModel):
    code: str
    description: str
    applies_to: list[VehicleType]


# ------------------------------------------------------------------- ops / health


class HealthRead(BaseModel):
    status: str
    version: str
    database: str
    uptime_seconds: float
    readings_ingested: int
    alerts_raised: int
    websocket_clients: int


class StatsRead(BaseModel):
    vehicles: int
    active_vehicles: int
    telemetry_rows: int
    open_alerts: int
    alerts_by_severity: dict[str, int]
    alerts_by_rule: dict[str, int]


class PruneResult(BaseModel):
    deleted_rows: int
    older_than_days: int


class DeliveryRead(ORMModel):
    id: int
    vehicle_id: int
    reference: str
    destination_label: str
    destination_lat: float
    destination_lon: float
    due_at: datetime
    status: DeliveryStatus
