"""FleetPulse ASGI application.

Run with:  uvicorn app.main:app --reload  (from the backend/ directory)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import settings
from .database import SessionLocal, init_db
from .routers import alerts, config, fleet, ops, routes, telemetry, vehicles
from .services.hub import hub
from .services.ingestion import sweep_offline

logging.basicConfig(level=os.getenv("FLEETPULSE_LOG_LEVEL", "INFO"))
logger = logging.getLogger("fleetpulse")


async def _offline_sweeper() -> None:
    """Periodically look for vehicles that have gone quiet (FR-18, design D-7).

    The sweep is synchronous SQLAlchemy work, so it runs in a worker thread to
    keep the event loop free for ingestion and WebSocket traffic.
    """
    interval = settings.offline_sweep_interval_s
    while True:
        try:
            await asyncio.sleep(interval)
            await asyncio.to_thread(_sweep_once)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            # A failed sweep must never kill the loop — the next tick retries.
            logger.exception("offline sweep failed")


def _sweep_once() -> None:
    session = SessionLocal()
    try:
        created = sweep_offline(session)
        if created:
            logger.info("offline sweep raised %d alert(s)", len(created))
    finally:
        session.close()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    hub.bind_loop(asyncio.get_running_loop())
    task: asyncio.Task | None = None
    if os.getenv("FLEETPULSE_DISABLE_SWEEPER", "").lower() not in {"1", "true", "yes"}:
        task = asyncio.create_task(_offline_sweeper())
        logger.info("offline sweeper started (every %.0fs)", settings.offline_sweep_interval_s)
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await hub.close_all()


app = FastAPI(
    title="FleetPulse API",
    version=__version__,
    description=(
        "Real-time transportation fleet monitoring system. "
        "Final Term Project — Hafsa Aqeel (53317). "
        "Theme: July → Transportation, roll digit 7 → Monitoring System, "
        "Python → AI-generated tests."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (vehicles, routes, telemetry, alerts, fleet, config, ops):
    app.include_router(module.router)

root = APIRouter(tags=["meta"])


SERVE_STATIC = os.getenv("FLEETPULSE_SERVE_STATIC", "").lower() in {"1", "true", "yes"}


class SpaStaticFiles(StaticFiles):
    """StaticFiles with a history-API fallback.

    The dashboard pushes real URLs (`/alerts`, `/vehicles/BUS-03`) so the browser's
    Back button works, but those paths are not files on disk. Without this fallback
    a refresh or a shared deep link would 404.

    Only *extensionless* unknown paths fall through to index.html. A missing asset
    (`/assets/main.js`) still 404s, so a broken bundle reference stays visible
    instead of being masked by a 200 that returns HTML — which would surface much
    later as an unreadable JavaScript syntax error.
    """

    async def get_response(self, path: str, scope):  # noqa: ANN001, ANN201
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and "." not in Path(path).name:
                return await super().get_response("index.html", scope)
            raise


def _identity() -> dict:
    return {
        "name": "FleetPulse",
        "version": __version__,
        "student": "Hafsa Aqeel (53317)",
        "docs": "/docs",
        "websocket": "/ws/live",
    }


# Always available, and the only identity endpoint when the SPA owns "/".
root.add_api_route("/api/meta", _identity, methods=["GET"])

if not SERVE_STATIC:
    root.add_api_route("/", _identity, methods=["GET"])

app.include_router(root)


def _mount_spa(application: FastAPI) -> None:
    """Serve the built React bundle from the API process.

    Opt-in via FLEETPULSE_SERVE_STATIC=1, which the Docker image sets. Off by
    default so local development keeps using the Vite dev server (with hot reload)
    and so the test suite still sees the JSON index at "/".

    Mounted last: Starlette matches routes in order, so every /api and /ws route is
    resolved before this catch-all ever sees the request.
    """
    if not SERVE_STATIC:
        return

    static_dir = Path(os.getenv("FLEETPULSE_STATIC_DIR", "/app/static"))
    if not (static_dir / "index.html").exists():
        logger.warning("FLEETPULSE_SERVE_STATIC is set but %s has no index.html", static_dir)
        return

    application.mount("/", SpaStaticFiles(directory=str(static_dir), html=True), name="spa")
    logger.info("serving the dashboard from %s", static_dir)


@app.websocket("/ws/live")
async def live(websocket: WebSocket) -> None:
    """Live fleet feed (FR-30).

    The server pushes; the client's messages are ignored apart from keeping the
    socket warm. The receive loop exists only to notice a disconnect promptly.
    """
    await hub.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "version": __version__})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.debug("websocket closed abnormally", exc_info=True)
    finally:
        await hub.disconnect(websocket)


# Must run after every router and the WebSocket route are registered — the SPA
# mount is a catch-all and would otherwise shadow them.
_mount_spa(app)
