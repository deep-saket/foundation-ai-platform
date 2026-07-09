# `llm_platform` — Core Platform Package

The main Python package implementing the Foundation AI Platform. This package provides a modular, interface-driven architecture for registering, deploying, routing, and serving LLM models through a unified API gateway.

---

## Package Entry Points

### `__init__.py`

Package marker. Declares `llm_platform` as the top-level Python package.

---

### `bootstrap.py`

**Application bootstrap and dependency wiring.** This module assembles the entire platform from validated configuration and interface-backed implementations. It is intentionally explicit (no magic DI container) so the wiring remains understandable as the codebase grows.

#### Classes

| Class | Description |
|---|---|
| `PlatformApplication` | Dataclass holding all assembled platform dependencies (config, registry, router, lifecycle, telemetry, compatibility, model server, plugins, and services). Acts as the central application container. |
| `PlatformApplicationBuilder` | Builder that constructs a `PlatformApplication` from YAML configuration files or `PlatformConfig` objects. |

#### `PlatformApplicationBuilder` Methods

| Method | Signature | Use Case |
|---|---|---|
| `build_from_file` | `(path: str \| Path = "configs/platform.yaml") → PlatformApplication` | Load and validate a YAML config, then wire up and return a fully assembled application container. |
| `build_from_config` | `(config: PlatformConfig) → PlatformApplication` | Wire up the application from an already-validated config object. Used in tests and smoke scripts. |
| `create_fastapi_app` | `(path: str \| Path = "configs/platform.yaml") → FastAPI` | Convenience method that builds the application and wraps it in a FastAPI app ready to serve. |
| `_build_plugins` | `(config: PlatformConfig) → PluginManager` | Internal — loads plugin implementations (Qwen, Llama, Mistral, DeepSeek) enabled in configuration. |
| `_build_repositories` | `(config: PlatformConfig) → tuple` | Internal — constructs in-memory or SQLAlchemy-backed repositories depending on the database engine. |
| `_build_telemetry_provider` | `(config: PlatformConfig, telemetry_repository) → ITelemetryProvider` | Internal — builds the correct telemetry provider (Memory, Database, or NoOp) from config. |

---

## Sub-Packages

| Directory | Purpose |
|---|---|
| [`compatibility/`](compatibility/) | Model and deployment validation against platform-supported engines. HuggingFace model inspection. |
| [`database/`](database/) | SQLAlchemy ORM models, in-memory and SQL-backed repository implementations, session management. |
| [`gateway/`](gateway/) | FastAPI application factory, HTTP route definitions, and dependency injection helpers. |
| [`interfaces/`](interfaces/) | Abstract base classes (ABCs) defining contracts for all swappable components. |
| [`lifecycle/`](lifecycle/) | Deployment lifecycle state machine (HOT → WARM → COLD). |
| [`plugins/`](plugins/) | Model family plugins (Qwen, Llama, Mistral, DeepSeek) with declarative manifests. |
| [`registry/`](registry/) | Registry service implementation coordinating model, deployment, and lifecycle persistence. |
| [`routing/`](routing/) | Capability-based routing that selects eligible deployments for incoming requests. |
| [`schemas/`](schemas/) | Pydantic models for configuration, API payloads, registry records, routing, and telemetry. |
| [`services/`](services/) | Application-level service orchestration for chat completions, model management, and health. |
| [`serving/`](serving/) | Model server implementations — Fake, HuggingFace Transformers, vLLM, TGI, Docker manager. |
| [`telemetry/`](telemetry/) | Telemetry provider implementations (NoOp, Memory, Repository-backed). |
| [`utils/`](utils/) | Shared utilities — YAML config loading, custom exception hierarchy. |
