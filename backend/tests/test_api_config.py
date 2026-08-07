"""Runtime threshold tuning API (UC-7, US-08). AI-generated from prompt P-18."""

from __future__ import annotations

from conftest import telemetry_payload


def test_read_defaults(client):
    body = client.get("/api/config/thresholds").json()
    assert body["engine_warn_c"] == 105.0
    assert body["engine_critical_c"] == 115.0
    assert body["alert_cooldown_s"] == 180.0


def test_partial_update_leaves_the_rest_alone(client):
    updated = client.put(
        "/api/config/thresholds", json={"overspeed_tolerance_kph": 15.0}
    ).json()
    assert updated["overspeed_tolerance_kph"] == 15.0
    assert updated["engine_warn_c"] == 105.0


def test_tuning_changes_behaviour_without_a_code_change(client):
    """US-08 acceptance criterion, end to end."""
    route = client.post(
        "/api/routes",
        json={
            "code": "R-1",
            "name": "T",
            "vehicle_type": "bus",
            "speed_limit_kph": 60,
            "waypoints": [
                {"sequence": 0, "latitude": 24.86, "longitude": 67.00},
                {"sequence": 1, "latitude": 24.86, "longitude": 67.05},
            ],
        },
    ).json()
    client.post(
        "/api/vehicles",
        json={"code": "BUS-01", "label": "b", "vehicle_type": "bus", "route_id": route["id"]},
    )

    fired = client.post("/api/telemetry", json=telemetry_payload(speed_kph=70.0)).json()
    assert {a["rule_code"] for a in fired["alerts_created"]} == {"OVERSPEED"}

    client.put("/api/config/thresholds", json={"overspeed_tolerance_kph": 15.0})
    silent = client.post(
        "/api/telemetry", json=telemetry_payload(offset_s=600, speed_kph=70.0)
    ).json()
    assert silent["alerts_created"] == []


def test_reset_restores_defaults(client):
    client.put("/api/config/thresholds", json={"fuel_low_pct": 50.0})
    assert client.post("/api/config/thresholds/reset").json()["fuel_low_pct"] == 20.0


def test_inverted_engine_band_is_rejected(client):
    response = client.put(
        "/api/config/thresholds", json={"engine_critical_c": 90.0}
    )
    assert response.status_code == 422
    assert "engine_warn_c" in response.json()["detail"]
    # The rejected update must not have been applied.
    assert client.get("/api/config/thresholds").json()["engine_critical_c"] == 115.0


def test_inverted_fuel_band_is_rejected(client):
    assert client.put("/api/config/thresholds", json={"fuel_critical_pct": 40.0}).status_code == 422


def test_out_of_range_values_are_rejected(client):
    assert client.put("/api/config/thresholds", json={"fuel_low_pct": 150.0}).status_code == 422
    assert client.put("/api/config/thresholds", json={"heartbeat_timeout_s": 0}).status_code == 422
    assert (
        client.put("/api/config/thresholds", json={"overspeed_tolerance_kph": -1}).status_code
        == 422
    )


def test_rule_catalogue_is_introspectable(client):
    rules = client.get("/api/config/rules").json()
    assert len(rules) == 8

    by_code = {rule["code"]: rule for rule in rules}
    assert by_code["SCHEDULE_DELAY"]["applies_to"] == ["bus"]
    assert by_code["CARGO_TEMP_EXCURSION"]["applies_to"] == ["truck"]
    assert set(by_code["OVERSPEED"]["applies_to"]) == {"bus", "truck"}
