"""Offline sweeper and alert-service internals (FR-18, US-02, D-7).

AI-generated from prompt P-18. These exercise the service layer directly, without
HTTP, because the sweeper is driven by a background task rather than a request.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import Thresholds
from app.enums import AlertStatus, Severity, VehicleStatus
from app.models import Alert, Telemetry
from app.services import alerts as alert_service
from app.services.ingestion import sweep_offline
from conftest import seed_route, seed_vehicle

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def add_reading(session, vehicle, *, at, speed=30.0):
    row = Telemetry(
        vehicle_id=vehicle.id,
        recorded_at=at,
        latitude=24.86,
        longitude=67.01,
        speed_kph=speed,
        received_at=at,
    )
    session.add(row)
    session.commit()
    return row


def test_sweeper_ignores_a_vehicle_that_has_never_reported(session):
    seed_vehicle(session, code="BUS-01")
    assert sweep_offline(session, now=NOW) == []


def test_sweeper_ignores_a_recently_reporting_vehicle(session):
    vehicle = seed_vehicle(session, code="BUS-01")
    add_reading(session, vehicle, at=NOW - timedelta(seconds=30))
    assert sweep_offline(session, now=NOW) == []


def test_sweeper_raises_for_a_silent_vehicle(session):
    vehicle = seed_vehicle(session, code="BUS-01")
    add_reading(session, vehicle, at=NOW - timedelta(minutes=10))

    created = sweep_offline(session, now=NOW)
    assert len(created) == 1
    assert created[0].rule_code == "VEHICLE_OFFLINE"
    assert created[0].severity is Severity.CRITICAL
    assert created[0].telemetry_id is None  # not attributable to any single reading


def test_sweeper_skips_vehicles_that_are_not_in_service(session):
    vehicle = seed_vehicle(session, code="BUS-01", status=VehicleStatus.MAINTENANCE)
    add_reading(session, vehicle, at=NOW - timedelta(hours=2))
    assert sweep_offline(session, now=NOW) == []


def test_repeated_sweeps_deduplicate_into_one_alert(session):
    vehicle = seed_vehicle(session, code="BUS-01")
    add_reading(session, vehicle, at=NOW - timedelta(minutes=10))

    assert len(sweep_offline(session, now=NOW)) == 1
    assert sweep_offline(session, now=NOW + timedelta(seconds=20)) == []

    alerts = session.query(Alert).all()
    assert len(alerts) == 1
    assert alerts[0].occurrences == 2


def test_a_returning_vehicle_auto_resolves_its_offline_alert(session):
    """US-02 second criterion."""
    from app.schemas import TelemetryCreate
    from app.services.ingestion import ingest

    vehicle = seed_vehicle(session, code="BUS-01")
    add_reading(session, vehicle, at=NOW - timedelta(minutes=10))
    sweep_offline(session, now=NOW)

    ingest(
        session,
        TelemetryCreate(
            vehicle_code="BUS-01",
            recorded_at=NOW,
            latitude=24.86,
            longitude=67.01,
            speed_kph=20.0,
        ),
        now=NOW,
        broadcast=False,
    )

    alert = session.query(Alert).one()
    assert alert.status is AlertStatus.RESOLVED
    assert alert.resolved_at is not None


def test_sweeper_covers_a_whole_mixed_fleet(session):
    route = seed_route(session, code="R-1")
    quiet_bus = seed_vehicle(session, code="BUS-01", route=route)
    chatty_bus = seed_vehicle(session, code="BUS-02", route=route)
    add_reading(session, quiet_bus, at=NOW - timedelta(minutes=20))
    add_reading(session, chatty_bus, at=NOW - timedelta(seconds=10))

    created = sweep_offline(session, now=NOW)
    assert [a.vehicle_id for a in created] == [quiet_bus.id]


def test_timeout_is_honoured_from_the_supplied_thresholds(session):
    vehicle = seed_vehicle(session, code="BUS-01")
    add_reading(session, vehicle, at=NOW - timedelta(seconds=90))

    assert sweep_offline(session, now=NOW) == []
    assert len(
        sweep_offline(session, now=NOW, thresholds=Thresholds(heartbeat_timeout_s=60.0))
    ) == 1


# --------------------------------------------------------------------------
# Alert-service unit behaviour
# --------------------------------------------------------------------------


def test_cooldown_is_measured_from_last_seen_not_from_raised(session):
    """A fault that never stops must stay one alert, not spawn one per window."""
    from app.rules import AlertCandidate

    vehicle = seed_vehicle(session, code="BUS-01")
    candidate = AlertCandidate("ENGINE_OVERHEAT", Severity.WARNING, "hot", 110.0, 105.0)

    for minutes in range(0, 12, 2):  # every 2 minutes for 10 minutes, cooldown is 3
        alert_service.raise_candidates(
            session,
            vehicle=vehicle,
            candidates=[candidate],
            now=NOW + timedelta(minutes=minutes),
            cooldown_s=180.0,
        )

    alerts = session.query(Alert).all()
    assert len(alerts) == 1
    assert alerts[0].occurrences == 6


def test_a_genuinely_quiet_gap_starts_a_new_alert(session):
    from app.rules import AlertCandidate

    vehicle = seed_vehicle(session, code="BUS-01")
    candidate = AlertCandidate("ENGINE_OVERHEAT", Severity.WARNING, "hot", 110.0, 105.0)

    alert_service.raise_candidates(
        session, vehicle=vehicle, candidates=[candidate], now=NOW, cooldown_s=180.0
    )
    alert_service.raise_candidates(
        session,
        vehicle=vehicle,
        candidates=[candidate],
        now=NOW + timedelta(hours=1),
        cooldown_s=180.0,
    )
    assert session.query(Alert).count() == 2


def test_duration_is_none_until_resolved(session):
    vehicle = seed_vehicle(session, code="BUS-01")
    alert = Alert(
        vehicle_id=vehicle.id,
        rule_code="LOW_FUEL",
        severity=Severity.WARNING,
        message="low",
        raised_at=NOW,
        last_seen_at=NOW,
    )
    session.add(alert)
    session.commit()

    assert alert_service.duration_seconds(alert) is None
    alert_service.resolve(alert, NOW + timedelta(minutes=4))
    assert alert_service.duration_seconds(alert) == 240.0


def test_illegal_transitions_raise(session):
    import pytest

    vehicle = seed_vehicle(session, code="BUS-01")
    alert = Alert(
        vehicle_id=vehicle.id,
        rule_code="LOW_FUEL",
        severity=Severity.WARNING,
        message="low",
        raised_at=NOW,
        last_seen_at=NOW,
    )
    session.add(alert)
    session.commit()

    alert_service.resolve(alert, NOW)
    with pytest.raises(alert_service.AlertTransitionError):
        alert_service.acknowledge(alert, NOW)
    with pytest.raises(alert_service.AlertTransitionError):
        alert_service.resolve(alert, NOW)
