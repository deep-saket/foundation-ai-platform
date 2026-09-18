from pathlib import Path

import pytest

from mac_serving.config import load_config


def test_project_config_is_tuned_for_detected_mac() -> None:
    path = Path(__file__).parents[1] / "config" / "mac-serving.toml"
    config = load_config(path)

    assert config.engine.gpu_layers == "all"
    assert config.engine.threads == 12
    assert config.engine.parallel == 4
    assert config.engine.context_size // config.engine.parallel == 16384
    assert config.model.path.parent.name == "models"
    assert config.model.alias == "gemma-4-E4B"
    assert not config.model.chat
    assert config.footprint.model_billions == 8.0
    assert config.engine.cache_prompt
    assert config.engine.lazy_mode == "auto"


def test_public_bind_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('[server]\nhost = "0.0.0.0"\n[model]\npath = "model.gguf"\n')
    monkeypatch.delenv("MAC_SERVING_API_KEY", raising=False)

    with pytest.raises(ValueError, match="non-loopback"):
        load_config(config_file)
