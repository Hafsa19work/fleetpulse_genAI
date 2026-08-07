"""Simulator CLI — drives the demo fleet against a running FleetPulse API.

    python -m app.simulate                              # all vehicles, healthy
    python -m app.simulate --scenario BUS-03=overheat --scenario TRK-01=cargo_spike
    python -m app.simulate --seed 7 --interval 2 --ticks 60
    python -m app.simulate --gtfs https://host/vehicle-positions   # real feed instead

Reads the fleet from the database, posts telemetry over HTTP so the exact same
ingestion path the dashboard depends on is exercised — not a back door that writes
rows directly.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from .database import SessionLocal
from .models import Route, Vehicle
from .services.gtfs import GtfsReader, GtfsUnavailable
from .services.simulator import SCENARIOS, build_from_routes

DEFAULT_API = "http://127.0.0.1:8000"


def _post_batch(client: httpx.Client, api: str, readings: list[dict]) -> dict:
    response = client.post(f"{api}/api/telemetry/batch", json={"readings": readings})
    response.raise_for_status()
    return response.json()


def _restart_trips(client: httpx.Client, api: str, codes: list[str], now: datetime) -> None:
    """Move each bus's schedule origin to now, because it has turned round.

    Without this a long-running simulation drifts: `trip_started_at` stays at the
    original seed time while the bus shuttles for ever, so accrued elapsed time
    eventually exceeds every stop's scheduled offset and the whole fleet reports
    itself late against a timetable it already finished. Uses the public PATCH
    endpoint rather than writing to the database directly.
    """
    for code in codes:
        try:
            client.patch(
                f"{api}/api/vehicles/{code}",
                json={"trip_started_at": now.isoformat()},
            ).raise_for_status()
        except httpx.HTTPError as exc:
            # A missed reset is cosmetic drift, never a reason to stop simulating.
            print(f"  (could not reset trip for {code}: {exc})", file=sys.stderr)


def run_simulator(args: argparse.Namespace) -> int:
    session = SessionLocal()
    try:
        routes = list(session.execute(select(Route)).scalars())
        vehicles = list(session.execute(select(Vehicle)).scalars())
    finally:
        session.close()

    if not vehicles:
        print("no vehicles found — run `python -m app.seed` first", file=sys.stderr)
        return 1

    sim = build_from_routes(routes, vehicles, seed=args.seed)
    sim.tick_seconds = args.interval
    if not sim.vehicles:
        print("no vehicles have a route with a polyline to drive along", file=sys.stderr)
        return 1

    for spec in args.scenario or []:
        if "=" not in spec:
            print(f"bad --scenario '{spec}', expected CODE=scenario", file=sys.stderr)
            return 2
        code, scenario = spec.split("=", 1)
        try:
            sim.arm(code, scenario)
        except (KeyError, ValueError) as exc:
            print(f"{exc}", file=sys.stderr)
            return 2
        print(f"armed {code} with scenario '{scenario}'")

    print(
        f"simulating {len(sim.vehicles)} vehicle(s), seed={args.seed}, "
        f"every {args.interval}s → {args.api}"
    )
    total_alerts = 0
    with httpx.Client(timeout=15.0) as client:
        tick = 0
        while args.ticks == 0 or tick < args.ticks:
            now = datetime.now(UTC)
            readings = sim.step(now)

            restarted = sim.pop_trip_restarts()
            if restarted:
                _restart_trips(client, args.api, restarted, now)
                print(f"       new trip started for {', '.join(restarted)}")

            if readings:
                try:
                    result = _post_batch(client, args.api, readings)
                except httpx.HTTPError as exc:
                    print(f"post failed: {exc}", file=sys.stderr)
                    return 1
                total_alerts += result.get("alerts_created", 0)
                print(
                    f"tick {tick + 1:>4}  sent {len(readings):>3}  "
                    f"accepted {result['accepted']:>3}  "
                    f"new alerts {result['alerts_created']:>2}  "
                    f"(total {total_alerts})"
                )
            tick += 1
            if args.ticks == 0 or tick < args.ticks:
                time.sleep(args.interval)
    return 0


def run_gtfs(args: argparse.Namespace) -> int:
    reader = GtfsReader(args.gtfs, code_prefix=args.gtfs_prefix)
    with httpx.Client(timeout=20.0) as client:
        tick = 0
        while args.ticks == 0 or tick < args.ticks:
            try:
                readings = reader.fetch()
            except GtfsUnavailable as exc:
                print(f"GTFS unavailable: {exc}", file=sys.stderr)
                return 1
            if readings:
                result = _post_batch(client, args.api, readings[:500])
                print(
                    f"gtfs poll {tick + 1}: {len(readings)} positions, "
                    f"accepted {result['accepted']}, rejected {result['rejected']}"
                )
                if result["rejected"]:
                    print(
                        "  (rejected readings are vehicles not registered in FleetPulse — "
                        "register them first with POST /api/vehicles)"
                    )
            tick += 1
            if args.ticks == 0 or tick < args.ticks:
                time.sleep(args.interval)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="FleetPulse telemetry simulator")
    parser.add_argument("--api", default=DEFAULT_API, help="FleetPulse base URL")
    parser.add_argument("--seed", type=int, default=42, help="deterministic seed (FR-34)")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between ticks")
    parser.add_argument("--ticks", type=int, default=0, help="0 = run until interrupted")
    parser.add_argument(
        "--scenario",
        action="append",
        metavar="CODE=NAME",
        help=f"arm a fault scenario; one of {', '.join(SCENARIOS)}",
    )
    parser.add_argument("--gtfs", metavar="URL", help="ingest a real GTFS-Realtime feed instead")
    parser.add_argument("--gtfs-prefix", default="", help="prefix mapped onto GTFS vehicle ids")
    args = parser.parse_args()

    try:
        return run_gtfs(args) if args.gtfs else run_simulator(args)
    except KeyboardInterrupt:
        print("\nstopped")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
