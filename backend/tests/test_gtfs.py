"""Optional GTFS-Realtime reader (FR-36, FR-37). AI-generated from prompt P-17.

`map_entity` is tested against plain stub objects, so the suite runs whether or not
`gtfs-realtime-bindings` is installed — which is the whole point of FR-37.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.services.gtfs import GtfsReader, GtfsUnavailable, bindings_available


def entity(
    *,
    vid: str | None = "1001",
    lat: float | None = 24.86,
    lon: float | None = 67.01,
    speed: float | None = 10.0,
    bearing: float | None = 90.0,
    timestamp: int = 1_780_000_000,
    with_vehicle: bool = True,
    with_position: bool = True,
):
    position = (
        SimpleNamespace(latitude=lat, longitude=lon, speed=speed, bearing=bearing)
        if with_position
        else None
    )
    vehicle = (
        SimpleNamespace(
            position=position,
            timestamp=timestamp,
            vehicle=SimpleNamespace(id=vid),
        )
        if with_vehicle
        else None
    )
    return SimpleNamespace(id="entity-1", vehicle=vehicle)


def test_maps_a_complete_entity():
    mapped = GtfsReader.map_entity(entity())
    assert mapped["vehicle_code"] == "1001"
    assert mapped["latitude"] == 24.86
    assert mapped["longitude"] == 67.01
    assert mapped["heading_deg"] == 90.0


def test_speed_is_converted_from_metres_per_second_to_kph():
    assert GtfsReader.map_entity(entity(speed=10.0))["speed_kph"] == pytest.approx(36.0)


def test_missing_speed_defaults_to_zero_not_none():
    assert GtfsReader.map_entity(entity(speed=None))["speed_kph"] == 0.0


def test_negative_speed_is_clamped():
    assert GtfsReader.map_entity(entity(speed=-5.0))["speed_kph"] == 0.0


def test_timestamp_is_interpreted_as_utc_epoch_seconds():
    mapped = GtfsReader.map_entity(entity(timestamp=1_780_000_000))
    expected = datetime.fromtimestamp(1_780_000_000, tz=UTC).isoformat()
    assert mapped["recorded_at"] == expected


def test_a_zero_timestamp_falls_back_to_now():
    mapped = GtfsReader.map_entity(entity(timestamp=0))
    parsed = datetime.fromisoformat(mapped["recorded_at"])
    assert (datetime.now(UTC) - parsed).total_seconds() < 5


def test_bearing_is_wrapped_into_the_valid_range():
    assert GtfsReader.map_entity(entity(bearing=450.0))["heading_deg"] == 90.0


def test_missing_bearing_is_none_not_zero():
    """0° means due north; absent must not be silently reported as north."""
    assert GtfsReader.map_entity(entity(bearing=None))["heading_deg"] is None


def test_code_prefix_namespaces_external_ids():
    mapped = GtfsReader.map_entity(entity(), code_prefix="KHI-")
    assert mapped["vehicle_code"] == "KHI-1001"


def test_falls_back_to_the_entity_id_when_the_descriptor_has_none():
    assert GtfsReader.map_entity(entity(vid=None))["vehicle_code"] == "entity-1"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"with_vehicle": False},   # a trip-update entity, not a position
        {"with_position": False},  # vehicle known, position not reported
        {"lat": None},
        {"lon": None},
    ],
)
def test_unusable_entities_are_skipped_not_errors(kwargs):
    assert GtfsReader.map_entity(entity(**kwargs)) is None


@pytest.mark.parametrize(("lat", "lon"), [(95.0, 67.0), (24.0, 200.0), (-91.0, 0.0)])
def test_out_of_range_positions_are_discarded(lat, lon):
    assert GtfsReader.map_entity(entity(lat=lat, lon=lon)) is None


def test_entity_without_any_identifier_is_skipped():
    stub = SimpleNamespace(
        id=None,
        vehicle=SimpleNamespace(
            position=SimpleNamespace(latitude=24.0, longitude=67.0, speed=1.0, bearing=0.0),
            timestamp=0,
            vehicle=SimpleNamespace(id=None),
        ),
    )
    assert GtfsReader.map_entity(stub) is None


@pytest.mark.skipif(
    bindings_available(), reason="protobuf bindings are installed in this environment"
)
def test_missing_bindings_degrade_gracefully():
    """FR-37: the service must never crash because an optional wheel is absent."""
    reader = GtfsReader("https://example.invalid/feed")
    with pytest.raises(GtfsUnavailable, match="gtfs-realtime-bindings"):
        reader.fetch()


def test_bindings_available_returns_a_bool():
    assert isinstance(bindings_available(), bool)
