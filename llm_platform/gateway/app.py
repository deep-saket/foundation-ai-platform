"""FastAPI application factory."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from llm_platform.bootstrap import PlatformApplication, PlatformApplicationBuilder
from llm_platform.gateway.routes import router, v1_router
from llm_platform.services.lifecycle_worker import run_lifecycle_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(run_lifecycle_loop(app))
    
    try:
        platform = app.state.platform_application
        asyncio.create_task(
            platform.chat_service.prewarm_capabilities(["chat", "summarization", "reasoning", "math"])
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to trigger pre-warm: {e}")
        
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


def create_app(platform_application: PlatformApplication) -> FastAPI:
    app = FastAPI(title="Foundation AI Platform", lifespan=lifespan)
    
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.state.platform_application = platform_application
    app.include_router(router)
    app.include_router(v1_router)
    return app



def create_default_app() -> FastAPI:
    """Build the default FastAPI app from 'configs/platform.yaml'."""
    return PlatformApplicationBuilder().create_fastapi_app("configs/platform.yaml")
