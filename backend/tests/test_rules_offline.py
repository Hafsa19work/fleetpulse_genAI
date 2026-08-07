"""FR-18 vehicle-offline rule. AI-generated from prompt P-17."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.config import Thresholds
from app.enums import Severity
from app.rules import offline
from conftest import T0, make_ctx, make_reading


@pytest.mark.parametrize("age_s", [0, 30, 119, 120])
def test_fresh_enough_is_silent(age_s):
    ctx = make_ctx(reading=make_reading(recorded_at=T0 - timedelta(seconds=age_s)), now=T0)
    assert offline.evaluate(ctx) == []


def test_past_the_timeout_fires_critical():
    ctx = make_ctx(reading=make_reading(recorded_at=T0 - timedelta(seconds=121)), now=T0)
    (candidate,) = offline.evaluate(ctx)
    assert candidate.rule_code == "VEHICLE_OFFLINE"
    assert candidate.severity is Severity.CRITICAL
    assert candidate.measured_value == pytest.approx(121.0)
    assert candidate.threshold_value == 120.0


def test_on_the_ingestion_path_a_just_arrived_reading_is_silent():
    """The same rule runs on ingest, where age ~= 0 and it must stay quiet."""
    ctx = make_ctx(reading=make_reading(recorded_at=T0), now=T0)
    assert offline.evaluate(ctx) == []


def test_message_reports_minutes():
    ctx = make_ctx(reading=make_reading(recorded_at=T0 - timedelta(minutes=9)), now=T0)
    (candidate,) = offline.evaluate(ctx)
    assert "9.0 min" in candidate.message


def test_timeout_is_configurable():
    reading = make_reading(recorded_at=T0 - timedelta(seconds=90))
    assert offline.evaluate(make_ctx(reading=reading, now=T0)) == []
    strict = Thresholds(heartbeat_timeout_s=60.0)
    assert len(offline.evaluate(make_ctx(reading=reading, now=T0, thresholds=strict))) == 1


def test_a_future_timestamp_does_not_fire():
    """Clock skew on a device must not read as 'offline'."""
    ctx = make_ctx(reading=make_reading(recorded_at=T0 + timedelta(minutes=5)), now=T0)
    assert offline.evaluate(ctx) == []
