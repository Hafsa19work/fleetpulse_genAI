"""Health, stats and maintenance endpoints (NFR-06, NFR-08). From prompt P-18."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import telemetry_payload


def test_meta_identifies_the_project(client):
    """`/api/meta` is always present; `/` is taken over by the SPA in the
    container build, so the identity assertion belongs on the stable endpoint."""
    body = client.get("/api/meta").json()
    assert body["name"] == "FleetPulse"
    assert "53317" in body["student"]


def test_index_identifies_the_project_when_not_serving_the_spa(client):
    body = client.get("/").json()
    assert body["name"] == "FleetPulse"
    assert "53317" in body["student"]


def test_health_reports_database_and_counters(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["uptime_seconds"] >= 0
    assert body["websocket_clients"] == 0


def test_health_counters_move_with_ingestion(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    before = client.get("/api/health").json()["readings_ingested"]
    client.post("/api/telemetry", json=telemetry_payload())
    assert client.get("/api/health").json()["readings_ingested"] == before + 1


def test_stats_on_an_empty_system(client):
    body = client.get("/api/stats").json()
    assert body == {
        "vehicles": 0,
        "active_vehicles": 0,
        "telemetry_rows": 0,
        "open_alerts": 0,
        "alerts_by_severity": {},
        "alerts_by_rule": {},
    }


def test_stats_aggregate_correctly(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    client.post("/api/vehicles", json={"code": "BUS-02", "label": "c", "vehicle_type": "bus"})
    client.patch("/api/vehicles/BUS-02", json={"status": "maintenance"})
    client.post("/api/telemetry", json=telemetry_payload(engine_temp_c=130.0, fuel_pct=5.0))

    body = client.get("/api/stats").json()
    assert body["vehicles"] == 2
    assert body["active_vehicles"] == 1
    assert body["telemetry_rows"] == 1
    assert body["open_alerts"] == 2
    assert body["alerts_by_severity"]["critical"] == 2
    assert set(body["alerts_by_rule"]) == {"ENGINE_OVERHEAT", "LOW_FUEL"}


def test_prune_removes_old_telemetry_but_keeps_alerts(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    client.post("/api/telemetry", json=telemetry_payload(recorded_at=old, engine_temp_c=130.0))
    client.post("/api/telemetry", json=telemetry_payload())

    assert client.get("/api/stats").json()["telemetry_rows"] == 2
    # The 30-day-old reading also trips VEHICLE_OFFLINE on arrival, which the
    # fresh reading then auto-resolves (US-02) — so filter to the rule under test.
    overheats = client.get("/api/alerts", params={"rule_code": "ENGINE_OVERHEAT"}).json()
    assert overheats["total"] == 1

    result = client.request(
        "DELETE", "/api/maintenance/prune", params={"older_than_days": 7}
    ).json()
    assert result["deleted_rows"] == 1
    assert result["older_than_days"] == 7

    assert client.get("/api/stats").json()["telemetry_rows"] == 1
    # The audit trail survives, with its snapshotted values intact.
    alert = client.get("/api/alerts", params={"rule_code": "ENGINE_OVERHEAT"}).json()["items"][0]
    assert alert["measured_value"] == 130.0
    assert alert["telemetry_id"] is None


def test_prune_rejects_a_nonsense_window(client):
    response = client.request("DELETE", "/api/maintenance/prune", params={"older_than_days": 0})
    assert response.status_code == 422


def test_openapi_schema_is_served(client):
    schema = client.get("/openapi.json").json()
    assert "/api/telemetry" in schema["paths"]
    assert "/api/fleet/snapshot" in schema["paths"]
