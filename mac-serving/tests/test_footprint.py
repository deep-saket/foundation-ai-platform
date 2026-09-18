from pathlib import Path

from mac_serving.config import (
    AppConfig,
    EngineConfig,
    FootprintConfig,
    ModelConfig,
    ServerConfig,
)
from mac_serving.footprint import estimate_footprint
from mac_serving.hardware import HardwareProfile


def test_32b_profile_fits_64_gib_with_headroom(tmp_path: Path) -> None:
    config = AppConfig(
        server=ServerConfig(),
        model=ModelConfig(tmp_path / "missing.gguf"),
        engine=EngineConfig(context_size=32768, parallel=4),
        footprint=FootprintConfig(),
        source=tmp_path / "config.toml",
    )
    hardware = HardwareProfile("Darwin", "arm64", "Mac16,6", "Apple M4 Max", 64 * 1024**3, 16, 12, 40, True)

    estimate = estimate_footprint(config, hardware)

    assert estimate.fits_safely
    assert estimate.context_per_slot == 8192
    assert estimate.weights_gib > 17
    assert estimate.headroom_gib > 20


def test_model_file_size_overrides_parameter_estimate(tmp_path: Path) -> None:
    model = tmp_path / "tiny.gguf"
    model.write_bytes(b"x" * 1024)
    config = AppConfig(
        ServerConfig(),
        ModelConfig(model),
        EngineConfig(),
        FootprintConfig(model_billions=70),
        tmp_path / "config.toml",
    )
    hardware = HardwareProfile("Darwin", "arm64", "Mac", "Apple", 16 * 1024**3, 8, 4, 10, True)

    assert estimate_footprint(config, hardware).weights_gib < 0.01
