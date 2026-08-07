"""WebSocket fan-out hub (FR-30).

A failed send prunes the client rather than propagating: a browser tab closed
mid-broadcast must never turn into a 500 on the telemetry ingestion request that
happened to trigger the broadcast. That was defect D-05 in the AI review pass.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

logger = logging.getLogger("fleetpulse.hub")


class ConnectionHub:
    def __init__(self) -> None:
        self._clients: set[Any] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: set[asyncio.Task] = set()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the application's event loop.

        Sync endpoints (`def` rather than `async def`) execute in a worker thread
        where `asyncio.get_running_loop()` raises, so without this reference every
        broadcast triggered by telemetry ingestion was silently dropped — defect
        D-06 in docs/09-test-report.md.
        """
        self._loop = loop

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: Any) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: Any) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, message: dict) -> int:
        """Send to every client; drop the ones that fail. Returns the delivered count."""
        async with self._lock:
            targets = list(self._clients)
        delivered = 0
        dead: list[Any] = []
        for client in targets:
            try:
                await client.send_json(message)
                delivered += 1
            except Exception as exc:  # noqa: BLE001
                logger.debug("pruning dead websocket client: %s", exc)
                dead.append(client)
        if dead:
            async with self._lock:
                for client in dead:
                    self._clients.discard(client)
        return delivered

    def broadcast_soon(self, message: dict) -> None:
        """Fire-and-forget broadcast, callable from sync or async context.

        Three cases, in order: already on the event loop (async caller), on a
        worker thread with a bound loop (sync endpoint — the common case for
        telemetry ingestion), or no loop at all (unit tests, CLI) where the
        broadcast is simply a no-op because nobody can be listening.
        """
        if not self._clients:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            task = loop.create_task(self.broadcast(message))
            # Keep a reference so the task is not garbage-collected mid-flight.
            self._pending.add(task)
            task.add_done_callback(self._pending.discard)
            return

        if self._loop is not None and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)

    async def close_all(self) -> None:
        async with self._lock:
            targets = list(self._clients)
            self._clients.clear()
        for client in targets:
            with contextlib.suppress(Exception):
                await client.close()


hub = ConnectionHub()
