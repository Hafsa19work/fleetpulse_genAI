"""Configuration and runtime-mutable rule thresholds.

Every number the rule engine compares against lives in `Thresholds`. Nothing in
`app/rules/` reads a module-level constant, which is what makes FR-22 (tune
thresholds without a code change) and NFR-03 (testable rules) both achievable:
a test constructs its own `Thresholds` instead of monkey-patching globals.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, float(default)))


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Immutable threshold set handed to the rule engine on every evaluation."""

    # FR-14 overspeed
    overspeed_tolerance_kph: float = 5.0
    # FR-15 engine temperature
    engine_warn_c: float = 105.0
    engine_critical_c: float = 115.0
    # FR-16 fuel
    fuel_low_pct: float = 20.0
    fuel_critical_pct: float = 10.0
    # FR-19 harsh braking
    harsh_braking_delta_kph: float = 25.0
    harsh_braking_window_s: float = 15.0
    # FR-18 offline heartbeat
    heartbeat_timeout_s: float = 120.0
    # FR-20 schedule delay (buses)
    schedule_grace_s: float = 300.0
    # Floor on the *average* speed since the trip began, below which the ETA
    # projection is treated as meaningless and the rule reports the delay already
    # accrued instead. Applying this to the instantaneous speed was defect D-07, and
    # was not enough on its own — see D-09 in docs/09-test-report.md.
    schedule_min_speed_kph: float = 5.0
    # Alert deduplication window (FR-25)
    alert_cooldown_s: float = 180.0

    @classmethod
    def from_env(cls) -> "Thresholds":
        return cls(
            overspeed_tolerance_kph=_env_float("FLEETPULSE_OVERSPEED_TOLERANCE_KPH", 5.0),
            engine_warn_c=_env_float("FLEETPULSE_ENGINE_WARN_C", 105.0),
            engine_critical_c=_env_float("FLEETPULSE_ENGINE_CRITICAL_C", 115.0),
            fuel_low_pct=_env_float("FLEETPULSE_FUEL_LOW_PCT", 20.0),
            fuel_critical_pct=_env_float("FLEETPULSE_FUEL_CRITICAL_PCT", 10.0),
            harsh_braking_delta_kph=_env_float("FLEETPULSE_HARSH_BRAKING_DELTA_KPH", 25.0),
            harsh_braking_window_s=_env_float("FLEETPULSE_HARSH_BRAKING_WINDOW_S", 15.0),
            heartbeat_timeout_s=_env_float("FLEETPULSE_HEARTBEAT_TIMEOUT_S", 120.0),
            schedule_grace_s=_env_float("FLEETPULSE_SCHEDULE_GRACE_S", 300.0),
            alert_cooldown_s=_env_float("FLEETPULSE_ALERT_COOLDOWN_S", 180.0),
        )

    def merged(self, **changes: float) -> "Thresholds":
        """Return a copy with the given fields replaced, ignoring None values."""
        clean = {k: v for k, v in changes.items() if v is not None}
        unknown = set(clean) - {f for f in self.__dataclass_fields__}
        if unknown:
            raise ValueError(f"unknown threshold field(s): {sorted(unknown)}")
        return replace(self, **clean)


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = os.getenv("FLEETPULSE_DATABASE_URL", "sqlite:///./fleetpulse.db")
    retention_days: int = _env_int("FLEETPULSE_RETENTION_DAYS", 7)
    offline_sweep_interval_s: float = _env_float("FLEETPULSE_OFFLINE_SWEEP_INTERVAL_S", 20.0)
    max_batch_size: int = _env_int("FLEETPULSE_MAX_BATCH_SIZE", 500)
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    gtfs_feed_url: str | None = os.getenv("FLEETPULSE_GTFS_FEED_URL")


settings = Settings()

# The live threshold set. `PUT /api/config/thresholds` swaps this object wholesale;
# because Thresholds is frozen, an in-flight evaluation can never see a half-applied
# update — it keeps the object it was handed.
_active_thresholds: Thresholds = Thresholds.from_env()


def get_thresholds() -> Thresholds:
    return _active_thresholds


def set_thresholds(new: Thresholds) -> Thresholds:
    global _active_thresholds
    _active_thresholds = new
    return _active_thresholds


def reset_thresholds() -> Thresholds:
    return set_thresholds(Thresholds.from_env())
