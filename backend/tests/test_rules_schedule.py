"""FR-20 schedule delay rule — buses only. AI-generated from prompt P-17.

Fixture geometry: the route runs due east along latitude 24.86 from longitude
67.00 to 67.05, roughly 5.05 km. A single timetabled stop sits at the eastern end
with a scheduled offset of 600 s.

The rule projects arrival from the **average** speed since the trip began, not from
the speed in the reading (see the rule's docstring and defect D-09), so these tests
control the bus's *position* and *elapsed time* rather than its speedometer. The
`speed_kph` argument is still passed to prove it has no influence.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.config import Thresholds
from app.enums import Severity, VehicleType
from app.rules import schedule
from conftest import LINE, T0, make_ctx, make_reading, make_route, make_stop, make_vehicle

END_STOP = make_stop(0, LINE[1][0], LINE[1][1], offset_s=600, name="Airport Gate")
ROUTE_WITH_STOP = make_route(stops=(END_STOP,))


def bus_ctx(*, elapsed_s: float, speed_kph: float = 40.0, lon: float = 67.0000, **kw):
    vehicle = make_vehicle(trip_started_at=T0 - timedelta(seconds=elapsed_s))
    reading = make_reading(recorded_at=T0, latitude=24.8600, longitude=lon, speed_kph=speed_kph)
    return make_ctx(
        reading=reading, vehicle=vehicle, route=kw.pop("route", ROUTE_WITH_STOP), now=T0, **kw
    )


def test_on_time_bus_is_silent():
    # Halfway (2.53 km) after 300 s => 8.4 m/s average. The remaining 2.53 km takes
    # another 300 s, so projected arrival is 600 s — exactly on schedule.
    assert schedule.evaluate(bus_ctx(elapsed_s=300, lon=67.0250)) == []


def test_late_bus_raises_a_warning():
    # 40% along (2.02 km) after 400 s => 5.05 m/s average; the remaining 3.03 km
    # takes 600 s, so projected 1000 s against a 600 s schedule: 400 s late.
    (candidate,) = schedule.evaluate(bus_ctx(elapsed_s=400, lon=67.0200))
    assert candidate.rule_code == "SCHEDULE_DELAY"
    assert candidate.severity is Severity.WARNING
    assert candidate.threshold_value == 300.0
    assert candidate.measured_value == pytest.approx(400, abs=30)
    assert "Airport Gate" in candidate.message


def test_very_late_bus_is_critical():
    # 20% along after 600 s => a crawl; the rest of the route takes far longer than
    # the whole timetable allows.
    (candidate,) = schedule.evaluate(bus_ctx(elapsed_s=600, lon=67.0100))
    assert candidate.severity is Severity.CRITICAL


def test_stationary_bus_falls_back_to_delay_already_accrued():
    """A bus that has not moved has no finite ETA; the rule must still report,
    using the delay it has already accumulated."""
    candidates = schedule.evaluate(bus_ctx(elapsed_s=1500, lon=67.0000, speed_kph=0.0))
    assert len(candidates) == 1
    assert candidates[0].measured_value == 900.0  # 1500 elapsed - 600 scheduled


def test_stationary_but_still_early_is_silent():
    assert schedule.evaluate(bus_ctx(elapsed_s=400, lon=67.0000, speed_kph=0.0)) == []


def test_a_bus_dwelling_at_a_stop_does_not_project_a_false_delay():
    """Regression for D-07 and D-09.

    A bus momentarily at 1.5 kph — pulling into a stop — used to project an arrival
    an hour away and fire a critical alert. Raising the floor on the instantaneous
    speed (D-07) only moved the failure to ~6 kph, which is what a bus reads while
    accelerating away from a stop (D-09). The projection now uses average speed, so
    the momentary reading is irrelevant: this bus is on schedule and must be silent
    at any instantaneous speed.
    """
    for momentary_speed in (0.0, 1.5, 6.0, 12.0, 40.0):
        assert schedule.evaluate(
            bus_ctx(elapsed_s=300, lon=67.0250, speed_kph=momentary_speed)
        ) == [], f"false alert at an instantaneous {momentary_speed} kph"


def test_the_speedometer_reading_cannot_change_the_verdict():
    """Two readings identical but for their speedometer must agree."""
    slow = schedule.evaluate(bus_ctx(elapsed_s=600, lon=67.0100, speed_kph=2.0))
    fast = schedule.evaluate(bus_ctx(elapsed_s=600, lon=67.0100, speed_kph=90.0))
    assert len(slow) == len(fast) == 1
    assert slow[0].measured_value == pytest.approx(fast[0].measured_value)


def test_rule_is_bus_gated():
    """US-04: identical numbers on a truck raise nothing."""
    from conftest import make_truck

    ctx = bus_ctx(elapsed_s=1200)
    truck_ctx = make_ctx(
        reading=ctx.reading,
        vehicle=make_truck(trip_started_at=ctx.vehicle.trip_started_at),
        route=ROUTE_WITH_STOP,
        now=T0,
    )
    assert truck_ctx.vehicle.vehicle_type is VehicleType.TRUCK
    assert schedule.evaluate(truck_ctx) == []


def test_no_trip_start_is_skipped():
    vehicle = make_vehicle(trip_started_at=None)
    ctx = make_ctx(vehicle=vehicle, route=ROUTE_WITH_STOP, now=T0)
    assert schedule.evaluate(ctx) == []


def test_route_without_stops_is_skipped():
    assert schedule.evaluate(bus_ctx(elapsed_s=5000, route=make_route())) == []


def test_no_route_is_skipped():
    assert schedule.evaluate(bus_ctx(elapsed_s=5000, route=None)) == []


def test_reading_before_the_trip_started_is_bad_data_not_a_delay():
    assert schedule.evaluate(bus_ctx(elapsed_s=-120)) == []


def test_past_the_final_stop_the_rule_stops_caring():
    early_stop = make_stop(0, 24.8600, 67.0100, offset_s=60, name="Tower")
    ctx = bus_ctx(elapsed_s=9000, lon=67.0400, route=make_route(stops=(early_stop,)))
    assert schedule.evaluate(ctx) == []


def test_grace_period_is_configurable():
    generous = Thresholds(schedule_grace_s=3_600.0)
    assert schedule.evaluate(bus_ctx(elapsed_s=1200, thresholds=generous)) == []
