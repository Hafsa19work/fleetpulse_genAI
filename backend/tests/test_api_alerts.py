"""Alert query and lifecycle API (UC-4). AI-generated from prompt P-18."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from conftest import telemetry_payload


@pytest.fixture
def alerting_fleet(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    client.post("/api/vehicles", json={"code": "BUS-02", "label": "c", "vehicle_type": "bus"})
    now = datetime.now(UTC)
    client.post(
        "/api/telemetry",
        json=telemetry_payload(recorded_at=now.isoformat(), engine_temp_c=125.0),
    )
    client.post(
        "/api/telemetry",
        json=telemetry_payload(
            code="BUS-02", recorded_at=now.isoformat(), fuel_pct=15.0
        ),
    )
    return client.get("/api/alerts").json()


def test_alerts_are_listed_newest_first(client, alerting_fleet):
    assert alerting_fleet["total"] == 2
    assert {item["rule_code"] for item in alerting_fleet["items"]} == {
        "ENGINE_OVERHEAT",
        "LOW_FUEL",
    }


def test_alert_carries_its_vehicle_code_and_values(client, alerting_fleet):
    alert = next(
        a for a in alerting_fleet["items"] if a["rule_code"] == "ENGINE_OVERHEAT"
    )
    assert alert["vehicle_code"] == "BUS-01"
    assert alert["measured_value"] == 125.0
    assert alert["threshold_value"] == 115.0
    assert alert["status"] == "open"
    assert alert["duration_seconds"] is None


def test_filter_by_vehicle_severity_status_and_rule(client, alerting_fleet):
    assert client.get("/api/alerts", params={"vehicle_code": "BUS-02"}).json()["total"] == 1
    assert client.get("/api/alerts", params={"severity": "critical"}).json()["total"] == 1
    assert client.get("/api/alerts", params={"status": "open"}).json()["total"] == 2
    assert client.get("/api/alerts", params={"status": "resolved"}).json()["total"] == 0
    assert client.get("/api/alerts", params={"rule_code": "LOW_FUEL"}).json()["total"] == 1


def test_filter_by_time_window(client, alerting_fleet):
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert client.get("/api/alerts", params={"since": future}).json()["total"] == 0
    assert client.get("/api/alerts", params={"since": past}).json()["total"] == 2
    assert client.get("/api/alerts", params={"until": past}).json()["total"] == 0


def test_pagination_reports_the_full_total(client, alerting_fleet):
    page = client.get("/api/alerts", params={"limit": 1, "offset": 0}).json()
    assert page["total"] == 2
    assert len(page["items"]) == 1

    second = client.get("/api/alerts", params={"limit": 1, "offset": 1}).json()
    assert second["items"][0]["id"] != page["items"][0]["id"]


def test_acknowledge_then_resolve(client, alerting_fleet):
    alert_id = alerting_fleet["items"][0]["id"]

    acknowledged = client.post(f"/api/alerts/{alert_id}/acknowledge").json()
    assert acknowledged["status"] == "acknowledged"
    assert acknowledged["acknowledged_at"] is not None

    resolved = client.post(f"/api/alerts/{alert_id}/resolve").json()
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None
    assert resolved["duration_seconds"] >= 0


def test_open_can_be_resolved_directly(client, alerting_fleet):
    alert_id = alerting_fleet["items"][0]["id"]
    assert client.post(f"/api/alerts/{alert_id}/resolve").json()["status"] == "resolved"


def test_acknowledging_a_resolved_alert_is_409(client, alerting_fleet):
    alert_id = alerting_fleet["items"][0]["id"]
    client.post(f"/api/alerts/{alert_id}/resolve")

    conflict = client.post(f"/api/alerts/{alert_id}/acknowledge")
    assert conflict.status_code == 409
    assert client.get(f"/api/alerts/{alert_id}").json()["status"] == "resolved"


def test_resolving_twice_is_409(client, alerting_fleet):
    alert_id = alerting_fleet["items"][0]["id"]
    client.post(f"/api/alerts/{alert_id}/resolve")
    assert client.post(f"/api/alerts/{alert_id}/resolve").status_code == 409


def test_acknowledging_twice_is_idempotent(client, alerting_fleet):
    alert_id = alerting_fleet["items"][0]["id"]
    first = client.post(f"/api/alerts/{alert_id}/acknowledge").json()
    second = client.post(f"/api/alerts/{alert_id}/acknowledge").json()
    assert second["status"] == "acknowledged"
    assert second["acknowledged_at"] == first["acknowledged_at"]


def test_unknown_alert_is_404(client):
    assert client.get("/api/alerts/999").status_code == 404
    assert client.post("/api/alerts/999/acknowledge").status_code == 404
    assert client.post("/api/alerts/999/resolve").status_code == 404


def test_a_resolved_alert_is_not_reused_by_deduplication(client, alerting_fleet):
    """UC-3 extension 3a: a resolved alert is terminal; a refire creates a new one."""
    alert_id = next(
        a["id"] for a in alerting_fleet["items"] if a["rule_code"] == "ENGINE_OVERHEAT"
    )
    client.post(f"/api/alerts/{alert_id}/resolve")

    client.post(
        "/api/telemetry",
        json=telemetry_payload(offset_s=10, engine_temp_c=126.0),
    )
    overheats = client.get("/api/alerts", params={"rule_code": "ENGINE_OVERHEAT"}).json()
    assert overheats["total"] == 2


def test_an_acknowledged_alert_still_absorbs_refires(client, alerting_fleet):
    alert_id = next(
        a["id"] for a in alerting_fleet["items"] if a["rule_code"] == "ENGINE_OVERHEAT"
    )
    client.post(f"/api/alerts/{alert_id}/acknowledge")

    client.post("/api/telemetry", json=telemetry_payload(offset_s=10, engine_temp_c=126.0))
    refreshed = client.get(f"/api/alerts/{alert_id}").json()
    assert refreshed["occurrences"] == 2
    assert refreshed["status"] == "acknowledged"
