"""Reproducible demo dataset (NFR-10, docs/04-database-design.md §6).

    python -m app.seed          # create routes + vehicles if absent
    python -m app.seed --reset  # drop everything first

Telemetry is deliberately NOT seeded: the demo starts from a clean state and the
simulator fills it in live, so an examiner watches alerts appear rather than
finding them pre-cooked.
"""

from __future__ import annotations

import argparse
from datetime import timedelta

from sqlalchemy import select

from .database import Base, SessionLocal, engine, init_db, utcnow
from .enums import VehicleStatus, VehicleType
from .models import Delivery, Route, Stop, Vehicle, Waypoint

# Karachi city centre, roughly along Shahrah-e-Faisal and the northern bypass.
BUS_ROUTE_A = [
    (24.8607, 67.0011),
    (24.8629, 67.0208),
    (24.8664, 67.0402),
    (24.8712, 67.0601),
    (24.8775, 67.0798),
    (24.8841, 67.0995),
    (24.8890, 67.1197),
    (24.8918, 67.1400),
]
BUS_ROUTE_B = [
    (24.9204, 67.0289),
    (24.9111, 67.0455),
    (24.9018, 67.0620),
    (24.8925, 67.0786),
    (24.8832, 67.0951),
    (24.8739, 67.1117),
]
TRUCK_ROUTE = [
    (24.8100, 66.9800),
    (24.8450, 67.0150),
    (24.8800, 67.0500),
    (24.9200, 67.0900),
    (24.9600, 67.1350),
    (25.0000, 67.1800),
]


def _waypoints(points: list[tuple[float, float]]) -> list[Waypoint]:
    return [
        Waypoint(sequence=i, latitude=lat, longitude=lon)
        for i, (lat, lon) in enumerate(points)
    ]


def _stops(names: list[str], points: list[tuple[float, float]], headway_s: int) -> list[Stop]:
    return [
        Stop(
            sequence=i,
            name=name,
            latitude=points[i][0],
            longitude=points[i][1],
            scheduled_offset_s=headway_s * (i + 1),
        )
        for i, name in enumerate(names)
    ]


def seed(reset: bool = False) -> dict[str, int]:
    if reset:
        Base.metadata.drop_all(bind=engine)
    init_db()

    session = SessionLocal()
    created = {"routes": 0, "vehicles": 0, "deliveries": 0}
    try:
        if session.execute(select(Route).limit(1)).scalar_one_or_none() is not None and not reset:
            print("database already seeded — pass --reset to rebuild")
            return created

        route_a = Route(
            code="R-11A",
            name="Route 11A · City Centre → Airport Road",
            vehicle_type=VehicleType.BUS,
            speed_limit_kph=60.0,
            corridor_half_width_m=150.0,
            waypoints=_waypoints(BUS_ROUTE_A),
            stops=_stops(
                [
                    "Tower",
                    "Shahrah-e-Quaideen",
                    "Nursery",
                    "Drigh Road",
                    "Malir Halt",
                    "Airport Gate",
                ],
                BUS_ROUTE_A[1:7],
                headway_s=420,
            ),
        )
        route_b = Route(
            code="R-22B",
            name="Route 22B · North Nazimabad → Gulshan",
            vehicle_type=VehicleType.BUS,
            speed_limit_kph=55.0,
            corridor_half_width_m=120.0,
            waypoints=_waypoints(BUS_ROUTE_B),
            stops=_stops(
                ["Board Office", "Hyderi", "Nazimabad", "Liaquatabad", "Gulshan Chowrangi"],
                BUS_ROUTE_B[1:6],
                headway_s=480,
            ),
        )
        route_t = Route(
            code="TRK-NORTH",
            name="Northern distribution run",
            vehicle_type=VehicleType.TRUCK,
            speed_limit_kph=80.0,
            corridor_half_width_m=250.0,
            waypoints=_waypoints(TRUCK_ROUTE),
        )
        session.add_all([route_a, route_b, route_t])
        session.flush()
        created["routes"] = 3

        now = utcnow()
        # Every bus starts its trip now, so the schedule-delay rule begins from a
        # clean slate. Back-dating trip starts (an earlier version of this seed did)
        # makes the whole fleet fire SCHEDULE_DELAY on the first reading and drowns
        # out every other alert in the demo.
        vehicles: list[Vehicle] = []
        for i in range(1, 5):
            vehicles.append(
                Vehicle(
                    code=f"BUS-{i:02d}",
                    label=f"Bus {i:02d} (Route 11A)",
                    vehicle_type=VehicleType.BUS,
                    status=VehicleStatus.ACTIVE,
                    route_id=route_a.id,
                    trip_started_at=now,
                )
            )
        for i in range(5, 9):
            vehicles.append(
                Vehicle(
                    code=f"BUS-{i:02d}",
                    label=f"Bus {i:02d} (Route 22B)",
                    vehicle_type=VehicleType.BUS,
                    status=VehicleStatus.ACTIVE,
                    route_id=route_b.id,
                    trip_started_at=now,
                )
            )
        # Two frozen loads (-20…-15 °C) and two chilled loads (2…8 °C).
        bands = [(-20.0, -15.0), (-20.0, -15.0), (2.0, 8.0), (2.0, 8.0)]
        for i, (lo, hi) in enumerate(bands, start=1):
            vehicles.append(
                Vehicle(
                    code=f"TRK-{i:02d}",
                    label=f"Reefer truck {i:02d}",
                    vehicle_type=VehicleType.TRUCK,
                    status=VehicleStatus.ACTIVE,
                    route_id=route_t.id,
                    cargo_temp_min_c=lo,
                    cargo_temp_max_c=hi,
                )
            )
        session.add_all(vehicles)
        session.flush()
        created["vehicles"] = len(vehicles)

        trucks = [v for v in vehicles if v.vehicle_type is VehicleType.TRUCK]
        for index, truck in enumerate(trucks):
            for leg in range(2):
                session.add(
                    Delivery(
                        vehicle_id=truck.id,
                        reference=f"DL-{index + 1:02d}{leg + 1}",
                        destination_label=f"Depot {chr(ord('A') + leg)}",
                        destination_lat=TRUCK_ROUTE[-1][0] - 0.01 * leg,
                        destination_lon=TRUCK_ROUTE[-1][1] - 0.01 * leg,
                        due_at=now + timedelta(hours=2 + leg),
                    )
                )
                created["deliveries"] += 1

        session.commit()
        print(
            f"seeded {created['routes']} routes, {created['vehicles']} vehicles, "
            f"{created['deliveries']} deliveries"
        )
        return created
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the FleetPulse demo dataset")
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
