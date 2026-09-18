"""Typed TOML configuration with paths resolved relative to the config file."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    backend_host: str = "127.0.0.1"
    backend_port: int = 8081
    startup_timeout_seconds: float = 300.0
    api_key_env: str = "MAC_SERVING_API_KEY"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    path: Path
    alias: str = "local-model"
    chat: bool = True


@dataclass(frozen=True, slots=True)
class EngineConfig:
    binary: str = "auto"
    manage_process: bool = True
    gpu_layers: str | int = "all"
    threads: int = 8
    context_size: int = 8192
    parallel: int = 1
    batch_size: int = 512
    micro_batch_size: int = 256
    cache_type_k: str = "q8_0"
    cache_type_v: str = "q8_0"
    flash_attention: bool = True
    continuous_batching: bool = True
    cache_prompt: bool = False
    lazy_mode: str = "auto"
    jinja: bool = True
    mlock: bool = False


@dataclass(frozen=True, slots=True)
class FootprintConfig:
    model_billions: float = 32.0
    quant_bits: float = 4.85
    layers: int = 64
    attention_heads: int = 40
    kv_heads: int = 8
    hidden_size: int = 5120
    head_dim: int | None = None
    cache_bytes: float = 1.0625


@dataclass(frozen=True, slots=True)
class AppConfig:
    server: ServerConfig
    model: ModelConfig
    engine: EngineConfig
    footprint: FootprintConfig
    source: Path

    @property
    def backend_url(self) -> str:
        return f"http://{self.server.backend_host}:{self.server.backend_port}"


def _section(data: dict[str, object], name: str) -> dict[str, object]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"[{name}] must be a TOML table")
    return value


def load_config(path: str | Path) -> AppConfig:
    source = Path(path).expanduser().resolve()
    with source.open("rb") as handle:
        data = tomllib.load(handle)

    server = ServerConfig(**_section(data, "server"))
    engine = EngineConfig(**_section(data, "engine"))
    footprint = FootprintConfig(**_section(data, "footprint"))
    model_values = _section(data, "model")
    if "path" not in model_values:
        raise ValueError("[model].path is required")
    model_path = Path(str(model_values["path"])).expanduser()
    if not model_path.is_absolute():
        model_path = (source.parent / model_path).resolve()
    model = ModelConfig(
        path=model_path,
        alias=str(model_values.get("alias", "local-model")),
        chat=bool(model_values.get("chat", True)),
    )

    if server.host not in {"127.0.0.1", "localhost", "::1"} and not os.getenv(server.api_key_env):
        raise ValueError(
            f"Refusing non-loopback bind {server.host!r} without {server.api_key_env}"
        )
    if engine.parallel < 1 or engine.context_size < engine.parallel:
        raise ValueError("engine.parallel must be positive and no larger than context_size")
    if engine.micro_batch_size > engine.batch_size:
        raise ValueError("engine.micro_batch_size cannot exceed engine.batch_size")
    if engine.lazy_mode not in {"auto", "on", "off"}:
        raise ValueError("engine.lazy_mode must be auto, on, or off")

    return AppConfig(server, model, engine, footprint, source)


def default_config_path() -> Path:
    override = os.getenv("MAC_SERVING_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "config" / "mac-serving.toml"
