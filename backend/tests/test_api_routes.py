"""Route registry API. AI-generated integration tests from prompt P-18."""

from __future__ import annotations

ROUTE = {
    "code": "R-11A",
    "name": "City Centre to Airport",
    "vehicle_type": "bus",
    "speed_limit_kph": 60,
    "corridor_half_width_m": 150,
    "waypoints": [
        {"sequence": 1, "latitude": 24.8629, "longitude": 67.0208},
        {"sequence": 0, "latitude": 24.8607, "longitude": 67.0011},
        {"sequence": 2, "latitude": 24.8664, "longitude": 67.0402},
    ],
    "stops": [
        {
            "sequence": 0,
            "name": "Tower",
            "latitude": 24.8629,
            "longitude": 67.0208,
            "scheduled_offset_s": 420,
        }
    ],
}


def test_create_route_sorts_waypoints_by_sequence(client):
    response = client.post("/api/routes", json=ROUTE)
    assert response.status_code == 201
    body = response.json()
    assert [w["sequence"] for w in body["waypoints"]] == [0, 1, 2]
    assert body["stops"][0]["name"] == "Tower"


def test_duplicate_route_code_is_409(client):
    client.post("/api/routes", json=ROUTE)
    assert client.post("/api/routes", json=ROUTE).status_code == 409


def test_duplicate_waypoint_sequence_is_422(client):
    bad = {
        **ROUTE,
        "code": "R-BAD",
        "waypoints": [
            {"sequence": 0, "latitude": 24.86, "longitude": 67.00},
            {"sequence": 0, "latitude": 24.87, "longitude": 67.01},
        ],
    }
    assert client.post("/api/routes", json=bad).status_code == 422


def test_out_of_range_coordinates_are_422(client):
    bad = {
        **ROUTE,
        "code": "R-BAD2",
        "waypoints": [{"sequence": 0, "latitude": 200.0, "longitude": 67.0}],
    }
    assert client.post("/api/routes", json=bad).status_code == 422


def test_non_positive_speed_limit_is_422(client):
    assert client.post("/api/routes", json={**ROUTE, "code": "R-0", "speed_limit_kph": 0}).status_code == 422


def test_get_and_list(client):
    client.post("/api/routes", json=ROUTE)
    assert client.get("/api/routes/R-11A").json()["name"] == ROUTE["name"]
    assert len(client.get("/api/routes").json()) == 1
    assert client.get("/api/routes/NOPE").status_code == 404


def test_deleting_a_route_detaches_its_vehicles_rather_than_failing(client):
    route = client.post("/api/routes", json=ROUTE).json()
    client.post(
        "/api/vehicles",
        json={"code": "BUS-01", "label": "b", "vehicle_type": "bus", "route_id": route["id"]},
    )

    assert client.delete("/api/routes/R-11A").status_code == 204

    vehicle = client.get("/api/vehicles/BUS-01").json()
    assert vehicle["route_id"] is None


def test_delete_unknown_route_is_404(client):
    assert client.delete("/api/routes/NOPE").status_code == 404
