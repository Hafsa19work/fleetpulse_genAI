"""Telemetry ingestion API — the end-to-end path of UC-1. From prompt P-18."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from conftest import telemetry_payload


@pytest.fixture
def fleet(client):
    route = client.post(
        "/api/routes",
        json={
            "code": "R-1",
            "name": "Test",
            "vehicle_type": "bus",
            "speed_limit_kph": 60,
            "corridor_half_width_m": 150,
            "waypoints": [
                {"sequence": 0, "latitude": 24.86, "longitude": 67.00},
                {"sequence": 1, "latitude": 24.86, "longitude": 67.05},
            ],
        },
    ).json()
    client.post(
        "/api/vehicles",
        json={"code": "BUS-01", "label": "Bus 01", "vehicle_type": "bus", "route_id": route["id"]},
    )
    client.post(
        "/api/vehicles",
        json={
            "code": "TRK-01",
            "label": "Reefer",
            "vehicle_type": "truck",
            "route_id": route["id"],
            "cargo_temp_min_c": -20,
            "cargo_temp_max_c": -15,
        },
    )
    return route


def test_healthy_reading_is_accepted_and_raises_nothing(client, fleet):
    response = client.post("/api/telemetry", json=telemetry_payload())
    assert response.status_code == 202
    body = response.json()
    assert body["reading_id"] is not None
    assert body["duplicate"] is False
    assert body["evaluated"] is True
    assert body["alerts_created"] == []
    assert body["failed_rules"] == {}


def test_faulty_reading_raises_the_expected_alerts(client, fleet):
    body = client.post(
        "/api/telemetry",
        json=telemetry_payload(speed_kph=95.0, engine_temp_c=125.0, fuel_pct=3.0),
    ).json()
    codes = {alert["rule_code"] for alert in body["alerts_created"]}
    assert codes == {"OVERSPEED", "ENGINE_OVERHEAT", "LOW_FUEL"}
    assert all(alert["vehicle_code"] == "BUS-01" for alert in body["alerts_created"])


def test_unknown_vehicle_is_404_and_persists_nothing(client, fleet):
    response = client.post("/api/telemetry", json=telemetry_payload(code="GHOST-99"))
    assert response.status_code == 404
    assert client.get("/api/stats").json()["telemetry_rows"] == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"latitude": 91.0},
        {"longitude": -181.0},
        {"speed_kph": -5.0},
        {"fuel_pct": 140.0},
        {"heading_deg": 400.0},
    ],
)
def test_invalid_payloads_are_422(client, fleet, bad):
    assert client.post("/api/telemetry", json=telemetry_payload(**bad)).status_code == 422


def test_ingestion_is_idempotent(client, fleet):
    payload = telemetry_payload()
    first = client.post("/api/telemetry", json=payload).json()
    second = client.post("/api/telemetry", json=payload).json()

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["evaluated"] is False
    assert second["reading_id"] == first["reading_id"]
    assert len(client.get("/api/vehicles/BUS-01/telemetry").json()) == 1


def test_a_duplicate_does_not_double_count_an_alert(client, fleet):
    payload = telemetry_payload(engine_temp_c=125.0)
    client.post("/api/telemetry", json=payload)
    client.post("/api/telemetry", json=payload)

    alerts = client.get("/api/alerts", params={"rule_code": "ENGINE_OVERHEAT"}).json()
    assert alerts["total"] == 1
    assert alerts["items"][0]["occurrences"] == 1


def test_alerts_deduplicate_within_the_cooldown(client, fleet):
    """FR-25: two firings inside the window make one alert with occurrences == 2."""
    now = datetime.now(UTC)
    for seconds in (0, 5):
        client.post(
            "/api/telemetry",
            json=telemetry_payload(
                recorded_at=(now + timedelta(seconds=seconds)).isoformat(),
                engine_temp_c=125.0,
            ),
        )

    alerts = client.get("/api/alerts", params={"rule_code": "ENGINE_OVERHEAT"}).json()
    assert alerts["total"] == 1
    assert alerts["items"][0]["occurrences"] == 2


def test_severity_escalates_but_never_downgrades(client, fleet):
    now = datetime.now(UTC)
    client.post(
        "/api/telemetry",
        json=telemetry_payload(recorded_at=now.isoformat(), engine_temp_c=110.0),
    )
    warning = client.get("/api/alerts").json()["items"][0]
    assert warning["severity"] == "warning"

    client.post(
        "/api/telemetry",
        json=telemetry_payload(
            recorded_at=(now + timedelta(seconds=5)).isoformat(), engine_temp_c=125.0
        ),
    )
    escalated = client.get("/api/alerts").json()["items"][0]
    assert escalated["severity"] == "critical"

    client.post(
        "/api/telemetry",
        json=telemetry_payload(
            recorded_at=(now + timedelta(seconds=10)).isoformat(), engine_temp_c=110.0
        ),
    )
    still_critical = client.get("/api/alerts").json()["items"][0]
    assert still_critical["severity"] == "critical"
    assert still_critical["occurrences"] == 3


def test_non_active_vehicle_is_recorded_but_not_evaluated(client, fleet):
    """FR-04: a vehicle in the workshop stores telemetry and raises nothing."""
    client.patch("/api/vehicles/BUS-01", json={"status": "maintenance"})
    body = client.post(
        "/api/telemetry", json=telemetry_payload(speed_kph=180.0, engine_temp_c=200.0)
    ).json()

    assert body["evaluated"] is False
    assert body["alerts_created"] == []
    assert body["reading_id"] is not None
    assert len(client.get("/api/vehicles/BUS-01/telemetry").json()) == 1


def test_truck_rules_are_gated_on_the_vehicle(client, fleet):
    body = client.post(
        "/api/telemetry", json=telemetry_payload(code="TRK-01", cargo_temp_c=-5.0)
    ).json()
    assert {a["rule_code"] for a in body["alerts_created"]} == {"CARGO_TEMP_EXCURSION"}

    bus = client.post("/api/telemetry", json=telemetry_payload(cargo_temp_c=-5.0)).json()
    assert bus["alerts_created"] == []


def test_harsh_braking_uses_the_previous_reading(client, fleet):
    now = datetime.now(UTC)
    client.post(
        "/api/telemetry",
        json=telemetry_payload(recorded_at=now.isoformat(), speed_kph=60.0),
    )
    body = client.post(
        "/api/telemetry",
        json=telemetry_payload(
            recorded_at=(now + timedelta(seconds=5)).isoformat(), speed_kph=5.0
        ),
    ).json()
    assert "HARSH_BRAKING" in {a["rule_code"] for a in body["alerts_created"]}


def test_batch_ingestion(client, fleet):
    now = datetime.now(UTC)
    readings = [
        telemetry_payload(recorded_at=(now + timedelta(seconds=i)).isoformat())
        for i in range(5)
    ]
    body = client.post("/api/telemetry/batch", json={"readings": readings}).json()
    assert body["accepted"] == 5
    assert body["rejected"] == 0
    assert body["duplicates"] == 0


def test_batch_reports_bad_rows_without_discarding_the_good_ones(client, fleet):
    now = datetime.now(UTC)
    readings = [
        telemetry_payload(recorded_at=now.isoformat()),
        telemetry_payload(code="GHOST", recorded_at=now.isoformat()),
        telemetry_payload(recorded_at=(now + timedelta(seconds=1)).isoformat()),
    ]
    body = client.post("/api/telemetry/batch", json={"readings": readings}).json()
    assert body["accepted"] == 2
    assert body["rejected"] == 1
    assert "GHOST" in body["errors"][0]


def test_batch_over_the_limit_is_422(client, fleet):
    readings = [telemetry_payload(offset_s=i) for i in range(501)]
    assert client.post("/api/telemetry/batch", json={"readings": readings}).status_code == 422


def test_empty_batch_is_422(client, fleet):
    assert client.post("/api/telemetry/batch", json={"readings": []}).status_code == 422
