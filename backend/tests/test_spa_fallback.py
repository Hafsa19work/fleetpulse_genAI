"""History-API fallback for the built SPA (prompt P-34).

The dashboard pushes real URLs so the browser's Back button works. Those paths are
not files on disk, so the static mount has to fall back to index.html — but only
for paths that could plausibly be a screen, never for a missing asset.

Mounted on a throwaway app over a temp directory: this behaviour belongs to
`SpaStaticFiles`, not to the FleetPulse routes, and testing it in isolation keeps
it independent of whether a real `dist/` has been built.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import SpaStaticFiles


@pytest.fixture
def spa_client(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>FleetPulse</title>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('bundle')")

    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.mount("/", SpaStaticFiles(directory=str(tmp_path), html=True), name="spa")
    with TestClient(app) as client:
        yield client


def test_root_serves_the_app(spa_client):
    response = spa_client.get("/")
    assert response.status_code == 200
    assert "FleetPulse" in response.text


def test_a_real_asset_is_served_as_itself(spa_client):
    response = spa_client.get("/assets/app.js")
    assert response.status_code == 200
    assert "bundle" in response.text


@pytest.mark.parametrize("path", ["/alerts", "/settings", "/vehicles/BUS-03", "/anything/deep"])
def test_screen_urls_fall_back_to_the_app(spa_client, path):
    """A refresh or a shared deep link must load the dashboard, not a 404."""
    response = spa_client.get(path)
    assert response.status_code == 200
    assert "FleetPulse" in response.text


def test_a_missing_asset_still_404s(spa_client):
    """Masking this with a 200 + HTML would turn a broken bundle reference into an
    unreadable JavaScript syntax error much later."""
    assert spa_client.get("/assets/does-not-exist.js").status_code == 404


def test_the_mount_does_not_shadow_the_api(spa_client):
    assert spa_client.get("/api/health").json() == {"status": "ok"}
