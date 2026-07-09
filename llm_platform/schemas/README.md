# `schemas/` — Pydantic Data Models

Centralized Pydantic schemas used across the entire platform for configuration, API payloads, registry records, routing decisions, telemetry events, and validation reports. These models are intentionally transport-agnostic so they can be reused by HTTP handlers, CLI scripts, and background jobs.

---

## Files & Models

### `enums.py` — Shared Enumerations

String enums used across the platform. Includes a Python 3.10 polyfill for `StrEnum`.

| Enum | Values | Use Case |
|---|---|---|
| `Capability` | `chat`, `reasoning`, `tool_calling`, `embedding`, `evaluation`, `classification` | Capabilities a model can declare for routing. |
| `ModelStatus` | `registered`, `deployed`, `disabled`, `failed` | Lifecycle status of a model in the registry. |
| `DeploymentStatus` | `pending`, `ready`, `unloaded`, `failed` | Lifecycle status of a deployment. |
| `LifecycleState` | `HOT`, `WARM`, `COLD`, `FAILED` | Thermal state of a deployment for resource management. |
| `EngineType` | `vllm`, `huggingface-transformers`, `tensorrt-llm`, `sglang`, `tgi`, `nim`, `external-api` | Supported serving engine identifiers. |

---

### `config.py` — Configuration Schemas

Pydantic models defining the validated configuration surface consumed by bootstrap.

| Model | Key Fields | Use Case |
|---|---|---|
| `PlatformMetadataConfig` | `name`, `environment` | Global platform identity. |
| `GatewayConfig` | `host`, `port`, `enable_metrics` | Gateway network settings. |
| `DatabaseConfig` | `engine`, `path`, `host`, `port`, `database`, `username`, `password`, `driver`, `url`, `echo` | Database connectivity. Computed `sqlalchemy_url` property builds URLs for SQLite, PostgreSQL, and MySQL. |
| `PluginConfig` | `enabled: list[str]` | Which model family plugins to load. |
| `HuggingFaceGenerationDefaults` | `max_new_tokens`, `temperature`, `top_p`, `do_sample` | Default generation parameters for the Transformers backend. |
| `HuggingFaceRuntimeConfig` | `trust_remote_code`, `revision`, `default_dtype`, `generation` | Runtime settings for HuggingFace Transformers. |
| `OpenAICompatibleBackendConfig` | `base_url`, `api_key`, `health_path`, `models_path`, `chat_completions_path`, `metrics_path`, `request_timeout_seconds`, `default_remote_model` | Settings for remote vLLM/TGI backends. |
| `ServingConfig` | `implementation`, `default_engine`, `supported_engines`, `default_placement`, `fallback_placements`, `model_cache_dir`, `huggingface`, `vllm`, `tgi` | Master serving configuration selecting the runtime backend. |
| `TelemetrySinkConfig` | `enabled` | Feature flag for an individual telemetry sink. |
| `TelemetryConfig` | `provider`, `prometheus`, `opentelemetry` | Telemetry backend selection. |
| `PlatformConfig` | `platform`, `gateway`, `database`, `plugins`, `serving`, `telemetry` | **Root configuration model** aggregating all subsystems. |

---

### `registry.py` — Registry & Deployment Schemas

Control-plane records exchanged between gateway, services, registry, and serving backends.

| Model | Key Fields | Use Case |
|---|---|---|
| `ModelRecord` | `id`, `name`, `version`, `family`, `engine`, `capabilities`, `memory_requirement_gb`, `ownership`, `status`, `created_at`, `metadata` | Persisted model metadata used by routing and deployment. |
| `DeploymentRecord` | `deployment_id`, `model_id`, `endpoint`, `engine`, `status`, `last_used`, `created_at`, `metadata` | Persisted deployment metadata used by routing and serving. |
| `LifecycleRecord` | `deployment_id`, `state`, `last_transition`, `idle_duration_seconds` | Persisted lifecycle state for a deployment. |
| `ModelRegistrationRequest` | `name`, `version`, `family`, `engine`, `capabilities`, `memory_requirement_gb`, `ownership`, `metadata` | Request payload for model registration. |
| `DeploymentCreateRequest` | `model_id`, `endpoint`, `engine`, `placement`, `fallback_placements`, `metadata` | Request payload for deployment creation (supports placement hints). |

#### Utility Function

| Function | Signature | Use Case |
|---|---|---|
| `utcnow` | `() → datetime` | Returns a timezone-aware UTC timestamp for default field values. |

---

### `gateway.py` — Gateway API Schemas

HTTP request/response models for the FastAPI gateway.

| Model | Use Case |
|---|---|
| `ChatMessage` | Single chat message (`role`, `content`) in OpenAI-compatible shape. |
| `ChatCompletionRequest` | Unified chat completion request with `request_id`, `capability`, `model`, `messages`, `temperature`, `max_tokens`, `stream`, `metadata`. |
| `ChatCompletionResponse` | Internal response with `request_id`, `status`, `route` (RouteDecision), and `message`. |
| `OpenAIChatMessage` | OpenAI-compatible assistant message. |
| `OpenAIChatChoice` | OpenAI-compatible choice with `index`, `message`, `finish_reason`. |
| `OpenAIChatUsage` | Token usage block (`prompt_tokens`, `completion_tokens`, `total_tokens`). |
| `OpenAIChatCompletionResponse` | Full OpenAI-compatible response with `id`, `object`, `created`, `model`, `choices`, `usage`. |
| `ModelRegisterRequest` | Alias for `ModelRegistrationRequest`. |
| `ModelDeployRequest` | Alias for `DeploymentCreateRequest`. |
| `ModelUnloadRequest` | Contains `deployment_id` for unload operations. |
| `ModelValidateRequest` | Contains `hf_repo` and optional `revision` for HuggingFace validation. |
| `ModelResponse` | Wraps a single `ModelRecord`. |
| `ModelsResponse` | Wraps a list of `ModelRecord`. |
| `DeploymentResponse` | Wraps a single `DeploymentRecord`. |
| `ValidationResponse` | Wraps a `ValidationReport`. |

---

### `routing.py` — Routing Schemas

| Model | Key Fields | Use Case |
|---|---|---|
| `RouteRequest` | `capability`, `labels`, `preferred_model_id`, `metadata` | Input to the router for deployment selection. |
| `RouteDecision` | `model_id`, `deployment_id`, `endpoint`, `capability`, `reason` | Output of routing containing the selected deployment. |

---

### `telemetry.py` — Telemetry Schemas

| Model | Key Fields | Use Case |
|---|---|---|
| `TelemetryEvent` | `request_id`, `deployment_id`, `model_name`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `cache_hit`, `error`, `timestamp`, `metadata` | Single request telemetry event. |
| `MetricsSnapshot` | `total_requests`, `total_errors`, `average_latency_ms` | Aggregate metrics snapshot for health/metrics endpoints. |

---

### `validation.py` — Validation Schemas

| Model | Key Fields | Use Case |
|---|---|---|
| `ValidationReport` | `hf_repo`, `revision`, `architecture`, `tokenizer_status`, `chat_template_status`, `config_status`, `compatibility`, `recommended_backend`, `estimated_gpu_memory_gb`, `max_context_length`, `smoke_test_status`, `json_validity_status`, `notes`, `metadata` | Comprehensive compatibility and onboarding report for a model candidate. |
