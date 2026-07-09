"""Configuration schemas.

The platform is configuration-driven by design. These Pydantic models define
the validated configuration surface consumed by the bootstrap layer and runtime
subsystems. Environment overrides are applied before validation.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, computed_field


class PlatformMetadataConfig(BaseModel):
    """Global platform metadata."""

    name: str = "foundation-ai-platform"
    environment: str = "development"


class GatewayConfig(BaseModel):
    """Gateway network settings."""

    host: str = "0.0.0.0"
    port: int = 8000
    enable_metrics: bool = True


class DatabaseConfig(BaseModel):
    """Database connectivity settings.

    The configuration intentionally captures the logical database shape rather
    than forcing callers to provide a raw SQLAlchemy URL. This keeps the config
    portable across SQLite, PostgreSQL, MySQL, and cloud-managed variants.
    """

    engine: str = "sqlite"
    path: str = "./data/platform.db"
    host: str = "localhost"
    port: int | None = None
    database: str = "llm_platform"
    username: str | None = None
    password: str | None = None
    driver: str | None = None
    url: str | None = None
    echo: bool = False

    @computed_field
    @property
    def sqlalchemy_url(self) -> str:
        """Build the SQLAlchemy URL for the configured database engine."""
        if self.url:
            return self.url

        engine = self.engine.lower()
        if engine == "sqlite":
            return f"sqlite+pysqlite:///{Path(self.path)}"
        if engine in {"postgres", "postgresql"}:
            driver = self.driver or "psycopg"
            port = self.port or 5432
            credentials = ""
            if self.username:
                credentials = self.username
                if self.password:
                    credentials = f"{credentials}:{self.password}"
                credentials = f"{credentials}@"
            return f"postgresql+{driver}://{credentials}{self.host}:{port}/{self.database}"
        if engine == "mysql":
            driver = self.driver or "pymysql"
            port = self.port or 3306
            credentials = ""
            if self.username:
                credentials = self.username
                if self.password:
                    credentials = f"{credentials}:{self.password}"
                credentials = f"{credentials}@"
            return f"mysql+{driver}://{credentials}{self.host}:{port}/{self.database}"
        raise ValueError(f"Unsupported database engine: {self.engine}")


class PluginConfig(BaseModel):
    """Plugin enablement settings."""

    enabled: list[str] = Field(default_factory=list)


class HuggingFaceGenerationDefaults(BaseModel):
    """Default generation parameters for the Transformers backend."""

    max_new_tokens: int = 96
    temperature: float = 0.0
    top_p: float = 1.0
    do_sample: bool = False


class HuggingFaceRuntimeConfig(BaseModel):
    """Runtime settings for the HuggingFace Transformers backend."""

    trust_remote_code: bool = False
    revision: str | None = None
    default_dtype: str = "auto"
    generation: HuggingFaceGenerationDefaults = Field(default_factory=HuggingFaceGenerationDefaults)


class OpenAICompatibleBackendConfig(BaseModel):
    """Settings for a remote OpenAI-compatible inference backend."""

    base_url: str | None = None
    api_key: str = "-"
    health_path: str = "/health"
    models_path: str = "/v1/models"
    chat_completions_path: str = "/v1/chat/completions"
    metrics_path: str = "/metrics"
    request_timeout_seconds: float = 300.0
    default_remote_model: str | None = None


class ServingConfig(BaseModel):
    """Serving runtime configuration.

    Attributes:
        implementation: The concrete runtime to instantiate at bootstrap time.
            Typical values are `fake` and `huggingface-transformers`.
        default_engine: The logical serving engine to prefer for model
            registrations and examples.
        supported_engines: Engines allowed by compatibility validation.
        default_placement: Preferred execution placement for local runtimes.
        fallback_placements: Ordered placement fallback list if the preferred
            placement is unavailable.
        model_cache_dir: Local cache directory used by model download
            workflows.
        huggingface: Runtime-specific configuration for Transformers hosting.
        vllm: Remote backend settings for vLLM's OpenAI-compatible server.
        tgi: Remote backend settings for TGI's Messages API.
    """

    implementation: str = "fake"
    default_engine: str = "vllm"
    supported_engines: list[str] = Field(default_factory=lambda: ["vllm", "tgi", "huggingface-transformers"])
    default_placement: str = "cpu"
    fallback_placements: list[str] = Field(default_factory=list)
    model_cache_dir: str = "./data/model-cache"
    gpu_vram_gb: int = 24  # Total GPU VRAM budget for model scheduling
    num_speculative_tokens: int = 5  # Default EAGLE speculative decode tokens
    huggingface: HuggingFaceRuntimeConfig = Field(default_factory=HuggingFaceRuntimeConfig)
    vllm: OpenAICompatibleBackendConfig = Field(default_factory=OpenAICompatibleBackendConfig)
    tgi: OpenAICompatibleBackendConfig = Field(default_factory=OpenAICompatibleBackendConfig)


class TelemetrySinkConfig(BaseModel):
    """Feature flag for an individual telemetry sink."""

    enabled: bool = False


class TelemetryConfig(BaseModel):
    """Telemetry backend configuration."""

    provider: str = "database"
    prometheus: TelemetrySinkConfig = Field(default_factory=lambda: TelemetrySinkConfig(enabled=True))
    opentelemetry: TelemetrySinkConfig = Field(default_factory=TelemetrySinkConfig)


class PlatformConfig(BaseModel):
    """Root platform configuration model."""

    platform: PlatformMetadataConfig = Field(default_factory=PlatformMetadataConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    serving: ServingConfig = Field(default_factory=ServingConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
