"""SQLAlchemy 2.0 declarative models.

Mirrors docs/04-database-design.md. These classes carry persistence structure and
constraints only — no business logic. Rule decisions live in app/rules/.
"""

from __future__ import annotations

import enum
from datetime import datetime  # noqa: TC003  (needed at runtime by Mapped[...])

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base, utcnow
from .enums import (
    AlertStatus,
    DeliveryStatus,
    Severity,
    VehicleStatus,
    VehicleType,
)

__all__ = [
    "Alert",
    "AlertStatus",
    "Delivery",
    "DeliveryStatus",
    "Route",
    "Severity",
    "Stop",
    "Telemetry",
    "Vehicle",
    "VehicleStatus",
    "VehicleType",
    "Waypoint",
]


def _enum_col(enum_cls: type[enum.Enum]) -> Enum:
    # values_callable stores the lowercase *values* ("bus") rather than the member
    # names ("BUS"), so the database contents match the API contract exactly.
    return Enum(enum_cls, values_callable=lambda e: [m.value for m in e], native_enum=False)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    vehicle_type: Mapped[VehicleType] = mapped_column(_enum_col(VehicleType))
    speed_limit_kph: Mapped[float] = mapped_column(Float, default=60.0)
    corridor_half_width_m: Mapped[float] = mapped_column(Float, default=150.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    waypoints: Mapped[list["Waypoint"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="Waypoint.sequence",
        lazy="selectin",
    )
    stops: Mapped[list["Stop"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="Stop.sequence",
        lazy="selectin",
    )
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="route")

    __table_args__ = (
        CheckConstraint("speed_limit_kph > 0", name="ck_route_speed_limit_positive"),
        CheckConstraint("corridor_half_width_m > 0", name="ck_route_corridor_positive"),
    )


class Waypoint(Base):
    __tablename__ = "waypoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    route: Mapped[Route] = relationship(back_populates="waypoints")

    __table_args__ = (
        UniqueConstraint("route_id", "sequence", name="uq_waypoint_route_seq"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_waypoint_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_waypoint_lon"),
        Index("ix_waypoints_route_seq", "route_id", "sequence"),
    )


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    scheduled_offset_s: Mapped[int] = mapped_column(Integer)

    route: Mapped[Route] = relationship(back_populates="stops")

    __table_args__ = (
        UniqueConstraint("route_id", "sequence", name="uq_stop_route_seq"),
        CheckConstraint("scheduled_offset_s >= 0", name="ck_stop_offset_non_negative"),
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    vehicle_type: Mapped[VehicleType] = mapped_column(_enum_col(VehicleType))
    status: Mapped[VehicleStatus] = mapped_column(
        _enum_col(VehicleStatus), default=VehicleStatus.ACTIVE
    )
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL"), nullable=True
    )
    # Trucks only: permitted refrigeration band. Both NULL => cargo rule not applicable.
    cargo_temp_min_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    cargo_temp_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Buses only: when the current trip began, the origin for scheduled stop offsets.
    trip_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    route: Mapped[Route | None] = relationship(back_populates="vehicles")
    telemetry: Mapped[list["Telemetry"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
    deliveries: Mapped[list["Delivery"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed_kph: Mapped[float] = mapped_column(Float)
    heading_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cargo_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    odometer_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    vehicle: Mapped[Vehicle] = relationship(back_populates="telemetry")

    __table_args__ = (
        # Idempotent ingestion (FR-13) enforced by the database, not by an
        # application-level check that would race under concurrent posts.
        UniqueConstraint("vehicle_id", "recorded_at", name="uq_telemetry_vehicle_ts"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_telemetry_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_telemetry_lon"),
        CheckConstraint("speed_kph >= 0", name="ck_telemetry_speed_non_negative"),
        Index("ix_telemetry_vehicle_time", "vehicle_id", "recorded_at"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    telemetry_id: Mapped[int | None] = mapped_column(
        ForeignKey("telemetry.id", ondelete="SET NULL"), nullable=True
    )
    rule_code: Mapped[str] = mapped_column(String(32))
    severity: Mapped[Severity] = mapped_column(_enum_col(Severity))
    status: Mapped[AlertStatus] = mapped_column(_enum_col(AlertStatus), default=AlertStatus.OPEN)
    message: Mapped[str] = mapped_column(String(255))
    # Snapshotted, not joined: an alert must stay interpretable after its source
    # telemetry has been pruned, and must record the threshold as it was at raise time.
    measured_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    vehicle: Mapped[Vehicle] = relationship(back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_vehicle_rule_status", "vehicle_id", "rule_code", "status"),
        Index("ix_alerts_raised_at", "raised_at"),
    )


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    reference: Mapped[str] = mapped_column(String(64))
    destination_label: Mapped[str] = mapped_column(String(120))
    destination_lat: Mapped[float] = mapped_column(Float)
    destination_lon: Mapped[float] = mapped_column(Float)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[DeliveryStatus] = mapped_column(
        _enum_col(DeliveryStatus), default=DeliveryStatus.PENDING
    )

    vehicle: Mapped[Vehicle] = relationship(back_populates="deliveries")
