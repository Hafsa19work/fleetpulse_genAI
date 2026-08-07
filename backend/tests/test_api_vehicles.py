"""Vehicle registry API. AI-generated integration tests from prompt P-18."""

from __future__ import annotations


def make_route(client, code="R-1"):
    return client.post(
        "/api/routes",
        json={
            "code": code,
            "name": "Test route",
            "vehicle_type": "bus",
            "waypoints": [
                {"sequence": 0, "latitude": 24.86, "longitude": 67.00},
                {"sequence": 1, "latitude": 24.86, "longitude": 67.05},
            ],
        },
    ).json()


def test_create_and_fetch_vehicle(client):
    response = client.post(
        "/api/vehicles",
        json={"code": "BUS-01", "label": "Bus 01", "vehicle_type": "bus"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "BUS-01"
    assert body["status"] == "active"

    fetched = client.get("/api/vehicles/BUS-01")
    assert fetched.status_code == 200
    assert fetched.json()["label"] == "Bus 01"


def test_duplicate_code_is_rejected(client):
    payload = {"code": "BUS-01", "label": "First", "vehicle_type": "bus"}
    assert client.post("/api/vehicles", json=payload).status_code == 201

    conflict = client.post("/api/vehicles", json={**payload, "label": "Second"})
    assert conflict.status_code == 409
    assert "BUS-01" in conflict.json()["detail"]


def test_unknown_vehicle_is_404(client):
    assert client.get("/api/vehicles/NOPE").status_code == 404


def test_invalid_vehicle_type_is_422(client):
    response = client.post(
        "/api/vehicles",
        json={"code": "X-1", "label": "x", "vehicle_type": "spaceship"},
    )
    assert response.status_code == 422


def test_assign_a_route(client):
    route = make_route(client)
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})

    updated = client.patch("/api/vehicles/BUS-01", json={"route_id": route["id"]})
    assert updated.status_code == 200
    assert updated.json()["route_id"] == route["id"]


def test_assigning_a_missing_route_is_422(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    response = client.patch("/api/vehicles/BUS-01", json={"route_id": 9999})
    assert response.status_code == 422


def test_create_with_a_missing_route_is_422(client):
    response = client.post(
        "/api/vehicles",
        json={"code": "BUS-01", "label": "b", "vehicle_type": "bus", "route_id": 4242},
    )
    assert response.status_code == 422


def test_partial_update_leaves_other_fields_alone(client):
    client.post(
        "/api/vehicles",
        json={
            "code": "TRK-01",
            "label": "Reefer",
            "vehicle_type": "truck",
            "cargo_temp_min_c": -20,
            "cargo_temp_max_c": -15,
        },
    )
    updated = client.patch("/api/vehicles/TRK-01", json={"status": "maintenance"}).json()
    assert updated["status"] == "maintenance"
    assert updated["cargo_temp_min_c"] == -20
    assert updated["label"] == "Reefer"


def test_inverted_cargo_band_is_rejected(client):
    response = client.post(
        "/api/vehicles",
        json={
            "code": "TRK-02",
            "label": "Bad band",
            "vehicle_type": "truck",
            "cargo_temp_min_c": 5,
            "cargo_temp_max_c": -5,
        },
    )
    assert response.status_code == 422


def test_list_and_filter(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    client.post("/api/vehicles", json={"code": "TRK-01", "label": "t", "vehicle_type": "truck"})

    assert len(client.get("/api/vehicles").json()) == 2
    trucks = client.get("/api/vehicles", params={"vehicle_type": "truck"}).json()
    assert [v["code"] for v in trucks] == ["TRK-01"]


def test_delete_vehicle(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    assert client.delete("/api/vehicles/BUS-01").status_code == 204
    assert client.get("/api/vehicles/BUS-01").status_code == 404


def test_telemetry_history_is_newest_first(client):
    from conftest import telemetry_payload

    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    for offset in (-30, -20, -10):
        client.post("/api/telemetry", json=telemetry_payload(offset_s=offset, speed_kph=10))

    history = client.get("/api/vehicles/BUS-01/telemetry").json()
    assert len(history) == 3
    stamps = [row["recorded_at"] for row in history]
    assert stamps == sorted(stamps, reverse=True)


def test_telemetry_history_respects_the_limit(client):
    from conftest import telemetry_payload

    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})
    for offset in range(-5, 0):
        client.post("/api/telemetry", json=telemetry_payload(offset_s=offset))

    assert len(client.get("/api/vehicles/BUS-01/telemetry", params={"limit": 2}).json()) == 2


def test_telemetry_history_for_unknown_vehicle_is_404(client):
    assert client.get("/api/vehicles/GHOST/telemetry").status_code == 404
