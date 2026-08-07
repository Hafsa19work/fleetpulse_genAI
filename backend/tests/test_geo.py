"""Geodesic helpers. AI-generated from prompt P-17, extended by P-19 (D-03)."""

from __future__ import annotations

import pytest

from app.services.geo import (
    bearing_deg,
    distance_along_polyline_m,
    distance_to_polyline_m,
    haversine_m,
    normalize_lon_delta,
    point_at_distance,
    point_to_segment,
    polyline_length_m,
)

KARACHI = (24.8607, 67.0011)
LINE = [(24.8600, 67.0000), (24.8600, 67.0500)]


def test_haversine_zero_distance():
    assert haversine_m(KARACHI, KARACHI) == pytest.approx(0.0, abs=1e-6)


def test_haversine_one_degree_of_latitude():
    """1° of latitude is ~111.2 km anywhere on the globe."""
    assert haversine_m((0.0, 0.0), (1.0, 0.0)) == pytest.approx(111_195, rel=0.001)


def test_haversine_is_symmetric():
    a, b = (24.86, 67.00), (25.00, 67.20)
    assert haversine_m(a, b) == pytest.approx(haversine_m(b, a))


@pytest.mark.parametrize(
    ("delta", "expected"),
    [(0, 0), (10, 10), (-10, -10), (190, -170), (-190, 170), (360, 0), (540, -180)],
)
def test_normalize_lon_delta(delta, expected):
    assert normalize_lon_delta(delta) == pytest.approx(expected)


def test_antimeridian_distance_is_short_not_a_lap_of_the_planet():
    """Regression for D-03: 179.99°E to 179.99°W is ~2.2 km, not ~40,000 km."""
    distance = haversine_m((0.0, 179.99), (0.0, -179.99))
    assert distance == pytest.approx(2_226, rel=0.01)


def test_point_on_the_segment_has_zero_distance():
    distance, t = point_to_segment((24.8600, 67.0250), LINE[0], LINE[1])
    assert distance == pytest.approx(0.0, abs=1.0)
    assert 0.45 < t < 0.55


def test_projection_clamps_before_the_start():
    distance, t = point_to_segment((24.8600, 66.9000), LINE[0], LINE[1])
    assert t == 0.0
    assert distance > 1_000


def test_projection_clamps_past_the_end():
    _distance, t = point_to_segment((24.8600, 67.2000), LINE[0], LINE[1])
    assert t == 1.0


def test_degenerate_segment_does_not_divide_by_zero():
    distance, t = point_to_segment((24.8700, 67.0000), LINE[0], LINE[0])
    assert t == 0.0
    assert distance == pytest.approx(haversine_m((24.8700, 67.0000), LINE[0]))


def test_distance_to_polyline_offset_north():
    point = (24.8600 + 200 / 111_132.0, 67.0250)
    assert distance_to_polyline_m(LINE, point) == pytest.approx(200, abs=3)


def test_distance_to_empty_polyline_is_none():
    assert distance_to_polyline_m([], KARACHI) is None


def test_distance_to_single_point_polyline():
    assert distance_to_polyline_m([KARACHI], KARACHI) == pytest.approx(0.0, abs=1e-6)


def test_polyline_length_matches_the_sum_of_its_segments():
    poly = [(24.86, 67.00), (24.86, 67.02), (24.88, 67.02)]
    expected = haversine_m(poly[0], poly[1]) + haversine_m(poly[1], poly[2])
    assert polyline_length_m(poly) == pytest.approx(expected)


def test_polyline_length_of_a_single_point_is_zero():
    assert polyline_length_m([KARACHI]) == 0.0


def test_distance_along_polyline_at_the_start_and_end():
    assert distance_along_polyline_m(LINE, LINE[0]) == pytest.approx(0.0, abs=1.0)
    assert distance_along_polyline_m(LINE, LINE[1]) == pytest.approx(
        polyline_length_m(LINE), abs=1.0
    )


def test_distance_along_polyline_needs_two_points():
    assert distance_along_polyline_m([KARACHI], KARACHI) is None


def test_point_at_distance_round_trips():
    total = polyline_length_m(LINE)
    midpoint = point_at_distance(LINE, total / 2)
    assert distance_along_polyline_m(LINE, midpoint) == pytest.approx(total / 2, abs=2.0)


def test_point_at_distance_clamps_to_the_endpoints():
    assert point_at_distance(LINE, -100) == LINE[0]
    assert point_at_distance(LINE, 10_000_000)[1] == pytest.approx(LINE[-1][1])


def test_point_at_distance_rejects_an_empty_polyline():
    with pytest.raises(ValueError, match="at least one point"):
        point_at_distance([], 10.0)


def test_bearing_due_east_and_north():
    assert bearing_deg((0.0, 0.0), (0.0, 1.0)) == pytest.approx(90.0, abs=0.5)
    assert bearing_deg((0.0, 0.0), (1.0, 0.0)) == pytest.approx(0.0, abs=0.5)
