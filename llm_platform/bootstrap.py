"""Application bootstrap and dependency wiring.

This module assembles the platform from validated configuration and interface-
backed implementations. It is intentionally explicit rather than magical so the
wiring remains understandable as the repository grows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from llm_platform.compatibility.checker import DefaultCompatibilityChecker
from llm_platform.database.repositories import (
    InMemoryDeploymentRepository,
    InMemoryLifecycleRepository,
    InMemoryModelRepository,
    InMemoryTelemetryRepository,
    SQLAlchemyDeploymentRepository,
    SQLAlchemyLifecycleRepository,
    SQLAlchemyModelRepository,
    SQLAlchemyTelemetryRepository,
)
from llm_platform.database.session import DatabaseSessionManager
from llm_platform.interfaces.compatibility import ICompatibilityChecker
from llm_platform.interfaces.lifecycle import ILifecycleManager
from llm_platform.interfaces.model_server import IModelServer
from llm_platform.interfaces.registry import IRegistry
from llm_platform.interfaces.router import IRouter
from llm_platform.interfaces.telemetry import ITelemetryProvider
from llm_platform.lifecycle.manager import SimpleLifecycleManager
from llm_platform.plugins.deepseek import DeepSeekPlugin
from llm_platform.plugins.llama import LlamaPlugin
from llm_platform.plugins.manager import PluginManager
from llm_platform.plugins.mistral import MistralPlugin
from llm_platform.plugins.qwen import QwenPlugin
from llm_platform.registry.service import RegistryService
from llm_platform.routing.router import CapabilityRouter
from llm_platform.schemas.config import PlatformConfig
from llm_platform.services.chat import ChatService
from llm_platform.services.gpu_tracker import GPUResourceTracker
from llm_platform.services.health import HealthService
from llm_platform.services.model_management import ModelManagementService
from llm_platform.serving.factory import build_model_server
from llm_platform.telemetry.providers import MemoryTelemetryProvider, NoOpTelemetryProvider, RepositoryTelemetryProvider
from llm_platform.utils.config_loader import ConfigLoader

if TYPE_CHECKING:
    from fastapi import FastAPI


def _read_model_vram_from_cache(model_dir: Path) -> int:
    """Compute required VRAM (GB) by reading actual weight files from the
    HuggingFace cache directory for a single model.

    Resolution order (all offline, no network calls):
    1. ``model.safetensors.index.json`` → ``metadata.total_size`` (bytes)
       This file is present for any sharded model (7B+).
    2. Sum of all ``*.safetensors`` files in the snapshot
       (single-file models like 0.5B, 1.5B).
    3. Sum of all ``*.bin`` files (older PyTorch format).
    4. Name-based heuristic as absolute last resort.

    Adds 20 % overhead on top of raw weight size to account for KV cache,
    activations, and CUDA context, then rounds up to the nearest GB.
    """
    import json
    import math

    # ── 1. Locate the active snapshot directory ───────────────────────
    snapshot_dir = None
    refs_main = model_dir / "refs" / "main"
    if refs_main.exists():
        commit_hash = refs_main.read_text().strip()
        candidate = model_dir / "snapshots" / commit_hash
        if candidate.is_dir():
            snapshot_dir = candidate

    # Fallback: most recently modified snapshot (handles detached HEAD etc.)
    if snapshot_dir is None:
        snapshots_root = model_dir / "snapshots"
        if snapshots_root.is_dir():
            candidates = sorted(
                snapshots_root.iterdir(),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                snapshot_dir = candidates[0]

    if snapshot_dir is None:
        # Nothing usable on disk — fall back to name heuristic
        return _estimate_vram_gb_from_name(model_dir.name)

    total_bytes = 0

    # ── 2a. Sharded safetensors index ────────────────────────────────
    index_file = snapshot_dir / "model.safetensors.index.json"
    if not index_file.exists():
        # Some models use a different prefix (e.g. pytorch_model)
        for candidate in snapshot_dir.glob("*.index.json"):
            index_file = candidate
            break

    if index_file.exists():
        try:
            with open(index_file, encoding="utf-8") as f:
                idx = json.load(f)
            total_bytes = int(idx.get("metadata", {}).get("total_size", 0))
        except Exception:
            total_bytes = 0

    # ── 2b. Single-file safetensors ───────────────────────────────────
    if total_bytes == 0:
        for sf in snapshot_dir.glob("*.safetensors"):
            total_bytes += sf.stat().st_size

    # ── 2c. PyTorch .bin files ────────────────────────────────────────
    if total_bytes == 0:
        for bf in snapshot_dir.glob("*.bin"):
            total_bytes += bf.stat().st_size

    if total_bytes == 0:
        return _estimate_vram_gb_from_name(model_dir.name)

    # ── 3. Convert bytes → GB with a flat 2GB overhead ───────────────
    raw_gb = total_bytes / (1024 ** 3)
    vram_gb = math.ceil(raw_gb) + 2
    return max(vram_gb, 3)


def _estimate_vram_gb_from_name(dir_or_repo_name: str) -> int:
    """Last-resort heuristic: parse parameter count from the model name.

    Only used when no weight files are found on disk (e.g. model is
    registered before download completes).
    """
    name = dir_or_repo_name.lower()
    for suffix, gb in [
        ("70b", 140), ("72b", 144),
        ("34b",  70), ("32b",  65),
        ("13b",  26), ("14b",  29),
        ("7b",   15), ("8b",   16),
        ("3b",    7), ("2.5b",  6),
        ("1.8b",  4), ("1.5b",  4), ("1.1b",  3),
        ("0.5b",  2), ("0.5",   2),
    ]:
        if suffix in name:
            return gb
    return 8  # conservative default


@dataclass(slots=True)
class PlatformApplication:
    """Assembled platform dependencies.

    Attributes:
        config: Validated platform configuration.
        registry: Registry service used across the application.
        router: Capability-based routing implementation.
        lifecycle_manager: Lifecycle manager for deployment state.
        telemetry_provider: Active telemetry sink.
        compatibility_checker: Validation layer for model compatibility.
        model_server: Active serving backend implementation.
        plugin_manager: Registered plugin manager instance.
        model_management_service: Service for registration and deployment
            workflows.
        chat_service: Service for completion workflows.
        health_service: Service for health and metrics summary.
    """

    config: PlatformConfig
    registry: IRegistry
    router: IRouter
    lifecycle_manager: ILifecycleManager
    telemetry_provider: ITelemetryProvider
    compatibility_checker: ICompatibilityChecker
    model_server: IModelServer
    plugin_manager: PluginManager
    model_management_service: ModelManagementService
    chat_service: ChatService
    health_service: HealthService
    gpu_tracker: GPUResourceTracker


class PlatformApplicationBuilder:
    """Create a platform application from configuration."""

    def __init__(self, config_loader: ConfigLoader | None = None) -> None:
        """Initialize the application builder.

        Args:
            config_loader: Optional configuration loader override for tests or
                custom environments.
        """
        self._config_loader = config_loader or ConfigLoader()

    def build_from_file(self, path: str | Path = "configs/platform.yaml") -> PlatformApplication:
        """Build an application from a YAML configuration file.

        Args:
            path: Path to the platform configuration file.

        Returns:
            Fully assembled application container.
        """
        config = self._config_loader.load(path, PlatformConfig)
        return self.build_from_config(config)

    def build_from_config(self, config: PlatformConfig) -> PlatformApplication:
        """Build an application from an already validated config object."""
        plugin_manager = self._build_plugins(config)
        model_repository, deployment_repository, lifecycle_repository, telemetry_repository = self._build_repositories(
            config
        )
        if config.database.engine.lower() != "memory":
            session_manager = DatabaseSessionManager(config.database)
            from llm_platform.database.models import Base
            Base.metadata.create_all(bind=session_manager.engine)

        registry = RegistryService(
            model_repository=model_repository,
            deployment_repository=deployment_repository,
            lifecycle_repository=lifecycle_repository,
        )
        lifecycle_manager = SimpleLifecycleManager()
        gpu_tracker = GPUResourceTracker(
            total_vram_gb=getattr(config.serving, 'gpu_vram_gb', 18)
        )
        from llm_platform.services.concurrency import ConcurrencyTracker
        concurrency_tracker = ConcurrencyTracker()

        router = CapabilityRouter(gpu_tracker=gpu_tracker, concurrency_tracker=concurrency_tracker)
        model_server = build_model_server(config.serving)
        compatibility_checker = DefaultCompatibilityChecker(
            set(config.serving.supported_engines),
            compatibility_config_path="configs/validation/backend_compatibility.yaml",
        )
        telemetry_provider = self._build_telemetry_provider(config, telemetry_repository)
        model_management_service = ModelManagementService(
            registry=registry,
            model_server=model_server,
            compatibility_checker=compatibility_checker,
            lifecycle_manager=lifecycle_manager,
        )
        chat_service = ChatService(
            registry=registry,
            router=router,
            lifecycle_manager=lifecycle_manager,
            telemetry_provider=telemetry_provider,
            model_server=model_server,
            compatibility_checker=compatibility_checker,
            model_cache_dir=getattr(config.serving, 'model_cache_dir', './data/model-cache'),
            gpu_tracker=gpu_tracker,
            concurrency_tracker=concurrency_tracker,
            num_speculative_tokens=getattr(config.serving, 'num_speculative_tokens', 5),
        )
        health_service = HealthService(model_server=model_server, telemetry_provider=telemetry_provider)

        try:
            # Auto-create tables if they don't exist
            if config.database.engine.lower() == "sqlite":
                from pathlib import Path
                Path(config.database.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
                from sqlalchemy import create_engine
                from llm_platform.database.models import Base
                engine = create_engine(config.database.sqlalchemy_url)
                Base.metadata.create_all(bind=engine)

            existing_models = model_repository.list()
            
            # Auto-sync models found on SSD cache into the database
            import uuid
            from datetime import datetime, timezone
            from llm_platform.schemas.registry import ModelRecord, DeploymentRecord
            from llm_platform.schemas.enums import ModelStatus, DeploymentStatus
            from pathlib import Path
            
            cache_path = Path(getattr(config.serving, 'model_cache_dir', './data/model-cache')).expanduser().resolve()
            if cache_path.exists():
                for d in cache_path.iterdir():
                    if d.is_dir() and d.name.startswith("models--"):
                        repo_id = d.name.replace("models--", "").replace("--", "/")
                        
                        # Skip large models (7B+) that would starve smaller models on a single GPU
                        vram_estimate = _read_model_vram_from_cache(d)
                        if vram_estimate > 10:
                            print(f"[SSD Sync] Skipping large model {repo_id} ({vram_estimate}GB) to preserve GPU for multi-model serving.")
                            continue
                        
                        if not any(m.name == repo_id for m in existing_models):
                            print(f"[SSD Sync] Found un-registered model on SSD: {repo_id}. Auto-registering...")
                            model_id = str(uuid.uuid4())
                            
                            # Assign capabilities based on model identity
                            repo_id_lower = repo_id.lower()
                            capabilities = ["chat"]
                            if "phi-3" in repo_id_lower:
                                capabilities = ["math"]
                            elif "deepseek" in repo_id_lower:
                                capabilities = ["reasoning"]
                            elif "qwen" in repo_id_lower:
                                capabilities = ["summarization"]
                            
                            new_model = ModelRecord(
                                id=model_id,
                                name=repo_id,
                                version="latest",
                                family="unknown",
                                engine="vllm",
                                capabilities=capabilities,
                                memory_requirement_gb=_read_model_vram_from_cache(d),
                                ownership="system",
                                status=ModelStatus.REGISTERED,
                                created_at=datetime.now(timezone.utc),
                                metadata={"from_ssd_sync": True}
                            )
                            model_repository.save(new_model)
                            
                            new_deployment = DeploymentRecord(
                                deployment_id=str(uuid.uuid4()),
                                model_id=model_id,
                                endpoint="http://localhost:pending",
                                engine="vllm",
                                status=DeploymentStatus.PENDING,
                                created_at=datetime.now(timezone.utc),
                                metadata={}
                            )
                            deployment_repository.save(new_deployment)
                            vram = _read_model_vram_from_cache(d)
                            print(f"[SSD Sync] Successfully registered {repo_id} as PENDING.")
            
            existing_models = model_repository.list()
            print(f"[Bootstrap] Initialized with {len(existing_models)} models in registry.")
                
        except Exception as e:
            print(f"Seeding issue: {e}")


        return PlatformApplication(
            config=config,
            registry=registry,
            router=router,
            lifecycle_manager=lifecycle_manager,
            telemetry_provider=telemetry_provider,
            compatibility_checker=compatibility_checker,
            model_server=model_server,
            plugin_manager=plugin_manager,
            model_management_service=model_management_service,
            chat_service=chat_service,
            health_service=health_service,
            gpu_tracker=gpu_tracker,
        )

    def create_fastapi_app(self, path: str | Path = "configs/platform.yaml") -> "FastAPI":
        """Build and return a FastAPI application for the given config file."""
        from llm_platform.gateway.app import create_app

        return create_app(self.build_from_file(path))

    def _build_plugins(self, config: PlatformConfig) -> PluginManager:
        """Load plugin implementations enabled in configuration."""
        available_plugins = {
            "qwen": QwenPlugin,
            "llama": LlamaPlugin,
            "mistral": MistralPlugin,
            "deepseek": DeepSeekPlugin,
        }
        plugin_manager = PluginManager()
        for plugin_id in config.plugins.enabled:
            plugin_class = available_plugins.get(plugin_id)
            if plugin_class:
                plugin_manager.register(plugin_class())
        return plugin_manager

    def _build_repositories(self, config: PlatformConfig):
        """Build repository implementations for the configured database."""
        engine = config.database.engine.lower()
        if engine == "memory":
            return (
                InMemoryModelRepository(),
                InMemoryDeploymentRepository(),
                InMemoryLifecycleRepository(),
                InMemoryTelemetryRepository(),
            )

        session_manager = DatabaseSessionManager(config.database)
        session_factory = session_manager.session_scope
        return (
            SQLAlchemyModelRepository(session_factory),
            SQLAlchemyDeploymentRepository(session_factory),
            SQLAlchemyLifecycleRepository(session_factory),
            SQLAlchemyTelemetryRepository(session_factory),
        )

    def _build_telemetry_provider(self, config: PlatformConfig, telemetry_repository) -> ITelemetryProvider:
        """Build the configured telemetry provider."""
        if config.telemetry.provider == "memory":
            return MemoryTelemetryProvider(telemetry_repository)
        if config.telemetry.provider == "database":
            return RepositoryTelemetryProvider(telemetry_repository)
        return NoOpTelemetryProvider()
