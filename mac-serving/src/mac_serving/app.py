"""FastAPI control plane and transparent OpenAI-compatible proxy."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
import httpx

from . import __version__
from .backend import LlamaCppBackend
from .config import AppConfig, default_config_path, load_config
from .footprint import estimate_footprint
from .hardware import detect_hardware

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
}


class Metrics:
    def __init__(self) -> None:
        self.requests = 0
        self.failures = 0
        self.in_flight = 0
        self.total_seconds = 0.0
        self.started = time.monotonic()
        self._lock = asyncio.Lock()

    async def begin(self) -> float:
        async with self._lock:
            self.requests += 1
            self.in_flight += 1
        return time.monotonic()

    async def finish(self, started: float, failed: bool) -> None:
        async with self._lock:
            self.in_flight -= 1
            self.total_seconds += time.monotonic() - started
            if failed:
                self.failures += 1

    def render(self) -> str:
        return "\n".join(
            (
                "# TYPE mac_serving_requests_total counter",
                f"mac_serving_requests_total {self.requests}",
                "# TYPE mac_serving_failures_total counter",
                f"mac_serving_failures_total {self.failures}",
                "# TYPE mac_serving_requests_in_flight gauge",
                f"mac_serving_requests_in_flight {self.in_flight}",
                "# TYPE mac_serving_request_duration_seconds_total counter",
                f"mac_serving_request_duration_seconds_total {self.total_seconds:.6f}",
                "# TYPE mac_serving_uptime_seconds gauge",
                f"mac_serving_uptime_seconds {time.monotonic() - self.started:.3f}",
                "",
            )
        )


def create_app(config: AppConfig | None = None) -> FastAPI:
    settings = config or load_config(default_config_path())
    backend = LlamaCppBackend(settings)
    metrics = Metrics()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.backend = backend
        app.state.client = httpx.AsyncClient(
            base_url=settings.backend_url,
            timeout=httpx.Timeout(connect=5.0, read=None, write=60.0, pool=5.0),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=8),
        )
        await backend.start()
        try:
            yield
        finally:
            await app.state.client.aclose()
            await backend.stop()

    app = FastAPI(
        title="Foundation Mac Serving",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )

    @app.middleware("http")
    async def observe(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path == "/metrics":
            return await call_next(request)
        started = await metrics.begin()
        failed = False
        try:
            response = await call_next(request)
            failed = response.status_code >= 500
            return response
        except Exception:
            failed = True
            raise
        finally:
            await metrics.finish(started, failed)

    @app.get("/")
    async def root() -> dict[str, object]:
        return {
            "name": "foundation-mac-serving",
            "version": __version__,
            "model": settings.model.alias,
            "api": "/v1/chat/completions" if settings.model.chat else "/v1/completions",
        }

    async def backend_healthy() -> bool:
        try:
            response = await app.state.client.get("/health", timeout=2.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    @app.get("/healthz")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "backend": "up" if await backend_healthy() else "down",
            "managed_process": settings.engine.manage_process,
        }

    @app.get("/readyz")
    async def ready() -> JSONResponse:
        healthy = await backend_healthy()
        return JSONResponse(
            {"status": "ready" if healthy else "not_ready"},
            status_code=200 if healthy else 503,
        )

    @app.get("/footprint")
    async def footprint() -> dict[str, object]:
        return estimate_footprint(settings, detect_hardware()).as_dict()

    @app.get("/metrics", response_class=PlainTextResponse)
    async def prometheus_metrics() -> str:
        return metrics.render()

    async def verify_api_key(request: Request) -> None:
        expected = os.getenv(settings.server.api_key_env)
        if expected and request.headers.get("authorization") != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="invalid API key")

    async def stream_and_close(response: httpx.Response) -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_raw():
                yield chunk
        finally:
            await response.aclose()

    @app.api_route("/v1/{path:path}", methods=["GET", "POST", "DELETE"])
    async def proxy_v1(path: str, request: Request) -> StreamingResponse:
        await verify_api_key(request)
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in HOP_BY_HOP and key.lower() != "host"
        }
        upstream_request = app.state.client.build_request(
            request.method,
            f"/v1/{path}",
            params=request.query_params,
            headers=headers,
            content=await request.body(),
        )
        try:
            upstream = await app.state.client.send(upstream_request, stream=True)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="inference backend unavailable") from exc
        response_headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in HOP_BY_HOP
        }
        return StreamingResponse(
            stream_and_close(upstream),
            status_code=upstream.status_code,
            headers=response_headers,
            media_type=upstream.headers.get("content-type"),
        )

    return app


app = create_app()
