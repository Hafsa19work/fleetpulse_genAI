"""FR-14 overspeed rule. AI-generated from prompt P-17.

Boundary coverage: below / exactly at / just above the tolerated limit, plus the
warning-to-critical escalation and the no-route skip.
"""

from __future__ import annotations

import pytest

from app.config import Thresholds
from app.enums import Severity
from app.rules import overspeed
from conftest import make_ctx, make_reading, make_route


@pytest.mark.parametrize(
    ("speed", "expected"),
    [
        (0.0, 0),      # stationary
        (59.0, 0),     # under the limit
        (60.0, 0),     # exactly at the limit
        (65.0, 0),     # exactly at limit + tolerance — inclusive, so silent
        (65.1, 1),     # first speed that fires
        (95.0, 1),     # far over
    ],
)
def test_overspeed_boundaries(speed, expected):
    ctx = make_ctx(reading=make_reading(speed_kph=speed))
    assert len(overspeed.evaluate(ctx)) == expected


def test_warning_below_critical_margin():
    ctx = make_ctx(reading=make_reading(speed_kph=80.0))  # 65 allowed, +15 over
    (candidate,) = overspeed.evaluate(ctx)
    assert candidate.severity is Severity.WARNING
    assert candidate.rule_code == "OVERSPEED"


def test_critical_above_margin():
    ctx = make_ctx(reading=make_reading(speed_kph=90.0))  # 65 allowed, +25 over
    (candidate,) = overspeed.evaluate(ctx)
    assert candidate.severity is Severity.CRITICAL


def test_reports_measured_and_threshold_values():
    ctx = make_ctx(reading=make_reading(speed_kph=72.0))
    (candidate,) = overspeed.evaluate(ctx)
    assert candidate.measured_value == 72.0
    assert candidate.threshold_value == 65.0  # limit 60 + tolerance 5
    assert "72 kph" in candidate.message
    assert "R-1" in candidate.message


def test_skipped_without_a_route():
    """UC-2 extension 2a: no assigned route means no limit to compare against."""
    ctx = make_ctx(reading=make_reading(speed_kph=200.0), route=None)
    assert overspeed.evaluate(ctx) == []


def test_uses_the_route_limit_not_a_global_constant():
    slow_route = make_route(code="R-SLOW", speed_limit_kph=30.0)
    ctx = make_ctx(reading=make_reading(speed_kph=40.0), route=slow_route)
    (candidate,) = overspeed.evaluate(ctx)
    assert candidate.threshold_value == 35.0


def test_tolerance_is_configurable_at_runtime():
    """US-08: widening the tolerance silences an alert without a code change."""
    reading = make_reading(speed_kph=70.0)
    assert overspeed.evaluate(make_ctx(reading=reading))  # default tolerance 5

    relaxed = Thresholds(overspeed_tolerance_kph=15.0)
    assert overspeed.evaluate(make_ctx(reading=reading, thresholds=relaxed)) == []
