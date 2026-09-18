"""Lifecycle management for the native llama.cpp server process."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import os
from pathlib import Path
import shutil

from .config import AppConfig


class BackendConfigurationError(RuntimeError):
    """Raised when the native backend cannot be started safely."""


def resolve_binary(config: AppConfig) -> Path | None:
    configured = config.engine.binary
    if configured != "auto":
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = (config.source.parent / path).resolve()
        return path if path.is_file() else None

    installed = shutil.which("llama-server")
    if installed:
        return Path(installed).resolve()
    root = config.source.parent.parent
    for candidate in (
        root / "vendor" / "llama.cpp" / "build" / "bin" / "llama-server",
        root / "bin" / "llama-server",
    ):
        if candidate.is_file():
            return candidate.resolve()
    return None


def build_command(config: AppConfig, binary: Path | None = None) -> list[str]:
    executable = binary or resolve_binary(config)
    if executable is None:
        raise BackendConfigurationError(
            "llama-server was not found; run scripts/bootstrap.sh or set engine.binary"
        )
    if not config.model.path.is_file():
        raise BackendConfigurationError(f"GGUF model not found: {config.model.path}")

    engine = config.engine
    server = config.server
    command = [
        str(executable),
        "--model", str(config.model.path),
        "--alias", config.model.alias,
        "--host", server.backend_host,
        "--port", str(server.backend_port),
        "--ctx-size", str(engine.context_size),
        "--parallel", str(engine.parallel),
        "--n-gpu-layers", str(engine.gpu_layers),
        "--threads", str(engine.threads),
        "--batch-size", str(engine.batch_size),
        "--ubatch-size", str(engine.micro_batch_size),
        "--cache-type-k", engine.cache_type_k,
        "--cache-type-v", engine.cache_type_v,
        "--lazy-mode", engine.lazy_mode,
    ]
    if engine.flash_attention:
        command.extend(("--flash-attn", "on"))
    if engine.continuous_batching:
        command.append("--cont-batching")
    if not engine.cache_prompt:
        command.append("--no-cache-prompt")
    if engine.jinja:
        command.append("--jinja")
    if engine.mlock:
        command.extend(("--load-mode", "mmap+mlock"))
    return command


class LlamaCppBackend:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.process: asyncio.subprocess.Process | None = None
        self._log_handle: object | None = None

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    async def start(self) -> None:
        if not self.config.engine.manage_process or self.running:
            return
        command = build_command(self.config)
        log_path = self.config.source.parent.parent / "run" / "llama-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = log_path.open("ab", buffering=0)
        env = os.environ.copy()
        env.setdefault("GGML_METAL", "1")
        self.process = await asyncio.create_subprocess_exec(
            *command,
            stdout=self._log_handle,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        await self._wait_until_ready()

    async def _wait_until_ready(self) -> None:
        import httpx

        deadline = asyncio.get_running_loop().time() + self.config.server.startup_timeout_seconds
        async with httpx.AsyncClient(timeout=2.0) as client:
            while asyncio.get_running_loop().time() < deadline:
                if self.process is not None and self.process.returncode is not None:
                    raise RuntimeError(
                        f"llama-server exited during startup with code {self.process.returncode}"
                    )
                try:
                    response = await client.get(f"{self.config.backend_url}/health")
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.25)
        await self.stop()
        raise TimeoutError("llama-server did not become healthy before the startup timeout")

    async def stop(self) -> None:
        process = self.process
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=15)
            except TimeoutError:
                process.kill()
                await process.wait()
        self.process = None
        if self._log_handle is not None:
            self._log_handle.close()  # type: ignore[attr-defined]
            self._log_handle = None


def redacted_command(command: Sequence[str]) -> str:
    """Render an argv sequence without involving a shell."""
    import shlex

    return shlex.join(command)
