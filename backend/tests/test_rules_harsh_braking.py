"""FR-19 harsh braking rule. AI-generated from prompt P-17.

Includes the regression test for defect D-02 (division by zero on a zero-length
time gap) found by the adversarial review pass, prompt P-19.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.config import Thresholds
from app.enums import Severity
from app.rules import harsh_braking
from conftest import T0, make_ctx, make_reading


def ctx_with_drop(from_kph: float, to_kph: float, gap_s: float, **kw):
    previous = make_reading(recorded_at=T0 - timedelta(seconds=gap_s), speed_kph=from_kph)
    current = make_reading(recorded_at=T0, speed_kph=to_kph)
    return make_ctx(reading=current, previous=previous, now=T0, **kw)


def test_no_previous_reading_is_skipped():
    assert harsh_braking.evaluate(make_ctx(previous=None)) == []


@pytest.mark.parametrize(
    ("from_kph", "to_kph", "expected"),
    [
        (60.0, 50.0, 0),   # gentle
        (60.0, 35.0, 0),   # exactly 25 kph — at threshold, inclusive, silent
        (60.0, 34.0, 1),   # 26 kph drop
        (80.0, 0.0, 1),    # emergency stop
        (30.0, 60.0, 0),   # accelerating, not braking
    ],
)
def test_drop_thresholds(from_kph, to_kph, expected):
    assert len(harsh_braking.evaluate(ctx_with_drop(from_kph, to_kph, 5.0))) == expected


def test_zero_time_gap_does_not_divide_by_zero():
    """Regression for D-02: duplicate timestamps must not crash the engine."""
    assert harsh_braking.evaluate(ctx_with_drop(80.0, 0.0, 0.0)) == []


def test_negative_time_gap_is_declined():
    """Out-of-order delivery: the 'previous' reading is actually newer."""
    assert harsh_braking.evaluate(ctx_with_drop(80.0, 0.0, -10.0)) == []


def test_gap_beyond_the_window_is_ignored():
    """A 60 kph drop measured over 10 minutes says nothing about braking force."""
    assert harsh_braking.evaluate(ctx_with_drop(80.0, 10.0, 600.0)) == []


def test_severity_escalates_with_the_size_of_the_drop():
    (mild,) = harsh_braking.evaluate(ctx_with_drop(60.0, 25.0, 5.0))   # 35 kph
    (severe,) = harsh_braking.evaluate(ctx_with_drop(90.0, 0.0, 5.0))  # 90 kph
    assert mild.severity is Severity.WARNING
    assert severe.severity is Severity.CRITICAL


def test_reported_values_and_message():
    (candidate,) = harsh_braking.evaluate(ctx_with_drop(70.0, 20.0, 5.0))
    assert candidate.rule_code == "HARSH_BRAKING"
    assert candidate.measured_value == pytest.approx(50.0)
    assert candidate.threshold_value == 25.0
    assert "10.0 kph/s" in candidate.message


def test_window_is_configurable():
    ctx = ctx_with_drop(80.0, 10.0, 30.0, thresholds=Thresholds(harsh_braking_window_s=60.0))
    assert len(harsh_braking.evaluate(ctx)) == 1
