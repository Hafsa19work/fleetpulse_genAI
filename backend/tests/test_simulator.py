"""Fleet simulator (FR-33 … FR-35). AI-generated from prompt P-17."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.enums import VehicleType
from app.services.simulator import SCENARIOS, FleetSimulator, SimVehicle

START = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
LINE = [(24.8600, 67.0000), (24.8600, 67.0500)]


def make_sim(scenario: str = "none", vehicle_type=VehicleType.BUS, **kw) -> FleetSimulator:
    seed = kw.pop("seed", 42)
    vehicle = SimVehicle(
        code="BUS-01",
        vehicle_type=vehicle_type,
        polyline=list(LINE),
        cruise_kph=kw.pop("cruise_kph", 40.0),
        scenario=scenario,
        **kw,
    )
    return FleetSimulator([vehicle], seed=seed, tick_seconds=5.0)


def test_emits_one_reading_per_vehicle_per_tick():
    sim = make_sim()
    assert len(sim.step(START)) == 1
    assert len(sim.run(START, 10)) == 10


def test_reading_shape_matches_the_ingestion_contract():
    reading = make_sim().step(START)[0]
    assert set(reading) == {
        "vehicle_code",
        "recorded_at",
        "latitude",
        "longitude",
        "speed_kph",
        "heading_deg",
        "engine_temp_c",
        "fuel_pct",
        "cargo_temp_c",
        "odometer_km",
    }
    assert -90 <= reading["latitude"] <= 90
    assert -180 <= reading["longitude"] <= 180
    assert reading["speed_kph"] >= 0


def test_same_seed_reproduces_the_run_exactly():
    """FR-34 — without this the AI-generated assertions below would be flaky."""
    assert make_sim(seed=7).run(START, 25) == make_sim(seed=7).run(START, 25)


def test_different_seeds_diverge():
    assert make_sim(seed=1).run(START, 25) != make_sim(seed=2).run(START, 25)


def test_vehicle_advances_along_its_route():
    readings = make_sim().run(START, 10)
    assert readings[-1]["longitude"] > readings[0]["longitude"]


def test_bus_restarts_the_route_at_the_terminus():
    """A bus runs the route one way, then begins again as the next service.

    It must never travel backwards: the timetable is defined in one direction, so a
    reversing bus matches stops it has already served (see the module docstring).
    """
    sim = make_sim(cruise_kph=90.0)
    lons = [r["longitude"] for r in sim.run(START, 80)]

    assert max(lons) <= 67.0501  # never overruns the end of the polyline
    assert min(lons) >= 66.9999  # never runs off the start either

    # Longitude increases every tick except at a restart, where it jumps back to
    # the beginning. Exactly that pattern — never a small step backwards.
    restarts = [i for i in range(1, len(lons)) if lons[i] < lons[i - 1]]
    assert restarts, "the bus never completed the route"
    for i in restarts:
        assert lons[i] == pytest.approx(67.0, abs=1e-4), "went backwards instead of restarting"


def test_bus_reaching_the_terminus_reports_a_new_trip():
    """Reaching the terminus begins a new timetabled trip.

    Regression for the long-run schedule drift seen in the containerised demo:
    without this signal `trip_started_at` stays at the seed time for ever, elapsed
    time grows without bound, and eventually every bus reports itself late against
    a timetable it already completed.
    """
    sim = make_sim(cruise_kph=90.0)
    assert sim.pop_trip_restarts() == []  # nothing at the start of a run

    restarts = []
    for i in range(80):
        sim.step(START + timedelta(seconds=5 * i))
        restarts.extend(sim.pop_trip_restarts())

    assert "BUS-01" in restarts


def test_trip_restarts_are_drained_not_repeated():
    sim = make_sim(cruise_kph=200.0)
    for i in range(40):
        sim.step(START + timedelta(seconds=5 * i))
        if sim.pop_trip_restarts():
            # Immediately asking again must return nothing — the event is consumed.
            assert sim.pop_trip_restarts() == []
            return
    raise AssertionError("the bus never reached the end of its route")


def test_a_truck_never_reports_a_trip_restart():
    """Trucks hold at their destination; they do not shuttle, so no new trip."""
    sim = make_sim(vehicle_type=VehicleType.TRUCK, cruise_kph=200.0)
    restarts = []
    for i in range(40):
        sim.step(START + timedelta(seconds=5 * i))
        restarts.extend(sim.pop_trip_restarts())
    assert restarts == []


def test_truck_holds_at_the_far_end():
    sim = make_sim(vehicle_type=VehicleType.TRUCK, cruise_kph=90.0)
    longitudes = [r["longitude"] for r in sim.run(START, 80)]
    assert longitudes[-1] == pytest.approx(67.05, abs=1e-4)


def test_fuel_only_decreases():
    fuel = [r["fuel_pct"] for r in make_sim().run(START, 30)]
    assert all(later <= earlier for earlier, later in zip(fuel, fuel[1:], strict=False))


def test_odometer_only_increases():
    odo = [r["odometer_km"] for r in make_sim().run(START, 30)]
    assert all(later >= earlier for earlier, later in zip(odo, odo[1:], strict=False))


def test_healthy_run_stays_within_normal_engine_temperature():
    temps = [r["engine_temp_c"] for r in make_sim().run(START, 60)]
    assert max(temps) < 105.0


def test_overheat_scenario_crosses_both_thresholds():
    temps = [r["engine_temp_c"] for r in make_sim("overheat").run(START, 60)]
    assert max(temps) > 115.0
    assert temps[0] < temps[-1]


def test_fuel_drain_scenario_empties_much_faster():
    healthy = make_sim().run(START, 40)[-1]["fuel_pct"]
    leaking = make_sim("fuel_drain").run(START, 40)[-1]["fuel_pct"]
    assert leaking < healthy - 5.0


def test_deviation_scenario_walks_off_the_corridor():
    from app.services.geo import distance_to_polyline_m

    readings = make_sim("deviation").run(START, 40)
    last = readings[-1]
    assert distance_to_polyline_m(LINE, (last["latitude"], last["longitude"])) > 150.0


def test_dropout_scenario_stops_emitting():
    readings = make_sim("dropout").run(START, 30)
    assert 0 < len(readings) < 30


def test_cargo_spike_scenario_warms_the_load():
    sim = make_sim(vehicle_type=VehicleType.TRUCK, scenario="cargo_spike", cargo_temp_c=-18.0)
    readings = sim.run(START, 40)
    assert readings[-1]["cargo_temp_c"] > -15.0


def test_cargo_temperature_is_none_for_a_non_reefer():
    assert make_sim().step(START)[0]["cargo_temp_c"] is None


def test_timestamps_advance_with_the_tick():
    readings = make_sim().run(START, 3)
    stamps = [datetime.fromisoformat(r["recorded_at"]) for r in readings]
    assert stamps[1] - stamps[0] == timedelta(seconds=5)


def test_arm_rejects_an_unknown_scenario():
    with pytest.raises(ValueError, match="unknown scenario"):
        make_sim().arm("BUS-01", "explode")


def test_arm_rejects_an_unknown_vehicle():
    with pytest.raises(KeyError):
        make_sim().arm("GHOST", "overheat")


def test_arm_sets_the_scenario():
    sim = make_sim()
    sim.arm("BUS-01", "overheat")
    assert sim.vehicles[0].scenario == "overheat"


def test_scenario_catalogue():
    assert SCENARIOS == ("none", "overheat", "fuel_drain", "deviation", "dropout", "cargo_spike")


def test_a_vehicle_with_a_degenerate_route_does_not_crash():
    vehicle = SimVehicle(
        code="X", vehicle_type=VehicleType.BUS, polyline=[(24.86, 67.0)], cruise_kph=40.0
    )
    sim = FleetSimulator([vehicle], seed=1)
    reading = sim.step(START)[0]
    assert reading["latitude"] == pytest.approx(24.86)


def test_build_from_routes_skips_vehicles_without_a_usable_route(session):
    from app.services.simulator import build_from_routes
    from conftest import seed_route, seed_vehicle

    route = seed_route(session, code="R-1")
    on_route = seed_vehicle(session, code="BUS-01", route=route)
    stranded = seed_vehicle(session, code="BUS-99", route=None)

    sim = build_from_routes([route], [on_route, stranded], seed=3)
    assert [v.code for v in sim.vehicles] == ["BUS-01"]


def test_build_from_routes_gives_reefers_a_starting_cargo_temperature(session):
    from app.services.simulator import build_from_routes
    from conftest import seed_route, seed_vehicle

    route = seed_route(session, code="T-1", vehicle_type=VehicleType.TRUCK)
    truck = seed_vehicle(
        session,
        code="TRK-01",
        route=route,
        vehicle_type=VehicleType.TRUCK,
        cargo_temp_min_c=-20.0,
        cargo_temp_max_c=-15.0,
    )
    sim = build_from_routes([route], [truck], seed=3)
    assert sim.vehicles[0].cargo_temp_c == pytest.approx(-17.5)
