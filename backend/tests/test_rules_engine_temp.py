"""FR-15 engine overheating rule. AI-generated from prompt P-17."""

from __future__ import annotations

import pytest

from app.config import Thresholds
from app.enums import Severity
from app.rules import engine_temp
from conftest import make_ctx, make_reading


@pytest.mark.parametrize(
    ("temp", "count", "severity"),
    [
        (20.0, 0, None),                    # cold engine
        (104.9, 0, None),                   # just under warning
        (105.0, 0, None),                   # exactly at warning — inclusive, silent
        (105.1, 1, Severity.WARNING),       # first warning
        (115.0, 1, Severity.WARNING),       # exactly at critical — still a warning
        (115.1, 1, Severity.CRITICAL),      # first critical
        (140.0, 1, Severity.CRITICAL),      # extreme
    ],
)
def test_temperature_bands(temp, count, severity):
    candidates = engine_temp.evaluate(make_ctx(reading=make_reading(engine_temp_c=temp)))
    assert len(candidates) == count
    if severity is not None:
        assert candidates[0].severity is severity


def test_missing_sensor_is_not_a_fault():
    """A telematics unit without a temperature probe must not raise an alert."""
    ctx = make_ctx(reading=make_reading(engine_temp_c=None))
    assert engine_temp.evaluate(ctx) == []


def test_message_and_values():
    ctx = make_ctx(reading=make_reading(engine_temp_c=118.0))
    (candidate,) = engine_temp.evaluate(ctx)
    assert candidate.rule_code == "ENGINE_OVERHEAT"
    assert candidate.measured_value == 118.0
    assert candidate.threshold_value == 115.0
    assert "118.0 °C" in candidate.message
    assert candidate.message.startswith("BUS-01")


def test_thresholds_are_injected_not_hardcoded():
    reading = make_reading(engine_temp_c=95.0)
    assert engine_temp.evaluate(make_ctx(reading=reading)) == []

    strict = Thresholds(engine_warn_c=90.0, engine_critical_c=93.0)
    (candidate,) = engine_temp.evaluate(make_ctx(reading=reading, thresholds=strict))
    assert candidate.severity is Severity.CRITICAL


def test_applies_to_trucks_as_well():
    from conftest import make_truck

    ctx = make_ctx(vehicle=make_truck(), reading=make_reading(engine_temp_c=120.0))
    assert len(engine_temp.evaluate(ctx)) == 1
