"""Local bootstrap entrypoint for database initialization and sample data loading."""

from __future__ import annotations

from pathlib import Path

import yaml
from alembic import command
from alembic.config import Config

from llm_platform.bootstrap import PlatformApplicationBuilder
from llm_platform.schemas.config import PlatformConfig
from llm_platform.schemas.registry import DeploymentCreateRequest, ModelRegistrationRequest
from llm_platform.utils.config_loader import ConfigLoader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "platform.yaml"
DEFAULT_CATALOG_PATH = ROOT / "configs" / "models" / "catalog.yaml"


def load_platform_config(config_path: Path = DEFAULT_CONFIG_PATH) -> PlatformConfig:
    return ConfigLoader().load(config_path, PlatformConfig)


def run_migrations(config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    platform_config = load_platform_config(config_path)
    if platform_config.database.engine.lower() == "sqlite":
        Path(platform_config.database.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    alembic_config = Config(str(ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(ROOT / "alembic"))
    alembic_config.set_main_option("platform_config_path", str(config_path))
    alembic_config.set_main_option("sqlalchemy.url", platform_config.database.sqlalchemy_url)
    command.upgrade(alembic_config, "head")


def resolve_catalog_path(config_path: Path, catalog_path: Path | None = None) -> Path:
    if catalog_path is not None:
        return catalog_path
    colocated = config_path.parent / "configs" / "models" / "catalog.yaml"
    if colocated.exists():
        return colocated
    return DEFAULT_CATALOG_PATH


def load_sample_data(config_path: Path = DEFAULT_CONFIG_PATH, catalog_path: Path | None = None) -> None:
    application = PlatformApplicationBuilder().build_from_file(config_path)
    if application.model_management_service.list_models():
        return

    resolved_catalog = resolve_catalog_path(config_path, catalog_path)
    with resolved_catalog.open("r", encoding="utf-8") as handle:
        catalog = yaml.safe_load(handle) or {}

    for item in catalog.get("models", []):
        application.model_management_service.register_model(ModelRegistrationRequest(**item))


def bootstrap(config_path: Path = DEFAULT_CONFIG_PATH, catalog_path: Path | None = None) -> None:
    run_migrations(config_path)
    load_sample_data(config_path, catalog_path)


if __name__ == "__main__":
    bootstrap()
