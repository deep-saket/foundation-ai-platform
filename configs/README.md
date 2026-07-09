# `configs/` — Platform Configuration

YAML configuration files governing all platform subsystems. The platform is configuration-driven by design — these files are loaded by `ConfigLoader` at bootstrap time, validated into Pydantic models, and can be overridden by environment variables using the `LLM_PLATFORM__` prefix.

---

## Root Configuration

### `platform.yaml`

**Main platform configuration file.** Defines settings for all subsystems:

| Section | Key Settings | Description |
|---|---|---|
| `platform` | `name`, `environment` | Global platform identity and environment label. |
| `gateway` | `host`, `port`, `enable_metrics` | FastAPI gateway network binding. |
| `database` | `engine`, `path` | Database backend (SQLite by default, supports PostgreSQL/MySQL). |
| `plugins.enabled` | `[qwen, llama, mistral, deepseek]` | Model family plugins to load at startup. |
| `serving` | `implementation`, `default_engine`, `supported_engines`, `default_placement`, `model_cache_dir` | Serving runtime selection and engine configuration. |
| `serving.vllm` | `base_url`, `api_key`, `default_remote_model` | vLLM remote backend connectivity. |
| `serving.tgi` | `base_url`, `api_key`, `default_remote_model` | TGI remote backend connectivity. |
| `serving.huggingface` | `trust_remote_code`, `default_dtype`, `generation.*` | Local HuggingFace Transformers runtime settings. |
| `telemetry` | `provider`, `prometheus.enabled`, `opentelemetry.enabled` | Telemetry provider selection and sink feature flags. |

### `vllm_config.yaml`

Docker-specific vLLM serving configuration used by `DockerManager`.

| Key | Value | Description |
|---|---|---|
| `engine_image` | `vllm/vllm-openai:latest` | Docker image for the vLLM container. |
| `model_name` | `Qwen/Qwen2.5-7B-Instruct` | Model to load into the vLLM server. |
| `container_name` | `vllm-server-automated` | Docker container name. |
| `port` | `8001` | Port the vLLM server listens on. |
| `volumes` | `host_path` → `container_path` | Model cache volume mount. |

---

## Sub-Directories

### `capabilities/capabilities.yaml`

Declares the platform's supported capability types and their descriptions.

### `deployments/`

| File | Description |
|---|---|
| `default.yaml` | Default deployment template settings. |
| `placement_profiles.yaml` | Predefined placement profiles for different hardware targets (CPU, CUDA, MPS). |

### `lifecycle/policies.yaml`

Lifecycle policy configuration — idle timeout thresholds for WARM and COLD transitions.

### `models/`

| File | Description |
|---|---|
| `catalog.yaml` | Sample model catalog used by `scripts/bootstrap.py` to seed the registry with initial models. |
| `qwen3_1_7b.yaml` | Model definition for Qwen3-1.7B (for registration scripts). |

### `routing/routes.yaml`

Routing policy configuration — capability-to-model routing rules.

### `telemetry/telemetry.yaml`

Telemetry-specific configuration — sink settings and feature flags.

### `validation/backend_compatibility.yaml`

Architecture-to-backend compatibility rules used by `HuggingFaceModelInspector` to recommend a serving backend for each model architecture (e.g., `Qwen2ForCausalLM` → `vllm`).
