"""FR-17 route deviation rule. AI-generated from prompt P-17.

The corridor in the fixture is 150 m either side of a line of latitude, so a
north-south offset in degrees converts cleanly to metres (1° lat ≈ 111,132 m) and
the acceptance criteria in US-03 can be asserted at the metre.
"""

from __future__ import annotations

import pytest

from app.enums import Severity
from app.rules import deviation
from conftest import make_ctx, make_reading, make_route

M_PER_DEG_LAT = 111_132.0
BASE_LAT, BASE_LON = 24.8600, 67.0100


def reading_offset_by(metres: float):
    return make_reading(latitude=BASE_LAT + metres / M_PER_DEG_LAT, longitude=BASE_LON)


@pytest.mark.parametrize("metres", [0.0, 50.0, 149.0])
def test_inside_the_corridor_is_silent(metres):
    ctx = make_ctx(reading=reading_offset_by(metres))
    assert deviation.evaluate(ctx) == []


def test_just_outside_the_corridor_fires():
    """US-03: 149 m silent, 151 m fires."""
    ctx = make_ctx(reading=reading_offset_by(151.0))
    (candidate,) = deviation.evaluate(ctx)
    assert candidate.rule_code == "ROUTE_DEVIATION"
    assert candidate.severity is Severity.WARNING
    assert candidate.threshold_value == 150.0
    assert candidate.measured_value == pytest.approx(151.0, abs=2.0)


def test_far_outside_is_critical():
    ctx = make_ctx(reading=reading_offset_by(600.0))  # > 3 × corridor
    (candidate,) = deviation.evaluate(ctx)
    assert candidate.severity is Severity.CRITICAL


def test_deviation_south_is_symmetric():
    ctx = make_ctx(reading=reading_offset_by(-200.0))
    (candidate,) = deviation.evaluate(ctx)
    assert candidate.measured_value == pytest.approx(200.0, abs=2.0)


def test_no_route_is_skipped():
    ctx = make_ctx(reading=reading_offset_by(5_000.0), route=None)
    assert deviation.evaluate(ctx) == []


def test_single_point_polyline_defines_no_corridor():
    ctx = make_ctx(
        reading=reading_offset_by(5_000.0),
        route=make_route(polyline=((BASE_LAT, BASE_LON),)),
    )
    assert deviation.evaluate(ctx) == []


def test_empty_polyline_is_skipped():
    ctx = make_ctx(reading=reading_offset_by(5_000.0), route=make_route(polyline=()))
    assert deviation.evaluate(ctx) == []


def test_beyond_the_polyline_ends_measures_to_the_endpoint():
    """A vehicle past the end of its route is measured to the last waypoint,
    not treated as on-route because it is 'in line' with the corridor."""
    far_east = make_reading(latitude=BASE_LAT, longitude=67.2000)
    (candidate,) = deviation.evaluate(make_ctx(reading=far_east))
    assert candidate.measured_value > 1_000.0


def test_wider_corridor_tolerates_the_same_position():
    wide = make_route(corridor_half_width_m=1_000.0)
    ctx = make_ctx(reading=reading_offset_by(400.0), route=wide)
    assert deviation.evaluate(ctx) == []
