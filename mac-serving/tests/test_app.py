from pathlib import Path
import asyncio

import httpx

from mac_serving.app import create_app
from mac_serving.config import (
    AppConfig,
    EngineConfig,
    FootprintConfig,
    ModelConfig,
    ServerConfig,
)


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        server=ServerConfig(),
        model=ModelConfig(tmp_path / "model.gguf", "test-model"),
        engine=EngineConfig(manage_process=False),
        footprint=FootprintConfig(),
        source=tmp_path / "config.toml",
    )


def test_control_plane_lifecycle_and_metrics(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path))

    async def exercise() -> tuple[httpx.Response, httpx.Response]:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/"), await client.get("/metrics")

    root, metrics = asyncio.run(exercise())

    assert root.status_code == 200
    assert root.json()["model"] == "test-model"
    assert metrics.status_code == 200
    assert "mac_serving_requests_total 1" in metrics.text


def test_api_key_is_checked_before_proxying(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MAC_SERVING_API_KEY", "secret")
    app = create_app(_config(tmp_path))

    async def exercise() -> httpx.Response:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/v1/models")

    response = asyncio.run(exercise())

    assert response.status_code == 401
