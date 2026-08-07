"""FR-21 cargo temperature excursion — trucks only. AI-generated from prompt P-17."""

from __future__ import annotations

import pytest

from app.enums import Severity
from app.rules import cargo_temp
from conftest import make_ctx, make_reading, make_truck, make_vehicle

FROZEN = {"cargo_temp_min_c": -20.0, "cargo_temp_max_c": -15.0}


def truck_ctx(temp, **vehicle_kw):
    vehicle = make_truck(**{**FROZEN, **vehicle_kw})
    return make_ctx(vehicle=vehicle, reading=make_reading(cargo_temp_c=temp))


@pytest.mark.parametrize(
    ("temp", "count", "severity"),
    [
        (-17.5, 0, None),                  # mid-band
        (-20.0, 0, None),                  # exactly at the lower bound
        (-15.0, 0, None),                  # exactly at the upper bound
        (-14.9, 1, Severity.WARNING),      # just over
        (-12.0, 1, Severity.CRITICAL),     # 3 °C over
        (-21.0, 1, Severity.WARNING),      # just under
        (-25.0, 1, Severity.CRITICAL),     # 5 °C under
    ],
)
def test_band_boundaries(temp, count, severity):
    candidates = cargo_temp.evaluate(truck_ctx(temp))
    assert len(candidates) == count
    if severity is not None:
        assert candidates[0].severity is severity


def test_direction_is_reported():
    (hot,) = cargo_temp.evaluate(truck_ctx(-10.0))
    (cold,) = cargo_temp.evaluate(truck_ctx(-30.0))
    assert "above" in hot.message
    assert "below" in cold.message
    assert hot.rule_code == "CARGO_TEMP_EXCURSION"


def test_measured_and_threshold_values():
    (candidate,) = cargo_temp.evaluate(truck_ctx(-11.0))
    assert candidate.measured_value == -11.0
    assert candidate.threshold_value == -15.0


def test_rule_is_truck_gated():
    """US-06: a bus reporting a cargo temperature is ignored."""
    ctx = make_ctx(vehicle=make_vehicle(**FROZEN), reading=make_reading(cargo_temp_c=20.0))
    assert cargo_temp.evaluate(ctx) == []


def test_unrefrigerated_truck_has_no_band_to_break():
    ctx = make_ctx(
        vehicle=make_truck(cargo_temp_min_c=None, cargo_temp_max_c=None),
        reading=make_reading(cargo_temp_c=45.0),
    )
    assert cargo_temp.evaluate(ctx) == []


def test_missing_cargo_sensor_is_skipped():
    assert cargo_temp.evaluate(truck_ctx(None)) == []


def test_upper_bound_only():
    ctx = make_ctx(
        vehicle=make_truck(cargo_temp_min_c=None, cargo_temp_max_c=8.0),
        reading=make_reading(cargo_temp_c=12.0),
    )
    (candidate,) = cargo_temp.evaluate(ctx)
    assert candidate.threshold_value == 8.0


def test_lower_bound_only():
    ctx = make_ctx(
        vehicle=make_truck(cargo_temp_min_c=2.0, cargo_temp_max_c=None),
        reading=make_reading(cargo_temp_c=-1.0),
    )
    (candidate,) = cargo_temp.evaluate(ctx)
    assert candidate.threshold_value == 2.0


def test_chilled_band_is_independent_of_the_frozen_band():
    """Two trucks in one fleet, different limits — the band lives on the vehicle."""
    chilled = make_ctx(
        vehicle=make_truck(cargo_temp_min_c=2.0, cargo_temp_max_c=8.0),
        reading=make_reading(cargo_temp_c=-17.0),
    )
    assert len(cargo_temp.evaluate(chilled)) == 1  # fine for a frozen load, not a chilled one
