"""FR-16 low fuel rule. AI-generated from prompt P-17."""

from __future__ import annotations

import pytest

from app.config import Thresholds
from app.enums import Severity
from app.rules import fuel
from conftest import make_ctx, make_reading


@pytest.mark.parametrize(
    ("pct", "count", "severity"),
    [
        (100.0, 0, None),
        (20.1, 0, None),                 # just above low
        (20.0, 0, None),                 # exactly at low — inclusive, silent
        (19.9, 1, Severity.WARNING),
        (10.0, 1, Severity.WARNING),     # exactly at critical — still a warning
        (9.9, 1, Severity.CRITICAL),
        (0.0, 1, Severity.CRITICAL),     # empty tank
    ],
)
def test_fuel_bands(pct, count, severity):
    candidates = fuel.evaluate(make_ctx(reading=make_reading(fuel_pct=pct)))
    assert len(candidates) == count
    if severity is not None:
        assert candidates[0].severity is severity


def test_missing_fuel_sensor_is_skipped():
    assert fuel.evaluate(make_ctx(reading=make_reading(fuel_pct=None))) == []


def test_values_and_code():
    (candidate,) = fuel.evaluate(make_ctx(reading=make_reading(fuel_pct=8.0)))
    assert candidate.rule_code == "LOW_FUEL"
    assert candidate.measured_value == 8.0
    assert candidate.threshold_value == 10.0


def test_custom_thresholds():
    reading = make_reading(fuel_pct=35.0)
    assert fuel.evaluate(make_ctx(reading=reading)) == []
    generous = Thresholds(fuel_low_pct=40.0, fuel_critical_pct=30.0)
    (candidate,) = fuel.evaluate(make_ctx(reading=reading, thresholds=generous))
    assert candidate.severity is Severity.WARNING
