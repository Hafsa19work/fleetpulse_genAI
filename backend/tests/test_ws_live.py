"""WebSocket live feed (FR-30) and the hub's failure handling.

AI-generated from prompt P-18; the `broadcast_soon` tests are the regression suite
for defect D-06 — broadcasts triggered from a sync endpoint were silently dropped
because the worker thread has no running event loop.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.hub import ConnectionHub
from conftest import telemetry_payload


def test_connect_receives_a_greeting(client):
    with client.websocket_connect("/ws/live") as ws:
        assert ws.receive_json()["type"] == "connected"


def test_ingestion_pushes_a_vehicle_update(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})

    with client.websocket_connect("/ws/live") as ws:
        assert ws.receive_json()["type"] == "connected"
        client.post("/api/telemetry", json=telemetry_payload(latitude=24.99, speed_kph=12.0))

        message = ws.receive_json()
        assert message["type"] == "vehicle_update"
        assert message["vehicle"]["code"] == "BUS-01"
        assert message["vehicle"]["latitude"] == 24.99


def test_a_new_alert_is_pushed(client):
    client.post("/api/vehicles", json={"code": "BUS-01", "label": "b", "vehicle_type": "bus"})

    with client.websocket_connect("/ws/live") as ws:
        ws.receive_json()  # connected
        client.post("/api/telemetry", json=telemetry_payload(engine_temp_c=130.0))

        types = []
        payloads = []
        for _ in range(2):
            message = ws.receive_json()
            types.append(message["type"])
            payloads.append(message)

        assert "alert_raised" in types
        alert = next(m["alert"] for m in payloads if m["type"] == "alert_raised")
        assert alert["rule_code"] == "ENGINE_OVERHEAT"
        assert alert["severity"] == "critical"
        assert alert["vehicle_code"] == "BUS-01"


def test_client_count_is_tracked(client):
    assert client.get("/api/health").json()["websocket_clients"] == 0
    with client.websocket_connect("/ws/live") as ws:
        ws.receive_json()
        assert client.get("/api/health").json()["websocket_clients"] == 1
    # After the context manager exits the client is dropped again.
    assert client.get("/api/health").json()["websocket_clients"] == 0


# --------------------------------------------------------------------------
# Hub unit tests — no HTTP involved
# --------------------------------------------------------------------------


class FakeSocket:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[dict] = []
        self.fail = fail
        self.accepted = False
        self.closed = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self.fail:
            raise ConnectionResetError("client vanished")
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True


def test_broadcast_delivers_to_every_client():
    async def scenario():
        hub = ConnectionHub()
        a, b = FakeSocket(), FakeSocket()
        await hub.connect(a)
        await hub.connect(b)
        delivered = await hub.broadcast({"type": "ping"})
        return delivered, a.sent, b.sent, hub.client_count

    delivered, a_sent, b_sent, count = asyncio.run(scenario())
    assert delivered == 2
    assert a_sent == b_sent == [{"type": "ping"}]
    assert count == 2


def test_a_dead_client_is_pruned_not_propagated():
    """D-05: a closed browser tab must not turn into a 500 on the ingest request."""

    async def scenario():
        hub = ConnectionHub()
        good, dead = FakeSocket(), FakeSocket(fail=True)
        await hub.connect(good)
        await hub.connect(dead)
        delivered = await hub.broadcast({"type": "ping"})
        return delivered, hub.client_count, good.sent

    delivered, count, good_sent = asyncio.run(scenario())
    assert delivered == 1
    assert count == 1
    assert good_sent == [{"type": "ping"}]


def test_broadcast_soon_from_a_worker_thread_reaches_the_bound_loop():
    """D-06 regression: the sync-endpoint path must actually deliver."""

    async def scenario():
        hub = ConnectionHub()
        hub.bind_loop(asyncio.get_running_loop())
        socket = FakeSocket()
        await hub.connect(socket)

        await asyncio.to_thread(hub.broadcast_soon, {"type": "from_thread"})
        await asyncio.sleep(0.05)  # let the scheduled coroutine run
        return socket.sent

    assert asyncio.run(scenario()) == [{"type": "from_thread"}]


def test_broadcast_soon_without_a_loop_is_a_silent_no_op():
    hub = ConnectionHub()
    hub._clients.add(FakeSocket())  # noqa: SLF001 — exercising the no-loop branch
    hub.broadcast_soon({"type": "ignored"})  # must not raise


def test_broadcast_with_no_clients_is_free():
    async def scenario():
        hub = ConnectionHub()
        return await hub.broadcast({"type": "ping"})

    assert asyncio.run(scenario()) == 0


def test_disconnect_removes_the_client():
    async def scenario():
        hub = ConnectionHub()
        socket = FakeSocket()
        await hub.connect(socket)
        await hub.disconnect(socket)
        return hub.client_count

    assert asyncio.run(scenario()) == 0


def test_close_all_closes_and_clears():
    async def scenario():
        hub = ConnectionHub()
        socket = FakeSocket()
        await hub.connect(socket)
        await hub.close_all()
        return socket.closed, hub.client_count

    closed, count = asyncio.run(scenario())
    assert closed is True
    assert count == 0


@pytest.mark.parametrize("fail", [True, False])
def test_close_all_survives_a_socket_that_refuses_to_close(fail):
    class Stubborn(FakeSocket):
        async def close(self) -> None:
            if fail:
                raise RuntimeError("already gone")
            self.closed = True

    async def scenario():
        hub = ConnectionHub()
        socket = Stubborn()
        await hub.connect(socket)
        await hub.close_all()
        return hub.client_count

    assert asyncio.run(scenario()) == 0
