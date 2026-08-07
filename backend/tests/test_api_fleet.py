"""Fleet snapshot API (UC-5). AI-generated from prompt P-18."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import telemetry_payload


def test_empty_fleet_snapshot(client):
    body = client.get("/api/fleet/snapshot").json()
    assert body["vehicles"] == []
    assert body["counts"]["total"] == 0
    assert "generated_at" in body


def test_vehicle_with_no_telemetry_reads_as_offline(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    vehicle = client.get("/api/fleet/snapshot").json()["vehicles"][0]
    assert vehicle["state"] == "offline"
    assert vehicle["latitude"] is None
    assert vehicle["last_seen_at"] is None


def test_healthy_vehicle_reads_as_ok_with_its_last_position(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    client.post("/api/telemetry", json=telemetry_payload(latitude=24.87, longitude=67.02))

    vehicle = client.get("/api/fleet/snapshot").json()["vehicles"][0]
    assert vehicle["state"] == "ok"
    assert vehicle["latitude"] == 24.87
    assert vehicle["open_alerts"] == 0
    assert vehicle["seconds_since_report"] < 5


def test_state_reflects_the_worst_open_alert(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    now = datetime.now(UTC)
    client.post(
        "/api/telemetry",
        json=telemetry_payload(recorded_at=now.isoformat(), fuel_pct=15.0),
    )
    assert client.get("/api/fleet/snapshot").json()["vehicles"][0]["state"] == "warning"

    client.post(
        "/api/telemetry",
        json=telemetry_payload(
            recorded_at=(now + timedelta(seconds=1)).isoformat(),
            fuel_pct=15.0,
            engine_temp_c=130.0,
        ),
    )
    vehicle = client.get("/api/fleet/snapshot").json()["vehicles"][0]
    assert vehicle["state"] == "critical"
    assert vehicle["worst_severity"] == "critical"
    assert vehicle["open_alerts"] == 2


def test_resolving_the_alert_returns_the_vehicle_to_ok(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    client.post("/api/telemetry", json=telemetry_payload(fuel_pct=15.0))
    alert_id = client.get("/api/alerts").json()["items"][0]["id"]
    client.post(f"/api/alerts/{alert_id}/resolve")

    assert client.get("/api/fleet/snapshot").json()["vehicles"][0]["state"] == "ok"


def test_stale_telemetry_reads_as_offline(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    stale = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
    client.post("/api/telemetry", json=telemetry_payload(recorded_at=stale))

    vehicle = client.get("/api/fleet/snapshot").json()["vehicles"][0]
    assert vehicle["state"] == "offline"
    assert vehicle["seconds_since_report"] > 120


def test_retired_vehicle_is_not_shown_as_reporting(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    client.post("/api/telemetry", json=telemetry_payload())
    client.patch("/api/vehicles/BUS-01", json={"status": "retired"})

    vehicle = client.get("/api/fleet/snapshot").json()["vehicles"][0]
    assert vehicle["state"] == "offline"


def test_counts_add_up(client):
    for code in ("BUS-01", "BUS-02", "BUS-03"):
        client.post("/api/vehicles", json={"code": code, "label": code, "vehicle_type": "bus"})
    client.post("/api/telemetry", json=telemetry_payload(code="BUS-01"))
    client.post("/api/telemetry", json=telemetry_payload(code="BUS-02", engine_temp_c=130.0))

    counts = client.get("/api/fleet/snapshot").json()["counts"]
    assert counts["total"] == 3
    assert counts["ok"] == 1
    assert counts["critical"] == 1
    assert counts["offline"] == 1
    assert counts["reporting"] == 2


def test_snapshot_includes_routes_for_the_map(client):
    client.post(
        "/api/routes",
        json={
            "code": "R-1",
            "name": "Test",
            "vehicle_type": "bus",
            "waypoints": [
                {"sequence": 0, "latitude": 24.86, "longitude": 67.00},
                {"sequence": 1, "latitude": 24.86, "longitude": 67.05},
            ],
        },
    )
    routes = client.get("/api/fleet/snapshot").json()["routes"]
    assert len(routes) == 1
    assert len(routes[0]["waypoints"]) == 2


def test_snapshot_does_not_issue_a_query_per_vehicle(client, db_engine):
    """N+1 guard: 25 vehicles must not mean 25 latest-reading queries."""
    from sqlalchemy import event

    for i in range(25):
        code = f"BUS-{i:02d}"
        client.post("/api/vehicles", json={"code": code, "label": code, "vehicle_type": "bus"})
        client.post("/api/telemetry", json=telemetry_payload(code=code))

    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    event.listen(db_engine, "before_cursor_execute", _record)
    try:
        body = client.get("/api/fleet/snapshot").json()
    finally:
        event.remove(db_engine, "before_cursor_execute", _record)

    assert len(body["vehicles"]) == 25
    # Four queries — latest telemetry, alert counts, vehicles, routes — plus the
    # eager loads for route waypoints and stops. Nowhere near one per vehicle.
    assert len(statements) <= 8, statements
