from pathlib import Path

from mac_serving.backend import build_command
from mac_serving.config import (
    AppConfig,
    EngineConfig,
    FootprintConfig,
    ModelConfig,
    ServerConfig,
)


def test_native_command_contains_metal_throughput_settings(tmp_path: Path) -> None:
    binary = tmp_path / "llama-server"
    model = tmp_path / "model.gguf"
    binary.touch()
    model.touch()
    config = AppConfig(
        ServerConfig(backend_port=9091),
        ModelConfig(model, "test-model"),
        EngineConfig(context_size=32768, parallel=4, threads=12),
        FootprintConfig(),
        tmp_path / "config.toml",
    )

    command = build_command(config, binary)

    assert command[0] == str(binary)
    assert command[command.index("--parallel") + 1] == "4"
    assert command[command.index("--n-gpu-layers") + 1] == "all"
    assert command[command.index("--lazy-mode") + 1] == "auto"
    assert "--flash-attn" in command
    assert command[command.index("--flash-attn") + 1] == "on"
    assert "--cont-batching" in command
    assert "--no-cache-prompt" in command
    assert "--jinja" in command
