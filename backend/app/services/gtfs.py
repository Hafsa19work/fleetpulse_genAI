"""Optional GTFS-Realtime vehicle-position reader (FR-36, FR-37).

`gtfs-realtime-bindings` is deliberately **not** a hard dependency. If the wheel is
missing, or the feed is unreachable, or the payload is not a valid protobuf, this
module reports the problem and the service keeps running on simulated telemetry.
An examiner without internet access must still be able to run the project.

Usage:
    from app.services.gtfs import GtfsReader
    reader = GtfsReader("https://example.org/gtfs-rt/vehicle-positions")
    readings = reader.fetch()          # list[dict] ready for POST /api/telemetry/batch
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("fleetpulse.gtfs")


class GtfsUnavailable(RuntimeError):
    """The GTFS path cannot be used right now — never fatal to the service."""


def bindings_available() -> bool:
    """True if the optional protobuf bindings are importable."""
    try:
        import google.transit.gtfs_realtime_pb2  # noqa: F401
    except Exception:  # noqa: BLE001 — ImportError, but broken installs raise others
        return False
    return True


@dataclass(slots=True)
class GtfsReader:
    feed_url: str
    code_prefix: str = ""
    timeout_s: float = 10.0

    # ------------------------------------------------------------------ mapping

    @staticmethod
    def map_entity(entity: Any, *, code_prefix: str = "") -> dict | None:
        """Map one GTFS-RT `FeedEntity` onto a FleetPulse telemetry payload.

        Split out from the network call so it can be unit-tested against a plain
        stub object — no protobuf, no HTTP (see backend/tests/test_gtfs.py).

        Returns None for entities that carry no usable vehicle position, which is
        normal: a feed mixes trip updates and alerts in with vehicle positions.
        """
        vehicle = getattr(entity, "vehicle", None)
        if vehicle is None:
            return None
        position = getattr(vehicle, "position", None)
        if position is None:
            return None

        lat = getattr(position, "latitude", None)
        lon = getattr(position, "longitude", None)
        if lat is None or lon is None:
            return None
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            logger.warning("discarding GTFS entity with out-of-range position %s,%s", lat, lon)
            return None

        descriptor = getattr(vehicle, "vehicle", None)
        raw_id = getattr(descriptor, "id", None) or getattr(entity, "id", None)
        if not raw_id:
            return None

        timestamp = getattr(vehicle, "timestamp", 0) or 0
        recorded_at = (
            datetime.fromtimestamp(timestamp, tz=UTC) if timestamp else datetime.now(UTC)
        )

        # GTFS-RT speed is metres per second; FleetPulse speaks km/h.
        speed_mps = getattr(position, "speed", None)
        speed_kph = round(speed_mps * 3.6, 2) if speed_mps is not None else 0.0

        bearing = getattr(position, "bearing", None)
        heading = float(bearing) % 360.0 if bearing is not None else None

        return {
            "vehicle_code": f"{code_prefix}{raw_id}",
            "recorded_at": recorded_at.isoformat(),
            "latitude": float(lat),
            "longitude": float(lon),
            "speed_kph": max(0.0, speed_kph),
            "heading_deg": heading,
        }

    # ------------------------------------------------------------------- fetch

    def fetch(self) -> list[dict]:
        """Poll the feed once. Raises GtfsUnavailable — never a bare network error."""
        if not bindings_available():
            raise GtfsUnavailable(
                "gtfs-realtime-bindings is not installed; "
                "run `pip install gtfs-realtime-bindings` to enable the GTFS path"
            )
        import httpx
        from google.transit import gtfs_realtime_pb2

        try:
            response = httpx.get(self.feed_url, timeout=self.timeout_s)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise GtfsUnavailable(f"could not fetch {self.feed_url}: {exc}") from exc

        feed = gtfs_realtime_pb2.FeedMessage()
        try:
            feed.ParseFromString(response.content)
        except Exception as exc:  # noqa: BLE001
            raise GtfsUnavailable(f"feed at {self.feed_url} is not valid GTFS-RT: {exc}") from exc

        readings = [
            mapped
            for entity in feed.entity
            if (mapped := self.map_entity(entity, code_prefix=self.code_prefix)) is not None
        ]
        logger.info("GTFS feed yielded %d vehicle position(s)", len(readings))
        return readings
