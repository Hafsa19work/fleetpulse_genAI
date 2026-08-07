"""Geodesic helpers used by the route-deviation and schedule rules.

Pure maths: no I/O, no clock, no logging. Distances are in metres.

Longitude differences are normalised to the range [-180, 180] so a route that
crosses the antimeridian (Fiji, Chatham Islands, trans-Pacific freight) does not
produce a spurious ~40,000 km deviation. This was defect D-03 in the AI review
pass (docs/09-test-report.md).
"""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_008.8
Point = tuple[float, float]  # (latitude, longitude) in degrees


def normalize_lon_delta(delta_deg: float) -> float:
    """Wrap a longitude difference into [-180, 180]."""
    return (delta_deg + 180.0) % 360.0 - 180.0


def haversine_m(a: Point, b: Point) -> float:
    """Great-circle distance between two (lat, lon) points, in metres."""
    lat1, lon1 = a
    lat2, lon2 = b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(normalize_lon_delta(lon2 - lon1))
    h = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def _to_local_xy(point: Point, origin: Point) -> tuple[float, float]:
    """Equirectangular projection about `origin`, accurate to <0.1% over a few km.

    Used only for point-to-segment geometry, where the segment is short; the
    absolute distances returned to callers still come from `haversine_m`.
    """
    lat, lon = point
    lat0, lon0 = origin
    m_per_deg_lat = 111_132.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    return (
        normalize_lon_delta(lon - lon0) * m_per_deg_lon,
        (lat - lat0) * m_per_deg_lat,
    )


def point_to_segment(point: Point, seg_start: Point, seg_end: Point) -> tuple[float, float]:
    """Distance in metres from `point` to segment, plus the projection parameter t.

    `t` is clamped to [0, 1]: 0 means the closest point is `seg_start`, 1 means
    `seg_end`. Returns (distance_m, t).
    """
    px, py = _to_local_xy(point, seg_start)
    ex, ey = _to_local_xy(seg_end, seg_start)
    seg_len_sq = ex * ex + ey * ey
    if seg_len_sq == 0.0:
        # Degenerate segment (duplicate waypoints) — distance to the single point.
        return haversine_m(point, seg_start), 0.0
    t = max(0.0, min(1.0, (px * ex + py * ey) / seg_len_sq))
    closest = (
        seg_start[0] + (seg_end[0] - seg_start[0]) * t,
        seg_start[1] + normalize_lon_delta(seg_end[1] - seg_start[1]) * t,
    )
    return haversine_m(point, closest), t


def distance_to_polyline_m(polyline: list[Point], point: Point) -> float | None:
    """Shortest distance from `point` to the polyline, or None if under-defined.

    Returns None for an empty polyline; for a single-point polyline returns the
    direct distance to that point.
    """
    if not polyline:
        return None
    if len(polyline) == 1:
        return haversine_m(point, polyline[0])
    return min(
        point_to_segment(point, polyline[i], polyline[i + 1])[0]
        for i in range(len(polyline) - 1)
    )


def polyline_length_m(polyline: list[Point]) -> float:
    """Total length of the polyline in metres (0.0 for fewer than two points)."""
    if len(polyline) < 2:
        return 0.0
    return sum(haversine_m(polyline[i], polyline[i + 1]) for i in range(len(polyline) - 1))


def distance_along_polyline_m(polyline: list[Point], point: Point) -> float | None:
    """Arc length from the polyline start to the projection of `point` onto it.

    Used to decide which timetabled stop a bus has already passed and how far it
    still has to travel. Returns None if the polyline has fewer than two points.
    """
    if len(polyline) < 2:
        return None
    best_distance = math.inf
    best_along = 0.0
    travelled = 0.0
    for i in range(len(polyline) - 1):
        seg_len = haversine_m(polyline[i], polyline[i + 1])
        dist, t = point_to_segment(point, polyline[i], polyline[i + 1])
        if dist < best_distance:
            best_distance = dist
            best_along = travelled + seg_len * t
        travelled += seg_len
    return best_along


def point_at_distance(polyline: list[Point], distance_m: float) -> Point:
    """Interpolate the point that is `distance_m` along the polyline.

    Clamps to the endpoints. Used by the simulator to drive a vehicle along its
    route; kept here so the same geometry serves both production and simulation.
    """
    if not polyline:
        raise ValueError("polyline must contain at least one point")
    if len(polyline) == 1 or distance_m <= 0:
        return polyline[0]
    remaining = distance_m
    for i in range(len(polyline) - 1):
        seg_len = haversine_m(polyline[i], polyline[i + 1])
        if seg_len == 0.0:
            continue
        if remaining <= seg_len:
            t = remaining / seg_len
            return (
                polyline[i][0] + (polyline[i + 1][0] - polyline[i][0]) * t,
                polyline[i][1] + normalize_lon_delta(polyline[i + 1][1] - polyline[i][1]) * t,
            )
        remaining -= seg_len
    return polyline[-1]


def bearing_deg(a: Point, b: Point) -> float:
    """Initial compass bearing from a to b, in degrees [0, 360)."""
    phi1, phi2 = math.radians(a[0]), math.radians(b[0])
    d_lambda = math.radians(normalize_lon_delta(b[1] - a[1]))
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
